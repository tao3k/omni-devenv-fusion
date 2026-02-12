#!/usr/bin/env python3
"""
agent/main.py - Omni CLI (Kernel Native)

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

import argparse
import json
import structlog
import sys

from omni.foundation.utils.asyncio import run_async_blocking
from omni.core.kernel import get_kernel

logger = structlog.get_logger("omni.agent.main")


async def run_cli(skill_name, command_name, args):
    kernel = get_kernel()

    # 1. Boot Kernel
    if not kernel.is_ready:
        await kernel.initialize()

    # 2. Get Skill
    context = kernel.skill_context
    skill = context.get_skill(skill_name)

    if not skill:
        logger.error("Skill not found", skill=skill_name)
        return

    # 3. Execute
    try:
        result = await skill.execute(command_name, **args)
        print(result)
    except Exception as e:
        logger.error("Execution error", error=str(e))


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
    parser.add_argument(
        "--graph",
        action="store_true",
        help="Run using the experimental LangGraph Robust Workflow",
    )

    args = parser.parse_args()

    # Special handling for --graph mode
    if args.graph:
        from omni.agent.workflows.robust_task.graph import build_graph

        async def run_graph(request):
            app = build_graph()
            initial_state = {"user_request": request, "execution_history": [], "retry_count": 0}
            print(f"🚀 Starting Robust Task Graph for: {request}")
            try:
                final_state = await app.ainvoke(initial_state)
                # print(f"✅ Workflow Completed.\nResult: {final_state.get('validation_result')}")
                if final_state.get("validation_result", {}).get("is_valid"):
                    print(f"✅ Workflow Completed Successfully")
                else:
                    print(f"❌ Workflow Failed")

            except Exception as e:
                logger.error("Graph execution error", error=str(e))

        try:
            # When using --graph, the first argument 'command' is treated as the user request
            run_async_blocking(run_graph(args.command))
        except Exception as e:
            logger.error("Graph mode error", error=str(e))
            sys.exit(1)
        return

    # Parse arguments
    try:
        if args.args == "{}":
            parsed_args = {}
        else:
            parsed_args = json.loads(args.args)
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON arguments", error=str(e))
        sys.exit(1)

    # Parse skill.command format
    if "." in args.command:
        parts = args.command.split(".", 1)
        s_name, c_name = parts[0], parts[1]
    else:
        s_name, c_name = args.command, "help"

    try:
        run_async_blocking(run_cli(s_name, c_name, parsed_args))
    except Exception as e:
        logger.error("CLI error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
