#!/usr/bin/env python3
"""
@omni Command Invocation Performance Benchmark

Measures @omni command invocation performance.
"""

from __future__ import annotations

import asyncio
import gc
import sys
import time
from pathlib import Path

# Try to import get_project_root from common.gitops (standalone module)
try:
    from common.gitops import get_project_root
except ImportError:
    # Fallback for when common package isn't in sys.path yet
    def get_project_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent


def setup_import_path() -> None:
    """Ensure packages are in path."""
    root = get_project_root()
    agent_src = root / "packages" / "python" / "agent" / "src"
    common_src = root / "packages" / "python" / "common" / "src"

    for src in [str(agent_src), str(common_src)]:
        if src not in sys.path:
            sys.path.insert(0, src)


class FakeContext:
    """Fake MCP context for benchmarking."""

    async def info(self, msg: str) -> None:
        pass

    async def report_progress(self, current: int, total: int) -> None:
        pass


async def run_benchmarks():
    from agent.mcp_server import omni
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()
    skills = manager.list_available()
    print(f"Available skills: {len(skills)} - {skills[:5]}...")

    # Clear loaded skills for clean cold start
    for skill in list(manager._skills.keys()):
        manager.unload(skill)

    print("\n=== @omni Performance Benchmark ===\n")

    results = []

    # Cold start - first invocation
    gc.collect()
    t0 = time.perf_counter()
    try:
        result = await omni("git.status", {}, FakeContext())
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("git.status (cold)", "cold", elapsed, None))
        print(f"  git.status (cold):     {elapsed:>8.1f}ms")
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("git.status (cold)", "cold", elapsed, str(e)))
        print(f"  git.status (cold):     ERROR - {e}")

    # Warm invocations
    for i in range(5):
        gc.collect()
        t0 = time.perf_counter()
        try:
            result = await omni("git.status", {}, FakeContext())
            elapsed = (time.perf_counter() - t0) * 1000
            results.append((f"git.status (warm#{i + 1})", "warm", elapsed, None))
            print(f"  git.status (warm#{i + 1}):   {elapsed:>8.1f}ms")
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append((f"git.status (warm#{i + 1})", "warm", elapsed, str(e)))
            print(f"  git.status (warm#{i + 1}):   ERROR - {e}")

    # Different commands
    cmds = [
        ("git.log", {"max_count": "5"}),
        ("git.diff", {}),
        ("git.branch", {}),
    ]

    for cmd, args in cmds:
        gc.collect()
        t0 = time.perf_counter()
        try:
            result = await omni(cmd, args, FakeContext())
            elapsed = (time.perf_counter() - t0) * 1000
            results.append((f"{cmd}", "warm", elapsed, None))
            print(f"  {cmd}:          {elapsed:>8.1f}ms")
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            results.append((f"{cmd}", "warm", elapsed, str(e)))
            print(f"  {cmd}:          ERROR - {e}")

    # Help commands
    print("\n  --- Help Commands ---")
    gc.collect()
    t0 = time.perf_counter()
    try:
        result = await omni("help", {}, FakeContext())
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("omni help", "help", elapsed, None))
        print(f"  omni help:            {elapsed:>8.1f}ms")
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("omni help", "help", elapsed, str(e)))
        print(f"  omni help:            ERROR - {e}")

    gc.collect()
    t0 = time.perf_counter()
    try:
        result = await omni("git", {}, FakeContext())
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("omni git", "help", elapsed, None))
        print(f"  omni git:             {elapsed:>8.1f}ms")
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("omni git", "help", elapsed, str(e)))
        print(f"  omni git:             ERROR - {e}")

    # Cross-skill
    print("\n  --- Cross-Skill ---")
    gc.collect()
    t0 = time.perf_counter()
    try:
        result = await omni("terminal.run", {"cmd": "echo test"}, FakeContext())
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("terminal.run", "cross_skill", elapsed, None))
        print(f"  terminal.run:         {elapsed:>8.1f}ms")
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(("terminal.run", "cross_skill", elapsed, str(e)))
        print(f"  terminal.run:         ERROR - {e}")

    # Summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)

    cold = [r for r in results if r[1] == "cold" and not r[3]]
    warm = [r for r in results if r[1] == "warm" and not r[3]]
    help_cmds = [r for r in results if r[1] == "help" and not r[3]]
    cross = [r for r in results if r[1] == "cross_skill" and not r[3]]

    if cold:
        avg = sum(r[2] for r in cold) / len(cold)
        print(f"Cold start:  avg={avg:.1f}ms")

    if warm:
        times = [r[2] for r in warm]
        avg = sum(times) / len(times)
        print(f"Warm calls:  avg={avg:.1f}ms, min={min(times):.1f}ms, max={max(times):.1f}ms")

    if help_cmds:
        avg = sum(r[2] for r in help_cmds) / len(help_cmds)
        print(f"Help calls:  avg={avg:.1f}ms")

    if cross:
        print(f"Cross-skill: {cross[0][2]:.1f}ms")

    # Show loaded skills
    loaded = manager.list_loaded()
    print(f"\nLoaded skills: {loaded}")


def main():
    setup_import_path()
    asyncio.run(run_benchmarks())


if __name__ == "__main__":
    main()
