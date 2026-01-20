#!/usr/bin/env python3
"""
Performance Benchmark Suite - Omni DevEnv Fusion (Core Focus)

Comprehensive performance profiling for agent core package.
Run with: python scripts/benchmark.py

Priority Order:
1. Core Infrastructure (gitops, settings, lib)
2. Skill Management (registry, loader, manager)
3. Orchestration (router, semantic_router)
4. Schema (base models, skill manifests)

Excludes: Librarian, Harvester, Capabilities (lower priority)
"""

from __future__ import annotations

import gc
import importlib
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

# Try to import get_project_root from common.gitops (standalone module)
try:
    from common.gitops import get_project_root
except ImportError:
    # Fallback for when common package isn't in sys.path yet
    def get_project_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent

# =============================================================================
# Benchmark Framework
# =============================================================================


class BenchmarkRunner:
    """Run benchmarks and collect results."""

    def __init__(self, name: str):
        self.name = name
        self.results: list[dict] = []
        self.failed: list[dict] = []

    @contextmanager
    def measure(self, category: str, description: str, priority: int = 5):
        """Measure execution time for a block."""
        gc.collect()
        start = time.perf_counter()
        error = None
        try:
            yield
        except Exception as e:
            error = str(e)
        end = time.perf_counter()
        elapsed = (end - start) * 1000  # ms

        result = {
            "category": category,
            "description": description,
            "time_ms": elapsed,
            "priority": priority,
        }
        if error:
            result["error"] = error
            self.failed.append(result)
        else:
            self.results.append(result)

    def report(self) -> str:
        """Generate comprehensive report."""
        lines = [
            "=" * 70,
            "PERFORMANCE BENCHMARK REPORT (CORE FOCUS)",
            "=" * 70,
            "",
            f"Python: {sys.version.split()[0]}",
            f"Platform: {sys.platform}",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Sort by priority then time
        priority_order = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM", 4: "LOW", 5: "INFO"}

        for priority in range(1, 6):
            items = [r for r in self.results if r["priority"] == priority]
            if not items:
                continue

            lines.extend(
                [
                    "-" * 70,
                    f"PRIORITY {priority} - {priority_order[priority]}",
                    "-" * 70,
                ]
            )

            # Sort by time
            items = sorted(items, key=lambda x: x["time_ms"], reverse=True)
            for r in items:
                bar_len = int(r["time_ms"] / 10) if r["time_ms"] > 0 else 1
                bar = "█" * min(bar_len, 50)
                lines.append(f"{r['time_ms']:>8.1f}ms {bar} {r['description']}")

        # Failed tests
        if self.failed:
            lines.extend(
                [
                    "",
                    "-" * 70,
                    "FAILED TESTS",
                    "-" * 70,
                ]
            )
            for f in self.failed:
                lines.append(f"❌ {f['description']}: {f.get('error', 'unknown')}")

        # Summary by priority
        lines.extend(
            [
                "",
                "=" * 70,
                "SUMMARY BY PRIORITY",
                "=" * 70,
            ]
        )

        for priority in range(1, 6):
            items = [r for r in self.results if r["priority"] == priority]
            if items:
                total = sum(r["time_ms"] for r in items)
                slowest = max(r["time_ms"] for r in items)
                lines.append(
                    f"P{priority} {priority_order[priority]}: {len(items)} tests, {total:.1f}ms total, slowest: {slowest:.1f}ms"
                )

        # Top bottlenecks
        lines.extend(
            [
                "",
                "-" * 70,
                "TOP BOTTLENECKS (all priorities)",
                "-" * 70,
            ]
        )

        top5 = sorted(self.results, key=lambda x: x["time_ms"], reverse=True)[:5]
        for i, r in enumerate(top5, 1):
            lines.append(f"{i}. {r['description']}: {r['time_ms']:.1f}ms (P{r['priority']})")

        # Recommendations
        critical = [r for r in self.results if r["priority"] <= 2 and r["time_ms"] > 50]
        lines.extend(
            [
                "",
                "-" * 70,
                "RECOMMENDATIONS",
                "-" * 70,
            ]
        )
        for r in critical:
            lines.append(f"🔴 {r['description']}: {r['time_ms']:.1f}ms")

        lines.extend(
            [
                "",
                "=" * 70,
                "END OF REPORT",
                "=" * 70,
            ]
        )

        return "\n".join(lines)


def setup_import_path() -> None:
    """Ensure packages are in path."""
    root = get_project_root()
    agent_src = root / "packages" / "python" / "agent" / "src"
    common_src = root / "packages" / "python" / "common" / "src"

    for src in [str(agent_src), str(common_src)]:
        if src not in sys.path:
            sys.path.insert(0, src)


def clear_modules(prefixes: list[str]) -> None:
    """Clear modules matching prefixes."""
    to_delete = [k for k in sys.modules if any(k.startswith(p) for p in prefixes)]
    for mod in to_delete:
        del sys.modules[mod]


# =============================================================================
# Benchmark Suite (Priority Ordered)
# =============================================================================


def run_priority1_critical(runner: BenchmarkRunner) -> None:
    """PRIORITY 1: CRITICAL - Core infrastructure that fails everything."""

    # Clear all
    clear_modules(["agent", "common"])

    with runner.measure("import", "from common.gitops import get_project_root", priority=1):
        from common.gitops import get_project_root

    with runner.measure("function", "get_project_root() - FIRST CALL", priority=1):
        import common.gitops

        common.gitops._project_root = None
        from common.gitops import get_project_root

        get_project_root()

    with runner.measure("function", "get_project_root() - CACHED", priority=1):
        from common.gitops import get_project_root

        get_project_root()

    # Settings
    clear_modules(["common.config", "common.settings"])

    with runner.measure("import", "from common.config.settings import get_setting", priority=1):
        from common.config.settings import get_setting

    with runner.measure("function", "get_setting() first call", priority=1):
        get_setting("skills.path")


def run_priority2_high(runner: BenchmarkRunner) -> None:
    """PRIORITY 2: HIGH - Skill system and registry."""

    # Skill Registry
    clear_modules(["agent"])

    with runner.measure("import", "from agent.core.registry import get_skill_registry", priority=2):
        from agent.core.registry import get_skill_registry

    with runner.measure("function", "get_skill_registry() - FIRST CALL", priority=2):
        import agent.core.registry.core as core_mod

        core_mod.SkillRegistry._instance = None
        from agent.core.registry import get_skill_registry

        get_skill_registry()

    # Skill Loader
    clear_modules(["agent"])

    with runner.measure("import", "from agent.core.loader import SkillLoader", priority=2):
        from agent.core.loader import SkillLoader

    # Skill Manager
    clear_modules(["agent"])

    with runner.measure("import", "from agent.core.skill_manager import SkillManager", priority=2):
        from agent.core.skill_manager import SkillManager


def run_priority3_medium(runner: BenchmarkRunner) -> None:
    """PRIORITY 3: MEDIUM - Core models and schemas."""

    # Schema - most imports are here!
    clear_modules(["agent"])

    with runner.measure("import", "from agent.core.schema import SkillManifest", priority=3):
        from agent.core.schema import SkillManifest

    # Context Loader
    clear_modules(["agent"])

    with runner.measure(
        "import", "from agent.core.context_loader import ContextLoader", priority=3
    ):
        from agent.core.context_loader import ContextLoader


def run_priority4_low(runner: BenchmarkRunner) -> None:
    """PRIORITY 4: LOW - Orchestration and routing."""

    # Semantic Router (heavy)
    clear_modules(["agent"])

    with runner.measure(
        "import", "from agent.core.router.semantic_router import SemanticRouter", priority=4
    ):
        from agent.core.router.semantic_router import SemanticRouter


def run_priority5_info(runner: BenchmarkRunner) -> None:
    """PRIORITY 5: INFO - Utility functions."""

    # Lib utilities
    clear_modules(["common"])

    with runner.measure("import", "from common.lib import agent_src, common_src", priority=5):
        from common.lib import agent_src, common_src

    with runner.measure("function", "agent_src() cached", priority=5):
        agent_src()

    with runner.measure("function", "common_src() cached", priority=5):
        common_src()


def run_function_benchmarks(runner: BenchmarkRunner) -> None:
    """PRIORITY 1-2: Function execution benchmarks."""

    # SkillManager functions
    clear_modules(["agent"])

    with runner.measure("function", "SkillManager() instantiation", priority=2):
        from agent.core.skill_manager import SkillManager
        from pathlib import Path

        manager = SkillManager()

    with runner.measure("function", "SkillManager.discover()", priority=2):
        from agent.core.skill_manager import SkillManager

        manager = SkillManager()
        manager.discover()

    with runner.measure("function", "SkillManager.list_available()", priority=3):
        from agent.core.skill_manager import SkillManager

        manager = SkillManager()
        manager.list_available()

    # Registry functions
    clear_modules(["agent"])

    with runner.measure("function", "get_skill_registry()", priority=2):
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()

    with runner.measure("function", "list_available_skills()", priority=2):
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        registry.list_available_skills()

    with runner.measure("function", "list_loaded_skills()", priority=3):
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        registry.list_loaded_skills()

    # Semantic Router functions
    clear_modules(["agent"])

    with runner.measure("function", "SemanticRouter() instantiation", priority=3):
        from agent.core.router.semantic_router import SemanticRouter

        router = SemanticRouter()

    with runner.measure("function", "router._build_routing_menu()", priority=3):
        from agent.core.router.semantic_router import SemanticRouter

        router = SemanticRouter()
        router._build_routing_menu()

    # Vector Memory functions
    clear_modules(["agent"])

    with runner.measure("function", "get_vector_memory()", priority=3):
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()

    with runner.measure("function", "vm.list_collections()", priority=4):
        from agent.core.vector_store import get_vector_memory
        import asyncio

        async def test_list():
            vm = get_vector_memory()
            return await vm.list_collections()

        asyncio.run(test_list())


def main():
    """Run all benchmarks and output report."""
    setup_import_path()

    runner = BenchmarkRunner("Omni-Dev-Fusion Core Performance")

    print("Running core benchmarks (Priority 1-5)...")
    print()

    # Run in priority order
    run_priority1_critical(runner)
    print(f"P1 Critical: {len([r for r in runner.results if r['priority'] == 1])} tests")

    run_priority2_high(runner)
    print(f"P2 High: {len([r for r in runner.results if r['priority'] == 2])} tests")

    run_priority3_medium(runner)
    print(f"P3 Medium: {len([r for r in runner.results if r['priority'] == 3])} tests")

    run_priority4_low(runner)
    print(f"P4 Low: {len([r for r in runner.results if r['priority'] == 4])} tests")

    run_priority5_info(runner)
    print(f"P5 Info: {len([r for r in runner.results if r['priority'] == 5])} tests")

    # Run function benchmarks
    print("\nRunning function benchmarks...")
    run_function_benchmarks(runner)
    print(f"Function: {len([r for r in runner.results if r['category'] == 'function'])} tests")

    report = runner.report()
    print()
    print(report)

    # Save report to .data directory
    root = get_project_root()
    data_dir = root / ".data"
    data_dir.mkdir(exist_ok=True)
    report_path = data_dir / "benchmark_report.txt"
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
