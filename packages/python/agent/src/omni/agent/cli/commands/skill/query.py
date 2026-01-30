# agent/cli/commands/skill/query.py
"""
Query commands for skill CLI.

Contains: list, info, query commands.
(discover/search deprecated in thin client model)
"""

from __future__ import annotations

import json
import sys

import typer
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .base import err_console, skill_app


@skill_app.command("query")
def skill_query(
    query: str = typer.Argument(..., help="Search query (e.g., 'commit changes', 'read file')"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of results"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """
    Search for tools matching the given intent.

    Shows tool name, description, and smart usage template with parameters.
    """
    from omni.core.skills.discovery import SkillDiscoveryService

    service = SkillDiscoveryService()
    matches = service.search_tools(query=query, limit=limit)

    if not matches:
        err_console.print(
            Panel(
                f"No tools found matching '{query}'",
                title="🔍 Search Results",
                style="yellow",
            )
        )
        return

    if json_output:
        output = [
            {
                "name": m.name,
                "skill_name": m.skill_name,
                "description": m.description,
                "score": round(m.score, 3),
                "usage_template": m.usage_template,
            }
            for m in matches
        ]
        err_console.print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        # Create table with results
        table = Table(title=f"🔍 Search Results: '{query}'", show_header=True)
        table.add_column("Tool", style="bold cyan")
        table.add_column("Usage Template", style="green")
        table.add_column("Score", justify="right")

        for m in matches:
            table.add_row(
                f"[bold]{m.name}[/bold]\n[muted]{m.description[:60]}...[/muted]",
                f"[green]{m.usage_template}[/green]",
                f"{m.score:.2f}",
            )

        err_console.print(table)

        # Show hint
        err_console.print(
            Panel(
                "💡 Copy the usage_template above to call the tool with @omni()",
                title="Tip",
                style="blue",
            )
        )


@skill_app.command("list")
def skill_list(
    compact: bool = typer.Option(False, "--compact", "-c", help="Show compact view (names only)"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output all skills info as JSON (from Rust DB)"),
):
    """
    List installed skills and their commands.

    Displays a hierarchical inventory of all available capabilities,
    including command aliases defined in settings.yaml.

    Use --json to get machine-readable output of all skills from the Rust DB index.
    """
    import asyncio

    from rich.tree import Tree
    from rich.text import Text
    from omni.core.kernel import get_kernel
    from omni.core.config.loader import load_command_overrides, is_filtered
    from omni.foundation.config.skills import SKILLS_DIR
    from omni.foundation.bridge import RustVectorStore

    # JSON output mode - dump all skills from Rust DB with full metadata
    if json_output:
        try:
            store = RustVectorStore()
            skills_dir = SKILLS_DIR()
            skills = asyncio.run(store.get_skill_index(str(skills_dir)))

            output = []
            for skill in skills:
                skill_path = skill.get("path", "")
                docs_path = f"{skill_path}/SKILL.md" if skill_path else ""

                # Extract docs_available subfields
                docs_avail = skill.get("docs_available", {})
                docs_status = {
                    "skill_md": docs_avail.get("skill_md", False) if isinstance(docs_avail, dict) else False,
                    "readme": docs_avail.get("readme", False) if isinstance(docs_avail, dict) else False,
                    "tests": docs_avail.get("tests", False) if isinstance(docs_avail, dict) else False,
                }

                # Convert require_refs to list of strings
                require_refs = skill.get("require_refs", [])
                if require_refs and isinstance(require_refs[0], dict):
                    require_refs = [r.get("path", r) if isinstance(r, dict) else r for r in require_refs]
                elif require_refs and isinstance(require_refs[0], str):
                    pass  # Already strings
                else:
                    require_refs = []

                # Convert sniffing_rules to simplified format
                sniffing_rules = skill.get("sniffing_rules", [])
                if sniffing_rules and isinstance(sniffing_rules[0], dict):
                    sniffing_rules = [
                        {
                            "type": r.get("type", ""),
                            "pattern": r.get("pattern", ""),
                        }
                        for r in sniffing_rules
                    ]

                skill_data = {
                    "name": skill.get("name", ""),
                    "path": skill_path,
                    "docs_path": docs_path,
                    "description": skill.get("description", ""),
                    "version": skill.get("version", "unknown"),
                    "repository": skill.get("repository", ""),
                    "routing_keywords": skill.get("routing_keywords", []),
                    "intents": skill.get("intents", []),
                    "authors": skill.get("authors", []),
                    "permissions": skill.get("permissions", []),
                    "require_refs": require_refs,
                    "oss_compliant": skill.get("oss_compliant", []),
                    "compliance_details": skill.get("compliance_details", []),
                    "sniffing_rules": sniffing_rules,
                    "docs_available": docs_status,
                    "has_extensions": bool(skill.get("tools")),
                    "tools": [
                        {
                            "name": t.get("name", ""),
                            "description": t.get("description", ""),
                            "category": t.get("category", ""),
                            "input_schema": t.get("input_schema", ""),
                            "file_hash": t.get("file_hash", ""),
                        }
                        for t in skill.get("tools", [])
                    ],
                }
                output.append(skill_data)

            # Output JSON to stdout (for piping) instead of stderr
            sys.stdout.write(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
            return
        except Exception as e:
            err_console.print(
                Panel(
                    f"Failed to load skill index: {e}",
                    title="Error",
                    style="red",
                )
            )
            raise typer.Exit(1)

    skills_dir = SKILLS_DIR()
    kernel = get_kernel()
    ctx = kernel.skill_context
    overrides = load_command_overrides()

    # Get available skills from filesystem
    available_skills = []
    if skills_dir.exists():
        available_skills = sorted(
            [d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")]
        )

    loaded_skills = ctx.list_skills()

    # Build Tree
    tree = Tree("📦 [bold]Skill Inventory[/bold]", guide_style="dim")

    for skill_name in available_skills:
        is_loaded = skill_name in loaded_skills
        status_color = "green" if is_loaded else "dim white"
        status_icon = "🟢" if is_loaded else "⚪"

        skill_node = tree.add(f"{status_icon} [bold {status_color}]{skill_name}[/]")

        if is_loaded and not compact:
            skill_obj = ctx.get_skill(skill_name)
            commands = skill_obj.list_commands() if skill_obj else []

            # Sort commands: Aliased first, then others
            commands.sort(key=lambda c: (c not in overrides.commands, c))

            for full_cmd in commands:
                # Filter hidden commands
                if is_filtered(full_cmd):
                    continue

                # Handle Alias
                override = overrides.commands.get(full_cmd)
                alias = override.alias if override else None
                append_doc = override.append_doc if override else None

                cmd_text = Text()
                if alias:
                    cmd_text.append("⭐ ", style="yellow")
                    cmd_text.append(alias, style="bold cyan")
                    cmd_text.append(f" (Canon: {full_cmd})", style="dim")
                else:
                    cmd_text.append("🔧 ", style="dim")
                    cmd_text.append(full_cmd, style="white")

                # Handle Description
                cmd_obj = ctx.get_command(full_cmd)
                desc = getattr(cmd_obj, "description", "") or ""
                if append_doc:
                    desc = f"{desc} {append_doc}"

                # Truncate description for clean display
                desc = desc.strip().split("\n")[0]
                if len(desc) > 60:
                    desc = desc[:57] + "..."

                if desc:
                    cmd_text.append(f" - {desc}", style="dim italic")

                skill_node.add(cmd_text)

            if not skill_node.children:
                skill_node.add("[dim italic]No public commands[/]")

    err_console.print(tree)
    err_console.print(
        Panel(
            'Use [bold cyan]omni run "intent"[/] to execute a task.\n'
            "Use [bold cyan]omni run skill.discover[/] to find specific tools.",
            title="💡 Tip",
            style="blue",
            expand=False,
        )
    )


@skill_app.command("info")
def skill_info(name: str = typer.Argument(..., help="Skill name")):
    """Show information about a skill."""
    import logging

    import yaml

    from omni.foundation.bridge.scanner import PythonSkillScanner
    from omni.foundation.config.skills import SKILLS_DIR

    # Suppress logging for cleaner CLI output
    logging.getLogger("omni.foundation.scanner").setLevel(logging.WARNING)

    skills_dir = SKILLS_DIR()
    skill_path = skills_dir / name
    info_path = skill_path / "SKILL.md"

    if not info_path.exists():
        err_console.print(Panel(f"Skill '{name}' not found", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Get commands from index (works even if skill is not loaded)
    commands = []
    try:
        scanner = PythonSkillScanner()
        index_entries = scanner.scan_directory()
        for entry in index_entries:
            if entry.skill_name == name:
                # Extract tool names from metadata
                metadata = entry.metadata or {}
                if "tools" in metadata:
                    # Strip skill name prefix to avoid duplication (e.g., "git.git_commit" -> "git_commit")
                    prefix = f"{name}."
                    for t in metadata["tools"]:
                        cmd_name = t.get("name", "")
                        if cmd_name.startswith(prefix):
                            cmd_name = cmd_name[len(prefix) :]
                        commands.append(cmd_name)
                break
    except Exception:
        pass  # Silently fail - commands will show 0

    # Parse SKILL.md frontmatter
    content = info_path.read_text()
    info = {"version": "unknown", "description": "", "authors": [], "keywords": []}
    if content.startswith("---"):
        _, frontmatter, _ = content.split("---", 2)
        data = yaml.safe_load(frontmatter) or {}
        info = {
            "version": data.get("version", "unknown"),
            "description": data.get("description", ""),
            "authors": data.get("authors", []),
            "keywords": data.get("routing_keywords", []),
        }

    lines = [f"**Version:** {info['version']}  "]
    lines.append(f"**Commands:** {len(commands)}")

    if info["description"]:
        lines.extend(["", f"> {info['description']}"])

    if info["authors"]:
        lines.extend(["", f"**Authors:** {', '.join(info['authors'])}"])

    if commands:
        lines.extend(["", "### Commands"])
        for cmd in commands[:10]:
            lines.append(f"- `{cmd}`")
        if len(commands) > 10:
            lines.append(f"- ... and {len(commands) - 10} more")

    markdown_content = "\n".join(lines)
    err_console.print(Panel(Markdown(markdown_content), title=f"ℹ️ {name}", expand=False))


# Deprecated commands - removed in thin client model
@skill_app.command("discover")
def skill_discover(query: str = typer.Argument(..., help="Search query")):
    """Discover skills from remote index. [DEPRECATED]"""
    err_console.print(
        Panel(
            "Remote skill discovery is not available in thin client mode.\n"
            "Skills are loaded from assets/skills/ automatically.",
            title="⚠️ Deprecated",
            style="yellow",
        )
    )


@skill_app.command("search")
def skill_search(
    query: str = typer.Argument(..., help="Semantic search query"),
    limit: int = typer.Option(5, "--limit", "-n", help="Maximum number of results"),
):
    """Search skills. [DEPRECATED]"""
    err_console.print(
        Panel(
            "Semantic skill search is not available in thin client mode.\n"
            "Use 'omni skill list' to see all available skills.",
            title="⚠️ Deprecated",
            style="yellow",
        )
    )
