"""
skill.py - Skill Command Group

Phase 35.2: Modular CLI Architecture

Provides full skill management commands:
- run: Run a skill command
- list: List installed skills
- discover: Discover skills from index
- info: Show skill information
- install: Install a skill from URL
- update: Update an installed skill
- test: Test skills (Phase 35.1)
- check: Validate skill structure (Phase 35.2)
- templates: Manage skill templates (Phase 35.2)
- create: Create a new skill from template (Phase 35.2)
"""

from __future__ import annotations

import json
import typer
from typing import Optional
from pathlib import Path

from rich.panel import Panel
from rich.table import Table

from common.skills_path import SKILLS_DIR

from ..console import cli_log_handler, print_result, err_console
from ..runner import run_skills

skill_app = typer.Typer(help="Skill management commands")


@skill_app.command("run")
def skill_run(
    command: str = typer.Argument(..., help="Skill command in format 'skill.command'"),
    args_json: Optional[str] = typer.Argument(None, help="JSON arguments for the command"),
    json_output: bool = typer.Option(
        False, "--json", "-j", help="Output raw JSON instead of markdown content"
    ),
):
    """Execute a skill command."""
    commands = [command]
    if args_json:
        commands.append(args_json)
    run_skills(commands, json_output=json_output, log_handler=cli_log_handler)


@skill_app.command("list")
def skill_list():
    """List installed skills."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    skills = registry.list_available_skills()
    loaded = registry.list_loaded_skills()

    table = Table(title="📦 Installed Skills", show_header=True)
    table.add_column("Skill", style="bold")
    table.add_column("Status")
    table.add_column("Version")
    table.add_column("Dirty")

    for skill in sorted(skills):
        status = "loaded" if skill in loaded else "unloaded"
        status_style = "green" if status == "loaded" else "yellow"

        info = registry.get_skill_info(skill)
        version = info.get("version", "unknown") if info else "unknown"
        dirty = "📝" if info and info.get("dirty") else ""

        table.add_row(skill, f"[{status_style}]{status}[/{status_style}]", version, dirty)

    err_console.print(table)


@skill_app.command("discover")
def skill_discover(query: str = typer.Argument(..., help="Search query")):
    """Discover skills from remote index."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    results = registry.discover_remote_skills(query)

    if results:
        table = Table(title=f"🔍 Search Results for '{query}'", show_header=True)
        table.add_column("Name")
        table.add_column("Description")

        for name, desc in results[:20]:
            table.add_row(name, desc[:60] + "..." if len(desc) > 60 else desc)

        err_console.print(table)
    else:
        err_console.print(Panel(f"No skills found for '{query}'", title="🔍 Results"))


@skill_app.command("info")
def skill_info(name: str = typer.Argument(..., help="Skill name")):
    """Show detailed information about a skill."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    info = registry.get_skill_info(name)

    if info:
        lines = [f"# 📦 {name}", "", f"**Version**: {info.get('version', 'unknown')}", ""]

        if info.get("commands"):
            lines.append("## Commands")
            for cmd in sorted(info["commands"])[:20]:
                lines.append(f"- `{name}.{cmd}`")

        err_console.print(Panel("\n".join(lines), title=f"ℹ️ {name}", expand=False))
    else:
        err_console.print(Panel(f"Skill '{name}' not found", title="❌ Error", style="red"))
        raise typer.Exit(1)


@skill_app.command("install")
def skill_install(
    url: str = typer.Argument(..., help="Git repository URL"),
    name: Optional[str] = typer.Argument(
        None, help="Skill name (derived from URL if not provided)"
    ),
    version: str = typer.Option("main", "--version", "-v", help="Git ref (default: main)"),
):
    """Install a skill from a remote repository."""
    from agent.core.registry import get_skill_registry

    if not name:
        name = url.rstrip("/").split("/")[-1].replace("-skill", "")

    registry = get_skill_registry()
    success, msg = registry.install_remote_skill(name, url, version)

    if success:
        err_console.print(Panel(f"Installed {name} from {url}", title="✅ Success", style="green"))
    else:
        err_console.print(Panel(msg, title="❌ Failed", style="red"))
        raise typer.Exit(1)


@skill_app.command("update")
def skill_update(
    name: str = typer.Argument(..., help="Skill name"),
    version: str = typer.Option("main", "--version", "-v", help="Git ref"),
):
    """Update an installed skill."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    success, msg = registry.update_skill(name, version)

    if success:
        err_console.print(Panel(f"Updated {name} to {version}", title="✅ Success", style="green"))
    else:
        err_console.print(Panel(msg, title="❌ Failed", style="red"))
        raise typer.Exit(1)


# =============================================================================
# Skill Testing (Phase 35.1)
# =============================================================================


@skill_app.command("test")
def skill_test(
    skill_name: Optional[str] = typer.Argument(
        None, help="Skill name to test (default: all skills)"
    ),
    all_skills: bool = typer.Option(False, "--all", help="Test all skills with tests/ directory"),
):
    """Test skills using the testing framework."""
    from agent.testing.context import TestContext

    ctx = TestContext()

    if all_skills:
        results = ctx.run_all_tests()
        ctx.print_summary(results)
    elif skill_name:
        results = ctx.run_skill_tests(skill_name)
        ctx.print_summary(results)
    else:
        err_console.print(
            Panel(
                "Specify a skill name or use --all to test all skills",
                title="ℹ️ Usage",
                style="blue",
            )
        )


# =============================================================================
# Skill Structure Validation (Phase 35.2)
# =============================================================================


@skill_app.command("check")
def skill_check(
    skill_name: Optional[str] = typer.Argument(
        None, help="Skill name to check (default: all skills)"
    ),
    examples: bool = typer.Option(False, "--examples", help="Check with structure examples"),
):
    """Validate skill structure."""
    from agent.testing.context import TestContext

    ctx = TestContext()

    if skill_name:
        ctx.validate_skill_structure(skill_name, check_examples=examples)
    else:
        # Check all skills
        skills_dir = SKILLS_DIR()
        for skill_path in sorted(skills_dir.iterdir()):
            if skill_path.is_dir() and not skill_path.name.startswith("_"):
                ctx.validate_skill_structure(skill_path.name, check_examples=examples)


# =============================================================================
# Skill Templates Management (Phase 35.2)
# =============================================================================


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
    from agent.testing.context import TestContext

    ctx = TestContext()

    if list_templates:
        ctx.list_templates(skill_name)
    elif eject:
        ctx.eject_template(skill_name, eject)
    elif info:
        ctx.show_template_info(skill_name, info)
    else:
        err_console.print(
            Panel(
                "Use --list, --eject, or --info",
                title="ℹ️ Usage",
                style="blue",
            )
        )


# =============================================================================
# Create New Skill (Phase 35.2)
# =============================================================================


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


def register_skill_command(app_instance: typer.Typer) -> None:
    """Register skill subcommand with the main app."""
    app_instance.add_typer(skill_app, name="skill")


__all__ = ["skill_app", "register_skill_command"]
