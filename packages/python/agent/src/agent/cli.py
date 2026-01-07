#!/usr/bin/env python3
"""
agent/cli.py - Phase 25 One Tool CLI with Typer + Rich

Usage:
    omni mcp                      # Start MCP server (for Claude Desktop)
    omni skill run <cmd>          # Execute skill command
    omni skill install <url>      # Install a skill from URL
    omni skill list               # List installed skills
    omni skill info <name>        # Show skill information
    omni skill discover <query>   # Discover skills from index
    omni skill update <name>      # Update an installed skill
    omni --help                   # Show this help
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.json import JSON
from typing import Optional

from common.gitops import get_project_root
from common.settings import get_setting

app = typer.Typer(
    name="omni",
    help="Omni DevEnv - Phase 25 One Tool CLI",
    add_completion=False,
)

console = Console()

# Get project root from gitops (uses PRJ_ROOT env or git toplevel)
PROJECT_ROOT = get_project_root()


def run_skills(commands):
    """Execute skill commands - lightweight, no MCP overhead."""
    from agent.core.skill_manager import get_skill_manager

    if not commands or commands[0] in ("help", "?"):
        # Show available skills
        skill_manager = get_skill_manager()
        skills = skill_manager.skills

        console.print()
        console.print(Panel("# 🛠️ Available Skills", style="bold blue"))
        console.print()

        for name, skill in sorted(skills.items()):
            console.print(f"## {name}")
            console.print(f"- **Commands**: {len(skill.commands)}")
            for cmd_name in list(skill.commands.keys())[:5]:
                console.print(f"  - `{name}.{cmd_name}`")
            if len(skill.commands) > 5:
                console.print(f"  - ... and {len(skill.commands) - 5} more")
            console.print()
        console.print("---")
        console.print("**Usage**: `@omni('skill.command', args={})`")
        console.print("**Help**: `@omni('skill')` or `@omni('help')`")
        return

    # Execute skill command
    cmd = commands[0]
    if "." not in cmd:
        console.print(
            Panel(f"Invalid format: {cmd}. Use skill.command", title="❌ Error", style="red")
        )
        raise typer.Exit(1)

    parts = cmd.split(".")
    skill_name = parts[0]
    cmd_name = "_".join(parts[1:])

    skill_path = (
        PROJECT_ROOT / get_setting("skills.path", "assets/skills") / f"{skill_name}/tools.py"
    )
    if not skill_path.exists():
        console.print(Panel(f"Skill not found: {skill_name}", title="❌ Error", style="red"))
        raise typer.Exit(1)

    # Parse args if provided
    import json

    cmd_args = {}
    if len(commands) > 1 and commands[1].startswith("{"):
        try:
            cmd_args = json.loads(commands[1])
        except json.JSONDecodeError as e:
            console.print(Panel(f"Invalid JSON args: {e}", title="❌ Error", style="red"))
            raise typer.Exit(1)

    # Dynamically import and call
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"{skill_name}_tools", str(skill_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    func_name = f"{skill_name}_{cmd_name}" if cmd_name else cmd_name
    func = getattr(module, func_name, None)

    if func is None:
        func = getattr(module, cmd_name, None)

    if func is None:
        console.print(
            Panel(f"Command not found: {skill_name}.{cmd_name}", title="❌ Error", style="red")
        )
        raise typer.Exit(1)

    result = func(**cmd_args) if cmd_args else func()
    console.print(result)


# =============================================================================
# MCP Command
# =============================================================================


@app.command("mcp")
def run_mcp(
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port for SSE transport"),
):
    """Start MCP server (for Claude Desktop)."""
    from agent.mcp_server import mcp

    console.print("🤖 Starting MCP Server (stdio mode)...")
    mcp.run(transport="stdio")


# =============================================================================
# Skill Management Commands
# =============================================================================

skill_app = typer.Typer(help="Skill management: run, install, list, info, discover, update")


@skill_app.callback()
def skill_callback():
    """Skill management commands."""
    pass


@skill_app.command("run")
def skill_run(
    args: list[str] = typer.Argument(
        ..., help='Skill command and arguments (e.g., crawl4ai.crawl_webpage \'{"url": "..."}\')'
    ),
):
    """Execute a skill command."""
    run_skills(args)


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
        console.print(Panel(f"Installed {name} from {url}", title="✅ Success", style="green"))
    else:
        console.print(Panel(msg, title="❌ Failed", style="red"))
        raise typer.Exit(1)


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
        version = info.get("version", "unknown")
        is_dirty = info.get("is_dirty", False)
        dirty_text = Text("⚠️", style="red") if is_dirty else Text("-", style="dim")

        table.add_row(
            skill,
            Text(status, style=status_style),
            version,
            dirty_text,
        )

    console.print(table)


@skill_app.command("info")
def skill_info(
    name: str = typer.Argument(..., help="Skill name"),
):
    """Show detailed info about a skill."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    info = registry.get_skill_info(name)

    if "error" in info:
        console.print(Panel(f"Skill '{name}' not found", title="❌ Error", style="red"))
        raise typer.Exit(1)

    content = []
    content.append(f"Path: {info.get('path', 'unknown')}")
    content.append(
        f"Revision: {info.get('revision', 'unknown')[:8] if info.get('revision') else 'unknown'}"
    )

    dirty = info.get("is_dirty", False)
    dirty_text = Text("⚠️ Yes", style="red") if dirty else Text("No", style="green")
    content.append(f"Dirty: {dirty_text}")

    console.print(Panel("\n".join(content), title=f"📋 {name}", expand=False))

    if "manifest" in info:
        import json

        console.print(Panel(JSON(json.dumps(info["manifest"])), title="Manifest", expand=False))

    if "lockfile" in info:
        import json

        console.print(Panel(JSON(json.dumps(info["lockfile"])), title="Lockfile", expand=False))


