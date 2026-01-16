# agent/cli/commands/skill/create.py
"""
Create commands for skill CLI.

Contains: templates, create commands.
"""

from __future__ import annotations

import typer
from typing import Optional

from rich.panel import Panel

from .base import skill_app, err_console, _load_templates_module


@skill_app.command("templates")
def skill_templates(
    skill_name: str = typer.Argument(..., help="Skill name"),
    list_templates: bool = typer.Option(False, "--list", "-l", help="List available templates"),
    eject: Optional[str] = typer.Option(
        None, "--eject", "-e", help="Copy template to user directory"
    ),
    info: Optional[str] = typer.Option(None, "--info", "-i", help="Show template content"),
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
    from agent.testing.context import TestContext

    ctx = TestContext()
    ctx.create_skill(skill_name, description, force=force)
