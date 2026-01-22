# agent/cli/commands/skill/query.py
"""
Query commands for skill CLI.

Contains: list, info commands.
(discover/search deprecated in thin client model)
"""

from __future__ import annotations

import typer
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from .base import err_console, skill_app


@skill_app.command("list")
def skill_list():
    """List installed and loaded skills."""
    from omni.core.kernel import get_kernel
    from omni.foundation.config.skills import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    kernel = get_kernel()
    ctx = kernel.skill_context

    # Get available skills from filesystem
    available = []
    if skills_dir.exists():
        available = [
            d.name for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")
        ]

    # Get loaded skills
    loaded = ctx.list_skills()

    table = Table(title="📦 Installed Skills", show_header=True)
    table.add_column("Skill", style="bold")
    table.add_column("Status")
    table.add_column("Commands")

    for skill in sorted(available):
        status = "loaded" if skill in loaded else "unloaded"
        status_style = "green" if status == "loaded" else "yellow"

        skill_obj = ctx.get_skill(skill)
        cmd_count = len(skill_obj.list_commands()) if skill_obj else 0

        table.add_row(skill, f"[{status_style}]{status}[/{status_style}]", str(cmd_count))

    err_console.print(table)


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