@skill_app.command("discover")
def skill_discover(
    query: str = typer.Argument("", help="Search query (optional)"),
    limit: int = typer.Option(5, "--limit", "-l", help="Max results (default: 5)"),
):
    """Discover skills from the known index."""
    from agent.core.registry import discover_skills as registry_discover

    result = registry_discover(query=query, limit=limit)

    if result["count"] == 0:
        console.print(Panel("No matching skills found", title="🔍 Search Results", style="yellow"))
        return

    table = Table(title="🔍 Skill Discovery Results", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Keywords", style="dim")

    for skill in result["skills"]:
        keywords = ", ".join(skill.get("keywords", [])[:3])
        table.add_row(
            skill["id"],
            skill["name"],
            skill["description"],
            keywords,
        )

    console.print(table)
    console.print()
    console.print("💡 To install: omni skill install <url>")


# Backward-compatible function for tests
def run_skill_discover(query: str = "", limit: int = 5):
    """Discover skills from the known index (backward-compatible)."""
    from agent.core.registry import discover_skills as registry_discover

    result = registry_discover(query=query, limit=limit)

    if result["count"] == 0:
        console.print(Panel("No matching skills found", title="🔍 Search Results", style="yellow"))
        return

    table = Table(title="🔍 Skill Discovery Results", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Description")
    table.add_column("Keywords", style="dim")

    for skill in result["skills"]:
        keywords = ", ".join(skill.get("keywords", [])[:3])
        table.add_row(
            skill["id"],
            skill["name"],
            skill["description"],
            keywords,
        )

    console.print(table)
    console.print()
    console.print("💡 To install: omni skill install <url>")


@skill_app.command("update")
def skill_update(
    name: str = typer.Argument(..., help="Skill name"),
    strategy: str = typer.Option(
        "stash", "--strategy", "-s", help="Update strategy for dirty repos (default: stash)"
    ),
):
    """Update an installed skill."""
    from agent.core.registry import get_skill_registry

    registry = get_skill_registry()
    success, msg = registry.update_remote_skill(name, strategy)

    if success:
        console.print(Panel(msg, title="✅ Updated", style="green"))
    else:
        console.print(Panel(msg, title="❌ Failed", style="red"))
        raise typer.Exit(1)


# Add skill_app as a subcommand of main app
app.add_typer(skill_app, name="skill", invoke_without_command=True)


# =============================================================================
# Main Entry Point
# =============================================================================


def main():
    """Entry point for the omni CLI."""
    app()


if __name__ == "__main__":
    main()
