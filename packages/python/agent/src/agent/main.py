#!/usr/bin/env python3
"""
agent/main.py - Omni CLI

A CLI wrapper for calling @omni commands directly from terminal.
Works with Claude Code CLI and any other terminal.

Usage:
    python -m agent.main git.status
    python -m agent.main "git.log" '{"n": 5}'
    python -m agent.main help

As installed script:
    omni git.status
    omni git.log '{"n": 5}'
    omni help
"""

import sys
import json
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Omni CLI - Execute @omni commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m agent.main git.status                    # View git status
    python -m agent.main "git.log" '{"n": 5}'          # View 5 commits
    python -m agent.main help                           # Show all skills
    python -m agent.main git                            # Show git commands

From Claude Code CLI:
    You: Run `python -m agent.main git.status` to check status
        """,
    )
    parser.add_argument(
        "command", nargs="?", default="help", help="Command (e.g., git.status, help)"
    )
    parser.add_argument(
        "args",
        nargs="?",
        default="{}",
        help="JSON arguments (e.g., '{\"n\": 5}')",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text)",
    )

    args = parser.parse_args()

    # Parse arguments
    try:
        if args.args == "{}":
            parsed_args = {}
        else:
            parsed_args = json.loads(args.args)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON arguments: {e}")
        sys.exit(1)

    # Import and call omni
    try:
        import asyncio
        from agent.core.skill_manager import get_skill_manager

        manager = get_skill_manager()

        # Parse skill.command format
        if "." in args.command:
            parts = args.command.split(".", 1)
            skill_name = parts[0]
            command_name = parts[1]
        else:
            skill_name = args.command
            command_name = "help"

        result = asyncio.run(manager.run(skill_name, command_name, parsed_args))
        print(result)

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running from the project root.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
