"""
generate.py - Hybrid Skill Generator (Jinja2 + LLM)

Hybrid Generation Pipeline:
1. Wizard (Deterministic) -> Collect metadata & permissions
2. Template (Jinja2) -> Render SKILL.md, __init__.py
3. LLM (Creative) -> Generate commands.py, README.md
4. Materialize (Disk) -> Write all files

This combines the best of both worlds:
- Structure safety from Jinja2 templates
- Creative flexibility from LLM
"""

from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from .base import SKILLS_DIR, err_console, skill_app

# Template engine from foundation
from omni.foundation.utils.templating import TemplateEngine
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.cli.generate")

# Template paths
TEMPLATES_DIR = Path("assets/templates/skill")


def _get_template_engine() -> TemplateEngine:
    """Get template engine with skill templates."""
    return TemplateEngine(search_paths=[TEMPLATES_DIR])


def _clean_llm_code(code: str) -> str:
    """Strip markdown fences if LLM adds them."""
    code = code.strip()
    if code.startswith("```python"):
        code = code[9:]
    elif code.startswith("```"):
        code = code[3:]
    if code.endswith("```"):
        code = code[:-3]
    return code.strip()


def _infer_routing_keywords(name: str, description: str) -> list[str]:
    """Infer routing keywords from skill name and description."""
    keywords = [name]
    # Add words from description
    words = re.findall(r"\b\w+\b", description.lower())
    # Filter common words
    stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "with",
        "to",
        "from",
        "this",
        "that",
        "skill",
    }
    keywords.extend([w for w in words if w not in stop_words and len(w) > 2][:5])
    return list(dict.fromkeys(keywords))  # Preserve order, remove duplicates


def _sanitize_skill_name(name: str) -> str:
    """Convert user input to valid skill name."""
    # Replace spaces with hyphens, lowercase
    name = name.strip().lower().replace(" ", "-")
    # Remove special characters except hyphens
    name = re.sub(r"[^a-z0-9\-]", "", name)
    return name


