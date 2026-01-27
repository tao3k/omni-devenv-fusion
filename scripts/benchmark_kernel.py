#!/usr/bin/env python3
"""
Kernel Boot Performance Benchmark

Usage:
    python scripts/benchmark_kernel.py [--verbose]
"""

from __future__ import annotations

import asyncio
import sys
import time
from contextlib import contextmanager
from typing import Generator


class TimingContext:
    """Simple timing context manager."""

    def __init__(self, name: str, verbose: bool = True):
        self.name = name
        self.verbose = verbose
        self.start_time = 0
        self.end_time = 0
        self.elapsed = 0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        self.elapsed = (self.end_time - self.start_time) * 1000
        if self.verbose:
            print(f"[TIMING] {self.name}: {self.elapsed:.2f}ms", file=sys.stderr)
        return self.elapsed


async def benchmark_kernel_init() -> dict:
    """Benchmark kernel initialization phases."""
    from omni.agent.server import create_agent_handler

    results = {}

    with TimingContext("Total kernel init"):
        handler = create_agent_handler()

    with TimingContext("handler.initialize()"):
        await handler.initialize()

    kernel = handler._kernel
    results["skills_count"] = len(kernel.skill_context.list_skills())
    results["commands_count"] = len(kernel.skill_context.get_core_commands())
    results["status"] = "ready" if kernel._lifecycle.is_ready() else "not_ready"

    return results


async def benchmark_tools_list() -> dict:
    """Benchmark tools/list response time."""
    from omni.agent.server import create_agent_handler

    handler = create_agent_handler()
    await handler.initialize()

    async with TimingContext("tools/list (with init)") as elapsed:
        skill_context = handler._kernel.skill_context
        tools = []
        for skill_name in list(skill_context._skills.keys())[:5]:
            skill = skill_context._skills.get(skill_name)
            if skill:
                for cmd in skill.list_commands()[:10]:
                    tools.append({"name": cmd, "skill": skill_name})

    return {
        "tools_count": len(tools),
        "elapsed_ms": elapsed,
    }


async def main():
    """Main benchmark entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Kernel boot benchmark")
    parser.add_argument("--verbose", action="store_true", default=True)
    parser.add_argument("--init", action="store_true", help="Benchmark kernel init")
    parser.add_argument("--tools", action="store_true", help="Benchmark tools/list")
    args = parser.parse_args()

    print("Kernel Boot Benchmark", file=sys.stderr)
    print("=" * 40, file=sys.stderr)

    if args.init or not (args.init or args.tools):
        print("\n[1] Benchmarking kernel initialization...", file=sys.stderr)
        try:
            results = await benchmark_kernel_init()
            print(f"  Skills loaded: {results['skills_count']}", file=sys.stderr)
            print(f"  Commands loaded: {results['commands_count']}", file=sys.stderr)
            print(f"  Status: {results['status']}", file=sys.stderr)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            return 1

    if args.tools:
        print("\n[2] Benchmarking tools/list...", file=sys.stderr)
        try:
            results = await benchmark_tools_list()
            print(f"  Tools retrieved: {results['tools_count']}", file=sys.stderr)
            print(f"  Elapsed: {results['elapsed_ms']:.2f}ms", file=sys.stderr)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
