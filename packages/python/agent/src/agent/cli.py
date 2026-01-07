#!/usr/bin/env python3
"""
agent/cli.py - Phase 25 One Tool CLI (Lightweight)

Usage:
    omni mcp                 # Start MCP server (for Claude Desktop)
    omni skills git.status   # Execute skill command
    omni help                # Show this help
"""

import json
import argparse
import importlib
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

import structlog
from structlog.dev import ConsoleRenderer

# Configure logging BEFORE any other imports
console = Console()
handler = RichHandler(
    console=console,
    show_level=True,
    show_path=False,
    rich_tracebacks=True,
)

# Configure root logger first (before any other imports)
root_logger = logging.getLogger()
root_logger.handlers = [handler]
root_logger.setLevel(logging.INFO)


# Custom log level processor for structlog
def add_log_level_with_brackets(logger, method_name, event_dict):
    """Add log level with brackets to event dict."""
    level = event_dict.get("level", method_name.upper())
    event_dict["level"] = f"[{level}]"
    return event_dict


# Configure structlog with Rich console renderer
# Use stdlib LoggerFactory to avoid AttributeError with filter_by_level
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        add_log_level_with_brackets,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%m/%d/%y %H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger("INFO"),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()

# Get project root from gitops (uses PRJ_ROOT env or git toplevel)
from common.gitops import get_project_root
from common.settings import get_setting

PROJECT_ROOT = get_project_root()