@skill_app.command(
    "generate", short_help="Generate a new skill using Hybrid Generator (Jinja2 + LLM)"
)
def skill_generate(
    name: str = typer.Argument(
        None,
        help="Skill name (auto-derived from description if not provided)",
    ),
    description: str = typer.Option(
        None,
        "--description",
        "-d",
        help="Natural language description of the skill",
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--no-interactive",
        "-i/-I",
        help="Run in interactive mode (wizard)",
    ),
    permissions: list[str] = typer.Option(
        None,
        "--permission",
        "-p",
        help="Add permission (e.g., network:http, filesystem:read)",
    ),
    auto_load: bool = typer.Option(
        True,
        "--auto-load/--no-load",
        "-l/-L",
        help="Automatically load the generated skill",
    ),
):
    """
    Generate a new skill using Hybrid Generator (Jinja2 + LLM).

    This command combines:
    - Jinja2 templates for deterministic structure (SKILL.md, __init__.py)
    - LLM for creative implementation (commands.py, README.md)

    Examples:
        omni skill generate "Parse CSV files and convert to JSON"
        omni skill generate -d "Search for text in files" -p filesystem:read
        omni skill generate "API client for weather" -p network:http --no-interactive
    """

    async def _run():
        err_console.print(
            Panel(Text("🔧 Omni Hybrid Skill Generator (Jinja2 + LLM)", style="bold green"))
        )

        start_time = time.perf_counter()

        try:
            # ============================================================
            # STEP 1: THE WIZARD (Deterministic Input)
            # ============================================================
            err_console.print("\n[bold yellow]📝 Step 1: Skill Metadata[/bold yellow]")

            # Derive skill name from description if not provided
            if not name and not description:
                description = Prompt.ask(
                    "What should this skill do?", default="A useful utility skill"
                )
                name = _sanitize_skill_name(description.split()[0] if description else "utility")

            if name and not description:
                description = Prompt.ask(
                    f"Describe the '{name}' skill", default=f"Provides {name} functionality"
                )
            elif description and not name:
                name = _sanitize_skill_name(description.split()[0] if description else "utility")

            name = _sanitize_skill_name(name)

            # Auto-infer routing keywords
            routing_keywords = _infer_routing_keywords(name, description)

            if interactive:
                keywords_str = Prompt.ask(
                    "Routing Keywords (comma-separated)", default=",".join(routing_keywords)
                )
                routing_keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

            # ============================================================
            # SECURITY GATEKEEPER: Permissions
            # ============================================================
            err_console.print("\n[bold yellow]🛡️ Step 2: Security Permissions[/bold yellow]")

            if permissions:
                selected_permissions = list(permissions)
            elif interactive:
                selected_permissions = []
                err_console.print(
                    "Grant permissions for this skill (recommended: minimum required):"
                )

                if Confirm.ask("  Need network/http access?", default=False):
                    selected_permissions.append("network:http")
                if Confirm.ask("  Need filesystem read access?", default=False):
                    selected_permissions.extend(
                        ["filesystem:read_file", "filesystem:list_directory"]
                    )
                if Confirm.ask("  Need filesystem write access?", default=False):
                    selected_permissions.append("filesystem:write_file")
                if Confirm.ask("  Need subprocess execution?", default=False):
                    selected_permissions.append("process:run")
            else:
                selected_permissions = []

            # ============================================================
            # STEP 2: THE SKELETON (Jinja2 Scaffolding)
            # ============================================================
            err_console.print("\n[bold yellow]🏗️ Step 3: Generating Skeleton (Jinja2)[/bold yellow]")

            skills_dir = SKILLS_DIR()
            target_dir = skills_dir / name

            if target_dir.exists():
                if not Confirm.ask(f"Skill '{name}' exists. Overwrite?", default=False):
                    err_console.print("⚠️  Generation cancelled.")
                    return
            else:
                target_dir.mkdir(parents=True, exist_ok=True)

            # Prepare context for templates
            context = {
                "skill_name": name,
                "description": description,
                "routing_keywords": routing_keywords,
                "permissions": selected_permissions,
                "author": "omni-hybrid-gen",
                "commands": [
                    {"name": "list_tools", "description": "List all available commands"},
                    {
                        "name": "example",
                        "description": "Example command demonstrating the skill's functionality",
                    },
                ],
            }

            # Render deterministic files (Jinja2)
            engine = _get_template_engine()
            generated_files = {}

            # Render SKILL.md
            skill_md = engine.render("skill/SKILL.md.j2", context)
            generated_files["SKILL.md"] = skill_md

            # Render scripts/__init__.py
            init_py = engine.render("skill/scripts/__init__.py.j2", context)
            generated_files["scripts/__init__.py"] = init_py

            err_console.print(f"  ✅ Rendered {len(generated_files)} skeleton files")

            # ============================================================
            # STEP 3: THE FLESH (LLM Logic Generation)
            # ============================================================
            err_console.print("\n[bold blue]🧠 Step 4: AI Engineering (LLM)[/bold blue]")

            # Build prompts for LLM
            commands_prompt = f"""# ODF-EP PROTOCOL: skill_command Description Standards

## CRITICAL: This is a MANDATORY PROTOCOL, not a suggestion.

You MUST follow these rules strictly. Any deviation will result in INVALID output.

## Protocol Requirements

### Rule 1: First Line Must Start with Action Verb
The description's FIRST LINE must begin with one of these action verbs:
- Create, Get, Search, Update, Delete, Execute, Run, Load, Save, List, Show, Check, Build, Parse, Format, Validate, Generate, Apply, Process, Clear, Index, Ingest, Consult, Bridge, Refine, Summarize, Commit, Amend, Revert, Retrieve, Analyze, Suggest, Write, Read, Extract, Query, Filter, Detect, Navigate, Refactor

### Rule 2: Multi-line Description Must Include Args and Returns
For any function with parameters, the description MUST include:
```
Args:
    param_name: Description of the parameter. Defaults to `default_value`.

Returns:
    Description of the return value.
```

### Rule 3: Use description= Parameter (Not Docstring)
The @skill_command decorator MUST have an explicit description= parameter. Function docstrings are optional and secondary.

---

Task: Write the `scripts/commands.py` file for a new skill.

Skill Name: {name}
Description: {description}
Permissions: {", ".join(selected_permissions) if selected_permissions else "none"}

Commands to implement:
- `list_tools()`: List all commands (REQUIRED, always include this exact signature)
- `example()`: Main functionality based on description

Write ONLY the Python code for `scripts/commands.py`. Do NOT include markdown code blocks."""

            readme_prompt = f"""Write a short README.md for skill '{name}'.

Description: {description}

Include:
1. Brief overview
2. Usage examples with @omni() syntax
3. Available commands

Write in Markdown format. No code blocks needed since this is markdown."""

            with Progress(
                SpinnerColumn(), TextColumn("[progress.description]{task.description}")
            ) as progress:
                task_id = progress.add_task("Generating commands.py...", total=None)

                # Try to call LLM (graceful fallback if unavailable)
                commands_code = await _generate_with_llm(commands_prompt)
                generated_files["scripts/commands.py"] = commands_code

                progress.update(task_id, description="Generating README.md...")
                readme_code = await _generate_with_llm(readme_prompt)
                generated_files["README.md"] = readme_code

                progress.update(task_id, completed=100)

            # ============================================================
            # STEP 4: MATERIALIZATION (Write to Disk)
            # ============================================================
            err_console.print("\n[bold green]💾 Step 5: Writing Files[/bold green]")

            for rel_path, content in generated_files.items():
                full_path = target_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                err_console.print(f"  ✅ Created {rel_path}")

            # ============================================================
            # SUCCESS REPORT
            # ============================================================
            duration_ms = (time.perf_counter() - start_time) * 1000

            success_panel = _build_success_panel(
                skill_name=name,
                description=description,
                permissions=selected_permissions,
                files=list(generated_files.keys()),
                duration_ms=duration_ms,
            )
            err_console.print(success_panel)

            # Usage hint
            err_console.print(f'\n📖 Usage: @omni("{name.replace("-", "_")}.example")')

            # Auto-load if requested
            if auto_load:
                err_console.print(f"\n🔄 Skill saved to {target_dir}/")
                err_console.print("Skills are loaded automatically on next restart.")

        except KeyboardInterrupt:
            err_console.print("\n⚠️  Generation cancelled by user")
            sys.exit(130)
        except Exception as e:
            err_console.print(
                Panel(
                    f"Generation error: {e}",
                    title="💥 Critical Error",
                    border_style="red",
                )
            )
            if "--verbose" in sys.argv:
                import traceback

                err_console.print(traceback.format_exc())
            sys.exit(1)

    asyncio.run(_run())


