#!/usr/bin/env python3
"""
agent/cli/omni_loop.py
Phase 56: The Omni Loop CLI.

User-friendly CLI for the CCA Runtime Integration.

Usage:
    omni                              # Interactive REPL (default)
    omni "Fix the login bug"          # Run single task
    omni -i                           # Interactive mode (explicit)
    omni -s 10 "Refactor auth.py"     # With custom steps
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from common.lib import setup_import_paths

# Setup paths
setup_import_paths()


def print_banner():
    """Print CCA runtime banner."""
    console = Console()
    banner = Text()
    banner.append(" CCA Runtime ", style="bold green")
    banner.append("• ", style="dim")
    banner.append("Omni Loop (Phase 56)", style="italic")
    banner.append("\n")
    banner.append("Integrates ContextOrchestrator, Note-Taker, and Rust tools", style="dim")

    console.print(Panel(banner, expand=False))


async def run_task(task: str, max_steps: int = 20):
    """Run a single task through the CCA loop."""
    from agent.core.omni_agent import OmniAgent

    console = Console()

    print_banner()

    console.print(f"\n[bold]🚀 Starting Task:[/bold] {task}")
    console.print(f"[dim]Max steps: {max_steps}[/dim]\n")

    agent = OmniAgent()
    result = await agent.run(task, max_steps)

    console.print(Panel(result, title="Result", expand=False))

    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CCA Runtime - Omni Loop (Phase 56)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog="omni",
        epilog="""
Examples:
    omni                              # Interactive REPL
    omni "Fix the login bug"          # Run single task
    omni -i                           # Interactive mode
    omni -s 10 "Refactor auth.py"     # With custom steps
        """,
    )

    # Positional task argument (optional)
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Task to execute (omit for interactive mode)",
    )

    parser.add_argument(
        "-s",
        "--steps",
        type=int,
        default=20,
        help="Maximum steps (default: 20)",
    )

    parser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Enter interactive REPL mode",
    )

    parser.add_argument(
        "--repl",
        action="store_true",
        help="Enter interactive REPL mode (alias for -i)",
    )

    args = parser.parse_args()

    # Handle interactive mode flags
    if args.interactive or args.repl:
        from agent.core.omni_agent import interactive_mode

        print_banner()
        asyncio.run(interactive_mode())
        return 0

    # Handle task mode
    if args.task:
        try:
            asyncio.run(run_task(args.task, args.steps))
            return 0
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 130
        except Exception as e:
            print(f"\nError: {e}")
            return 1

    # Default: Interactive mode
    from agent.core.omni_agent import interactive_mode

    print_banner()
    asyncio.run(interactive_mode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
