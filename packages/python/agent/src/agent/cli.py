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
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
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


def main():
    parser = argparse.ArgumentParser(
        description="Phase 25 One Tool CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
    mcp          Start MCP server (for Claude Desktop)
    skills       Execute skill commands

Examples:
    omni mcp
    omni skills git.status
    omni skills git.log '{"n": 5}'
        """,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="help",
        choices=["mcp", "skills", "help"],
        help="Command to run",
    )
    parser.add_argument("args", nargs="*", help="Arguments")

    args = parser.parse_args()

    if args.command == "mcp":
        from agent.mcp_server import mcp

        print("🤖 Starting MCP Server (stdio mode)...")
        mcp.run(transport="stdio")
    elif args.command == "skills":
        run_skills(args.args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
