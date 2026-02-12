"""
generate.py - Omni RAG-Based Skill Generator (CLI)

CLI wrapper for skill generation using:
- Jinja2 templates for deterministic structure
- Semantic Cortex (RAG) for similar skill retrieval
- LLM for code generation with ODF-EP Protocol
- TaskGroup for parallel generation
- Self-correction for verification

Usage
=====

    omni skill generate "Parse CSV files"
    omni skill generate fibonacci-tool -d "Calculate fibonacci sequence"
    omni skill generate my-skill -d "My skill description" --no-interactive

Output
======

    [bold green]Omni RAG-Based Skill Generator[/bold green]

    [bold yellow]Step 1: Skill Metadata[/bold yellow]
    [bold yellow]Step 2: Semantic Cortex Retrieval[/bold yellow]
    [bold blue]Step 3: AI Engineering (LLM + RAG)[/bold blue]
    [bold green]Step 4: Verification & Self-Correction[/bold green]
    [bold green]Step 5: Writing Files[/bold green]

Related Files
=============

    - _generate_modular/rag.py - RAG retrieval
    - _generate_modular/verify.py - Verification & self-correction
    - _generate_modular/prompts.py - LLM prompt templates
    - docs/reference/odf-ep-protocol.md
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sys
import time
from pathlib import Path

import typer
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from omni.foundation.config.logging import get_logger
from omni.foundation.config.settings import get_setting
from omni.foundation.utils.asyncio import run_async_blocking
from omni.foundation.utils.templating import TemplateEngine

from .base import SKILLS_DIR, err_console, skill_app

# Import from modular submodules
from ._generate_modular import (
    format_rag_context,
    generate_commands_prompt,
    generate_readme_prompt,
    retrieve_similar_skills,
    verify_skill_code,
    fix_skill_code,
)

logger = get_logger("omni.cli.generate")

TEMPLATES_DIR = Path(get_setting("assets.templates_dir")) / "skill"


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
    words = re.findall(r"\b\w+\b", description.lower())
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
    return list(dict.fromkeys(keywords))


def _sanitize_skill_name(name: str) -> str:
    """Convert user input to valid skill name."""
    name = name.strip().lower().replace(" ", "-")
    name = re.sub(r"[^a-z0-9\-]", "", name)
    return name


async def _generate_with_llm(prompt: str) -> str:
    """Generate text using LLM with graceful fallback."""
    try:
        from omni.foundation.services.llm.client import InferenceClient

        client = InferenceClient()
        result = await client.complete(
            system_prompt="You are an expert Python developer.",
            user_query=prompt,
            max_tokens=2000,
        )

        if result["success"]:
            return _clean_llm_code(result["content"])
        else:
            logger.warning("LLM failed: %s", result.get("error"))
            return _get_fallback_code(prompt)

    except Exception:
        return _get_fallback_code(prompt)


def _get_fallback_code(prompt: str) -> str:
    """Generate fallback code when LLM is unavailable."""
    skill_match = re.search(r"Skill Name: (\w+)", prompt)
    description_match = re.search(r"Description: (.+)", prompt)

    skill_name = skill_match.group(1) if skill_match else "unknown"
    description = description_match.group(1) if description_match else "utility skill"

    return (
        '"""Commands for %s skill.\n\n%s\n"""\n\n'
        "from omni.foundation.api.decorators import skill_command\n"
        "from omni.foundation.api.types import CommandResult, CommandError\n\n\n"
        "@skill_command(\n"
        '    name="list_tools",\n'
        '    description="List all available commands for this skill.",\n'
        ")\n"
        "def list_tools() -> CommandResult:\n"
        '    """List all commands available in this skill."""\n'
        '    return CommandResult.success(data={"commands": [{"name": "list_tools"}, {"name": "example"}]})\n\n\n'
        "@skill_command(\n"
        '    name="example",\n'
        '    description="Execute the main functionality.",\n'
        ")\n"
        'def example(param: str = "default") -> CommandResult:\n'
        '    """Example command implementation."""\n'
        '    return CommandResult.success(data={"result": "result with param=\'%s\'" % param})'
    ) % (skill_name, description)


__all__ = []


@skill_app.command("templates", hidden=True)
def skill_templates(
    skill_name: str = typer.Argument(..., help="Skill name"),
    list_templates: bool = typer.Option(False, "--list", "-l", help="List available templates"),
    eject: str | None = typer.Option(None, "--eject", "-e", help="Copy template to user directory"),
    info: str | None = typer.Option(None, "--info", "-i", help="Show template content"),
):
    """Manage skill templates (hidden internal command)."""
    from .base import _load_templates_module

    templates = _load_templates_module()

    if templates is None:
        err_console.print(Panel("Templates module not found", title="Error", style="red"))
        return

    if list_templates:
        result = templates.format_template_list(skill_name)
        err_console.print(Panel(result, title="Templates: %s" % skill_name, expand=False))
    elif eject:
        result = templates.format_eject_result(skill_name, eject)
        err_console.print(Panel(result, title="Eject Result", expand=False))
    elif info:
        result = templates.format_info_result(skill_name, info)
        err_console.print(Panel(result, title="Template Info", expand=False))
    else:
        err_console.print(Panel("Use --list, --eject, or --info", title="Usage", style="blue"))


@skill_app.command("generate", short_help="Generate a new skill (RAG + LLM)")
def skill_generate(
    name: str = typer.Argument(
        None, help="Skill name (auto-derived from description if not provided)"
    ),
    description: str = typer.Option(
        None, "--description", "-d", help="Natural language description of the skill"
    ),
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-I"),
    permissions: list[str] = typer.Option(None, "--permission", "-p"),
    auto_load: bool = typer.Option(True, "--auto-load/--no-load", "-l/-L"),
):
    """Generate a new skill using RAG + LLM."""

    async def _run():
        err_console.print(Panel(Text("Omni RAG-Based Skill Generator", style="bold green")))

        start_time = time.perf_counter()

        try:
            # Wizard
            err_console.print("\n[bold yellow]Step 1: Skill Metadata[/bold yellow]")

            _name = name
            _description = description

            if not _name and not _description:
                _description = Prompt.ask(
                    "What should this skill do?", default="A useful utility skill"
                )
                _name = _sanitize_skill_name(_description.split()[0] if _description else "utility")

            if _name and not _description:
                if interactive:
                    default_desc = "Provides %s functionality" % _name
                    _description = Prompt.ask(
                        "Describe the '%s' skill" % _name, default=default_desc
                    )
                else:
                    _description = "Provides %s functionality" % _name
            elif _description and not _name:
                _name = _sanitize_skill_name(_description.split()[0] if _description else "utility")

            _name = _sanitize_skill_name(_name)
            routing_keywords = _infer_routing_keywords(_name, _description)

            if interactive:
                keywords_str = Prompt.ask("Routing Keywords", default=",".join(routing_keywords))
                routing_keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

            # Permissions
            err_console.print("\n[bold yellow]Step 2: Security Permissions[/bold yellow]")

            if permissions:
                selected_permissions = list(permissions)
            elif interactive:
                selected_permissions = []
                if Confirm.ask("  Need network/http access?", default=False):
                    selected_permissions.append("network:http")
                if Confirm.ask("  Need filesystem read?", default=False):
                    selected_permissions.extend(
                        ["filesystem:read_file", "filesystem:list_directory"]
                    )
                if Confirm.ask("  Need filesystem write?", default=False):
                    selected_permissions.append("filesystem:write_file")
            else:
                selected_permissions = []

            # Skeleton (Jinja2)
            err_console.print("\n[bold yellow]Step 3: Generating Skeleton (Jinja2)[/bold yellow]")

            skills_dir = SKILLS_DIR()
            target_dir = skills_dir / _name

            if target_dir.exists():
                if interactive:
                    if not Confirm.ask("Skill '%s' exists. Overwrite?" % _name, default=False):
                        err_console.print("Generation cancelled.")
                        return
                else:
                    err_console.print("Overwriting existing skill '%s'." % _name)
                    shutil.rmtree(target_dir)

            target_dir.mkdir(parents=True, exist_ok=True)

            context = {
                "skill_name": _name,
                "description": _description,
                "routing_keywords": routing_keywords,
                "permissions": selected_permissions,
                "author": "omni-rag-gen",
                "commands": [{"name": "list_tools"}, {"name": "example"}],
            }

            engine = _get_template_engine()
            skeleton_files = {}

            skill_md = engine.render("SKILL.md.j2", context)
            skeleton_files["SKILL.md"] = skill_md

            err_console.print("  Rendered %d skeleton file(s)" % len(skeleton_files))

            # RAG Retrieval
            err_console.print("\n[bold yellow]Step 4: Semantic Cortex Retrieval[/bold yellow]")
            rag_examples = await retrieve_similar_skills(_description, limit=3)
            rag_context = format_rag_context(rag_examples)
            err_console.print("  Retrieved %d RAG examples" % len(rag_examples))

            # LLM Generation (TaskGroup Parallel)
            err_console.print("\n[bold blue]Step 5: AI Engineering (LLM + RAG)[/bold blue]")

            permissions_str = ", ".join(selected_permissions) if selected_permissions else "none"
            commands_prompt = generate_commands_prompt(
                _name, _description, permissions_str, rag_context
            )
            readme_prompt = generate_readme_prompt(_name, _description)

            generated_files = {}
            try:
                async with asyncio.TaskGroup() as tg:
                    cmd_task = tg.create_task(_generate_with_llm(commands_prompt))
                    readme_task = tg.create_task(_generate_with_llm(readme_prompt))

                generated_files["scripts/commands.py"] = cmd_task.result()
                generated_files["README.md"] = readme_task.result()
            except ExceptionGroup as e:
                err_console.print("  Parallel generation had errors: %s" % e)
                generated_files["scripts/commands.py"] = await _generate_with_llm(commands_prompt)
                generated_files["README.md"] = await _generate_with_llm(readme_prompt)

            err_console.print("  Generated %d file(s)" % len(generated_files))

            # Verification & Self-Correction
            err_console.print("\n[bold green]Step 6: Verification & Self-Correction[/bold green]")

            commands_code = generated_files.get("scripts/commands.py", "")
            verification = await verify_skill_code(commands_code)

            if not verification["valid"]:
                err_console.print("  Verification failed: %s" % verification["error"])
                err_console.print("  Attempting auto-fix...")

                for attempt in range(3):
                    fixed = await fix_skill_code(commands_code, verification["error"], rag_context)
                    verification = await verify_skill_code(fixed)
                    if verification["valid"]:
                        generated_files["scripts/commands.py"] = fixed
                        err_console.print("  Auto-fixed on attempt %d" % (attempt + 1))
                        break
                else:
                    err_console.print("  Auto-fix failed. Using original code.")
            else:
                err_console.print("  Verification passed!")

            # Materialize
            err_console.print("\n[bold green]Step 7: Writing Files[/bold green]")

            for rel_path, content in generated_files.items():
                full_path = target_dir / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                err_console.print("  Created %s" % rel_path)

            # Success
            duration_ms = (time.perf_counter() - start_time) * 1000

            success_msg = (
                "Skill: %s\nDescription: %s\nPermissions: %s\nFiles: %s\nDuration: %.0fms"
                % (
                    _name,
                    _description,
                    permissions_str,
                    ", ".join(generated_files.keys()),
                    duration_ms,
                )
            )

            err_console.print(
                Panel(
                    success_msg,
                    title="Generation Successful",
                    border_style="green",
                )
            )

            usage_name = _name.replace("-", "_")
            err_console.print('\nUsage: @omni("%s.example")' % usage_name)

            if auto_load:
                err_console.print("\nSkill saved to %s/" % target_dir)

        except KeyboardInterrupt:
            err_console.print("\nGeneration cancelled.")
            sys.exit(130)
        except Exception as e:
            err_console.print(Panel("Error: %s" % e, title="Critical Error", border_style="red"))
            sys.exit(1)

    run_async_blocking(_run())


__all__ = []
