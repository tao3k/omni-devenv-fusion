# agent/cli/commands/skill/create.py
"""
Create commands for skill CLI.

Contains: templates, create commands.
"""

from __future__ import annotations

import typer
from rich.panel import Panel

from .base import _load_templates_module, err_console, skill_app


@skill_app.command("templates")
def skill_templates(
    skill_name: str = typer.Argument(..., help="Skill name"),
    list_templates: bool = typer.Option(False, "--list", "-l", help="List available templates"),
    eject: str | None = typer.Option(None, "--eject", "-e", help="Copy template to user directory"),
    info: str | None = typer.Option(None, "--info", "-i", help="Show template content"),
):
    """Manage skill templates."""
    templates = _load_templates_module()

    if templates is None:
        err_console.print(Panel("Templates module not found", title="❌ Error", style="red"))
        return

    if list_templates:
        result = templates.format_template_list(skill_name)
        err_console.print(Panel(result, title=f"📋 Templates: {skill_name}", expand=False))
    elif eject:
        result = templates.format_eject_result(skill_name, eject)
        err_console.print(Panel(result, title="✅ Eject Result", expand=False))
    elif info:
        result = templates.format_info_result(skill_name, info)
        err_console.print(Panel(result, title="📄 Template Info", expand=False))
    else:
        err_console.print(
            Panel(
                "Use --list, --eject, or --info",
                title="ℹ️ Usage",
                style="blue",
            )
        )


@skill_app.command("create")
def skill_create(
    skill_name: str = typer.Argument(..., help="New skill name (kebab-case)"),
    description: str = typer.Option(..., "--description", "-d", help="Skill description"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing skill"),
):
    """Create a new skill from template."""
    import shutil

    from omni.foundation.config.skills import SKILLS_DIR

    skills_dir = SKILLS_DIR()
    skill_dir = skills_dir / skill_name

    if skill_dir.exists() and not force:
        err_console.print(
            Panel(
                f"Skill '{skill_name}' already exists. Use --force to overwrite.",
                title="❌ Error",
                style="red",
            )
        )
        raise typer.Exit(1)

    if skill_dir.exists() and force:
        shutil.rmtree(skill_dir)

    # Create skill directory
    skill_dir.mkdir(parents=True, exist_ok=True)

    # Create SKILL.md from template
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(f"""---
name: {skill_name}
version: 1.0.0
description: {description}
routing_keywords: []
intents: []
authors: []
---

{description}
""")

    # Create scripts directory
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir()

    # Create __init__.py
    (scripts_dir / "__init__.py").write_text('"""Scripts for {skill_name} skill."""')

    err_console.print(
        Panel(
            f"Created skill '{skill_name}' at {skill_dir}",
            title="✅ Success",
            style="green",
        )
    )
