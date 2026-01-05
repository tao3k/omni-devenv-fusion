#!/usr/bin/env python3
"""
agent/main.py - Phase 25 One Tool CLI

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
        description="Phase 25 One Tool CLI - Execute @omni commands",
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
        from agent.mcp_server import omni

        result = omni(args.command, parsed_args)
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