def run_skills(commands):
    """Execute skill commands - lightweight, no MCP overhead."""
    if not commands or commands[0] in ("help", "?"):
        # Show available skills - with full skill manager logging
        from agent.core.skill_manager import get_skill_manager

        # Load all skills via skill manager (shows full logs)
        skill_manager = get_skill_manager()
        skills = skill_manager.skills

        print()
        print("# 🛠️ Available Skills")
        print()
        for name, skill in sorted(skills.items()):
            print(f"## {name}")
            print(f"- **Commands**: {len(skill.commands)}")
            for cmd_name in list(skill.commands.keys())[:5]:
                print(f"  - `{name}.{cmd_name}`")
            if len(skill.commands) > 5:
                print(f"  - ... and {len(skill.commands) - 5} more")
            print()
        print("---")
        print("**Usage**: `@omni('skill.command', args={})`")
        print("**Help**: `@omni('skill')` or `@omni('help')`")
        return

    # Execute skill command - clean output (no skill manager logging)
    # Parse command (e.g., "git.status" -> skill="git", cmd="git_status")
    cmd = commands[0]
    if "." not in cmd:
        logger.warning("Invalid format", format_example="skill.command")
        print(f"Invalid format: {cmd}. Use skill.command")
        return

    parts = cmd.split(".")
    skill_name = parts[0]
    cmd_name = "_".join(parts[1:])

    # Load only the specific skill module
    skill_path = (
        PROJECT_ROOT / get_setting("skills.path", "assets/skills") / f"{skill_name}/tools.py"
    )
    if not skill_path.exists():
        logger.warning("Skill not found", skill=skill_name)
        print(f"Skill not found: {skill_name}")
        return

    # Parse args if provided
    cmd_args = {}
    if len(commands) > 1 and commands[1].startswith("{"):
        try:
            cmd_args = json.loads(commands[1])
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON args", error=str(e))
            print(f"Invalid JSON args: {e}")
            return

    # Dynamically import and call
    spec = importlib.util.spec_from_file_location(f"{skill_name}_tools", str(skill_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Try both function names
    func_name = f"{skill_name}_{cmd_name}" if cmd_name else cmd_name
    func = getattr(module, func_name, None)

    if func is None:
        # Try without skill prefix
        func = getattr(module, cmd_name, None)

    if func is None:
        logger.warning("Command not found", skill=skill_name, command=cmd_name)
        print(f"Command not found: {skill_name}.{cmd_name}")
        return

    # Execute
    result = func(**cmd_args) if cmd_args else func()
    print(result)


def run_skill_install(name: str, url: str, version: str = "main"):
    """Install a skill from a remote repository."""
    from agent.core.skill_registry import get_skill_registry
    from rich.panel import Panel
    from rich.text import Text

    registry = get_skill_registry()
    success, msg = registry.install_remote_skill(name, url, version)
    if success:
        console.print(Panel(f"Installed {name} from {url}", title="✅ Success", style="green"))
    else:
        console.print(Panel(msg, title="❌ Failed", style="red"))
        sys.exit(1)


def run_skill_update(name: str, strategy: str = "stash"):
    """Update an installed skill."""
    from agent.core.skill_registry import get_skill_registry
    from rich.panel import Panel

    registry = get_skill_registry()
    success, msg = registry.update_remote_skill(name, strategy)
    if success:
        console.print(Panel(msg, title="✅ Updated", style="green"))
    else:
        console.print(Panel(msg, title="❌ Failed", style="red"))
        sys.exit(1)


def run_skill_list():
    """List installed skills."""
    from agent.core.skill_registry import get_skill_registry
    from rich.table import Table
    from rich.text import Text

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


def run_skill_info(name: str):
    """Show detailed info about a skill."""
    from agent.core.skill_registry import get_skill_registry
    from rich.panel import Panel
    from rich.json import JSON
    from rich.text import Text

    registry = get_skill_registry()
    info = registry.get_skill_info(name)

    if "error" in info:
        console.print(Panel(f"Skill '{name}' not found", title="❌ Error", style="red"))
        sys.exit(1)

    # Build info display
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
        console.print(Panel(JSON(json.dumps(info["manifest"])), title="Manifest", expand=False))

    if "lockfile" in info:
        console.print(Panel(JSON(json.dumps(info["lockfile"])), title="Lockfile", expand=False))


def run_skill_discover(query: str = "", limit: int = 5):
    """Discover skills from the known index."""
    from agent.core.skill_registry import discover_skills as registry_discover
    from rich.table import Table
    from rich.text import Text

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
    console.print(f"\n💡 To install: omni skill install <url>")
    console.print(f"   Or use JIT: @jit_install_skill('{result['skills'][0]['id']}') via MCP")


def main():
    # Main parser
    parser = argparse.ArgumentParser(
        description="Phase 25 One Tool CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # MCP command
    mcp_parser = subparsers.add_parser("mcp", help="Start MCP server")
    mcp_parser.add_argument("--port", type=int, default=None, help="Port for SSE transport")

    # Skills command (for executing skill commands)
    skills_parser = subparsers.add_parser("skills", help="Execute skill commands")
    skills_parser.add_argument("args", nargs="*", help="Skill command and arguments")

    # Skill management subcommands
    skill_parser = subparsers.add_parser("skill", help="Skill management commands")
    skill_subparsers = skill_parser.add_subparsers(dest="skill_command", help="Skill subcommands")

    # skill install
    install_parser = skill_subparsers.add_parser("install", help="Install a skill from URL")
    install_parser.add_argument("url", help="Git repository URL")
    install_parser.add_argument(
        "name", nargs="?", help="Skill name (derived from URL if not provided)"
    )
    install_parser.add_argument("--version", default="main", help="Git ref (default: main)")

    # skill update
    update_parser = skill_subparsers.add_parser("update", help="Update an installed skill")
    update_parser.add_argument("name", help="Skill name")
    update_parser.add_argument(
        "--strategy",
        choices=["stash", "abort", "overwrite"],
        default="stash",
        help="Update strategy for dirty repos (default: stash)",
    )

    # skill list
    list_parser = skill_subparsers.add_parser("list", help="List installed skills")

    # skill info
    info_parser = skill_subparsers.add_parser("info", help="Show skill information")
    info_parser.add_argument("name", help="Skill name")

    # skill discover
    discover_parser = skill_subparsers.add_parser(
        "discover", help="Discover skills from known index"
    )
    discover_parser.add_argument("query", nargs="?", default="", help="Search query (optional)")
    discover_parser.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")

    # Parse arguments
    args = parser.parse_args()

    if args.command == "mcp":
        from agent.mcp_server import mcp

        print("🤖 Starting MCP Server (stdio mode)...")
        mcp.run(transport="stdio")
    elif args.command == "skills":
        run_skills(args.args)
    elif args.command == "skill":
        if args.skill_command == "install":
            name = args.name
            if not name:
                # Derive name from URL
                name = args.url.rstrip("/").split("/")[-1].replace("-skill", "")
            run_skill_install(name, args.url, args.version)
        elif args.skill_command == "update":
            run_skill_update(args.name, args.strategy)
        elif args.skill_command == "list":
            run_skill_list()
        elif args.skill_command == "info":
            run_skill_info(args.name)
        elif args.skill_command == "discover":
            run_skill_discover(args.query, args.limit)
        else:
            skill_parser.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
