#!/usr/bin/env python3
"""
Skills Monitor CLI - Run a skill command with full observability.

Monitors: execution time, RSS, CPU, phase breakdown, Rust/DB events.

Usage:
  uv run python scripts/skills_monitor.py knowledge.recall '{"query":"什么是 librarian","limit":5}'
  uv run python scripts/skills_monitor.py knowledge.recall '{"query":"..."}' --verbose --json
  just skills-monitor knowledge.recall '{"query":"什么是 librarian"}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run skill command with full observability (time, RSS, CPU, phases, Rust/DB)"
    )
    parser.add_argument(
        "skill_command",
        help="Skill command (e.g. knowledge.recall)",
    )
    parser.add_argument(
        "args_json",
        nargs="?",
        default="{}",
        help="JSON object of command args (default: {})",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Stream progress and samples to stderr",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output report as JSON (to stdout)",
    )
    parser.add_argument(
        "--sample-interval",
        type=float,
        default=1.0,
        help="Metric sample interval in seconds (default: 1.0)",
    )
    args = parser.parse_args()

    try:
        cmd_args = json.loads(args.args_json) if args.args_json.strip() else {}
    except json.JSONDecodeError as e:
        print(f"Invalid JSON args: {e}", file=sys.stderr)
        return 1

    from omni.core.skills import run_skill
    from omni.foundation.config.logging import configure_logging
    from omni.foundation.runtime.skills_monitor import skills_monitor_scope

    if args.verbose:
        configure_logging(level="DEBUG", verbose=True)

    parts = args.skill_command.split(".", 1)
    if len(parts) != 2:
        print("Invalid skill_command: use skill.command (e.g. knowledge.recall)", file=sys.stderr)
        return 1
    skill_name, command_name = parts

    async with skills_monitor_scope(
        args.skill_command,
        sample_interval_s=args.sample_interval,
        verbose=args.verbose,
        output_json=args.json,
    ):
        try:
            result = await run_skill(skill_name, command_name, cmd_args)
            if not args.json:
                print(
                    result
                    if isinstance(result, str)
                    else json.dumps(result, indent=2, ensure_ascii=False)
                )
        except Exception as e:
            print(f"Skill error: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