async def _generate_with_llm(prompt: str) -> str:
    """Generate text using LLM with graceful fallback."""
    try:
        from omni.foundation.services.llm.client import InferenceClient

        client = InferenceClient()
        system_prompt = "You are an expert Python developer. Write clean, idiomatic code."

        result = await client.complete(
            system_prompt=system_prompt,
            user_query=prompt,
            max_tokens=2000,
        )

        if result["success"]:
            return _clean_llm_code(result["content"])
        else:
            logger.warning("LLM generation failed, using fallback", error=result.get("error"))
            return _get_fallback_code(prompt)

    except ImportError:
        logger.info("LLM client not available, using fallback")
        return _get_fallback_code(prompt)
    except Exception as e:
        logger.warning("LLM call failed, using fallback", error=str(e))
        return _get_fallback_code(prompt)


def _get_fallback_code(prompt: str) -> str:
    """Generate fallback code when LLM is unavailable.

    IMPORTANT: This follows ODF-EP Protocol for skill_command descriptions.
    - First line: Action verb (List, Example)
    - Multi-line: Args: and Returns: sections
    """
    # Extract skill name from prompt for context
    skill_match = re.search(r"Skill Name: (\w+)", prompt)
    description_match = re.search(r"Description: (.+)", prompt)

    skill_name = skill_match.group(1) if skill_match else "unknown"
    description = description_match.group(1) if description_match else "utility skill"

    # Escape skill_name for f-string, use regular string for the template
    safe_skill_name = skill_name

    return f'''"""Commands for {safe_skill_name} skill.

{description}
"""

from omni.foundation.api.decorators import skill_command
from omni.foundation.api.types import CommandResult, CommandError

@skill_command(
    name="list_tools",
    description="""
List all available commands for this skill.

Returns:
    CommandResult with list of available commands and their descriptions.
""",
    autowire=True,
)
def list_tools() -> CommandResult:
    """List all commands available in this skill."""
    commands = [
        {{"name": "list_tools", "description": "List all available commands"}},
        {{"name": "example", "description": "Example command demonstrating the skill's functionality"}},
    ]
    return CommandResult.success(data={{"commands": commands}})


@skill_command(
    name="example",
    description="""
Execute the main functionality of the {safe_skill_name} skill.

Args:
    param: Example parameter with default value.

Returns:
    CommandResult with execution result.
""",
    autowire=True,
)
def example(param: str = "default") -> CommandResult:
    """Example command implementation."""
    try:
        # TODO: Implement actual logic based on skill description
        result = f"Example result with param='{{param}}'"
        return CommandResult.success(data={{"result": result}})
    except Exception as e:
        raise CommandError(error=str(e))


__all__ = ["list_tools", "example"]
'''


def _build_success_panel(
    skill_name: str,
    description: str,
    permissions: list[str],
    files: list[str],
    duration_ms: float,
) -> Panel:
    """Build the success panel with generation summary."""
    from rich.table import Table

    table = Table.grid(expand=True)
    table.add_column()
    table.add_row(f"✅ Skill Generated: [bold cyan]{skill_name}[/bold cyan]")
    table.add_row(f"📝 Description: {description}")
    table.add_row(f"🛡️  Permissions: {', '.join(permissions) if permissions else 'none'}")
    table.add_row(f"📁 Files: {', '.join(files)}")
    table.add_row(f"⏱️  Duration: {duration_ms:.0f}ms")

    return Panel(
        table,
        title="✨ Generation Successful",
        border_style="green",
        expand=False,
    )


@skill_app.command("evolve", short_help="Analyze usage and suggest improvements")
def skill_evolve(
    min_frequency: int = typer.Option(2, "--min-freq", "-m", help="Minimum pattern frequency"),
    limit: int = typer.Option(5, "--limit", "-l", help="Maximum suggestions"),
):
    """
    Analyze usage patterns and suggest new skills (Harvester).

    Scans session history to find frequently used patterns that could
    be extracted into reusable skills.
    """
    err_console.print(
        Panel(
            Text("🌱 Skill Harvester - Analyzing Patterns", style="bold green"),
        )
    )

    err_console.print(
        Panel(
            "Harvester is planned for future release.",
            title="🚧 Coming Soon",
            border_style="yellow",
        )
    )


__all__ = []
