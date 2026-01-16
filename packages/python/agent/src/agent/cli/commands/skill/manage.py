# agent/cli/commands/skill/manage.py
"""
Management commands for skill CLI.

Contains: run, install, update, test, check commands.
"""

from __future__ import annotations

import typer
from typing import Optional

from rich.panel import Panel

from .base import skill_app, err_console, cli_log_handler, run_skills, SKILLS_DIR


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
        result = ctx.run_skill_tests(skill_name)
        # Wrap single result in dict for print_summary
        ctx.print_summary({skill_name: result})
    else:
        err_console.print(
            Panel(
                "Specify a skill name or use --all to test all skills",
                title="ℹ️ Usage",
                style="blue",
            )
        )


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
