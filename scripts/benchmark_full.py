#!/usr/bin/env python3
"""
Comprehensive Performance Benchmark Suite - Omni DevEnv Fusion

Complete performance profiling for all packages:
- common/ (gitops, config, lib)
- mcp_core/ (protocols, execution, inference, memory, context, utils)
- agent/core/ (registry, skill_manager, orchestrator, router, schema, etc.)
- agent/tools/ (orchestrator, router, status, etc.)
- agent/capabilities/ (knowledge, learning, etc.)

Run with: python scripts/benchmark_full.py

Priority Order:
1. CRITICAL - Core infrastructure (gitops, config, lib)
2. HIGH - MCP Core (execution, inference, memory)
3. MEDIUM - Agent Core (registry, skill_manager, orchestrator)
4. LOW - Agent Tools & Capabilities
5. INFO - Minor utilities
"""

from __future__ import annotations

import asyncio
import gc
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
            "COMPREHENSIVE PERFORMANCE BENCHMARK REPORT",
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

            # Sort by time descending (slowest first)
            items = sorted(items, key=lambda x: x["time_ms"], reverse=True)
            for r in items:
                bar_len = int(r["time_ms"] / 10) if r["time_ms"] > 0 else 1
                bar = "█" * min(bar_len, 50)
                status = "✓" if r["category"] == "function" else "I"
                lines.append(f"{status} {r['time_ms']:>8.1f}ms {bar} {r['description']}")

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
                avg = total / len(items)
                lines.append(
                    f"P{priority} {priority_order[priority]}: "
                    f"{len(items):3d} tests, {total:>10.1f}ms total, "
                    f"avg: {avg:>7.1f}ms, slowest: {slowest:>7.1f}ms"
                )

        # Top bottlenecks
        lines.extend(
            [
                "",
                "-" * 70,
                "TOP BOTTLENECKS (all categories)",
                "-" * 70,
            ]
        )

        top10 = sorted(self.results, key=lambda x: x["time_ms"], reverse=True)[:10]
        for i, r in enumerate(top10, 1):
            cat = r["category"][:8].upper()
            lines.append(
                f"{i:2d}. [{cat}] {r['description']}: {r['time_ms']:>8.1f}ms (P{r['priority']})"
            )

        # Recommendations
        critical_slow = [r for r in self.results if r["priority"] <= 2 and r["time_ms"] > 100]
        lines.extend(
            [
                "",
                "-" * 70,
                "RECOMMENDATIONS - Priority Optimization Targets",
                "-" * 70,
            ]
        )
        if critical_slow:
            for r in sorted(critical_slow, key=lambda x: x["time_ms"], reverse=True):
                lines.append(
                    f"🔴 P{r['priority']} [{r['category'][:8].upper()}] "
                    f"{r['description']}: {r['time_ms']:.1f}ms"
                )
        else:
            lines.append("✅ No critical bottlenecks found (>100ms in P1-P2)")

        # Category breakdown
        lines.extend(
            [
                "",
                "-" * 70,
                "CATEGORY BREAKDOWN",
                "-" * 70,
            ]
        )
        categories = {}
        for r in self.results:
            cat = r["category"]
            if cat not in categories:
                categories[cat] = {"count": 0, "total": 0.0, "slowest": 0.0}
            categories[cat]["count"] += 1
            categories[cat]["total"] += r["time_ms"]
            categories[cat]["slowest"] = max(categories[cat]["slowest"], r["time_ms"])

        for cat in sorted(categories.keys(), key=lambda c: categories[c]["total"], reverse=True):
            d = categories[cat]
            lines.append(
                f"{cat:>12s}: {d['count']:3d} tests, "
                f"total: {d['total']:>10.1f}ms, "
                f"slowest: {d['slowest']:>8.1f}ms"
            )

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
# Priority 1: CRITICAL - Common Package
# =============================================================================


def run_common_critical(runner: BenchmarkRunner) -> None:
    """PRIORITY 1: CRITICAL - Common infrastructure."""

    # gitops
    clear_modules(["common.gitops", "common"])
    with runner.measure("import", "from common.gitops import get_project_root", priority=1):
        from common.gitops import get_project_root

    with runner.measure("function", "get_project_root() - FIRST CALL", priority=1):
        import common.gitops

        common.gitops._project_root = None
        from common.gitops import get_project_root

        get_project_root()

    with runner.measure("function", "get_project_root() - CACHED", priority=2):
        from common.gitops import get_project_root

        get_project_root()

    # config settings
    clear_modules(["common.config", "common"])
    with runner.measure("import", "from common.config.settings import get_setting", priority=1):
        from common.config.settings import get_setting

    with runner.measure("function", "get_setting() first call", priority=1):
        from common.config.settings import get_setting

        get_setting("skills.path")

    with runner.measure("function", "get_setting() cached", priority=2):
        from common.config.settings import get_setting

        get_setting("skills.path")

    # lib utilities
    clear_modules(["common"])
    with runner.measure("import", "from common.lib import agent_src, common_src", priority=1):
        from common.lib import agent_src, common_src

    with runner.measure("function", "agent_src()", priority=2):
        agent_src()

    with runner.measure("function", "common_src()", priority=2):
        common_src()

    # config directory
    clear_modules(["common.config"])
    with runner.measure("import", "from common.config.directory import get_conf_dir", priority=2):
        from common.config.directory import get_conf_dir

    # config commits
    clear_modules(["common.config"])
    with runner.measure("import", "from common.config.commits import get_commit_types", priority=2):
        from common.config.commits import get_commit_types

    with runner.measure("function", "get_commit_types()", priority=2):
        from common.config.commits import get_commit_types

        get_commit_types()


# =============================================================================
# Priority 2: HIGH - MCP Core Package
# =============================================================================


def run_mcp_core_high(runner: BenchmarkRunner) -> None:
    """PRIORITY 2: HIGH - MCP Core modules.

    NOTE: Import directly from submodules to avoid loading common.mcp_core/__init__.py
    which imports everything (inference, memory, etc.) - over 600ms overhead!
    """

    # protocols - this triggers mcp_core/__init__.py (554ms) due to Python import mechanics
    # This is expected: `from common.mcp_core.protocols` loads parent package first
    clear_modules(["common"])
    with runner.measure("import", "from common.mcp_core.protocols import ISettings", priority=2):
        from common.mcp_core.protocols import ISettings

    # execution submodule - REMOVED (legacy code, now handled by skills/terminal)
    # The execution logic has been moved to assets/skills/terminal/tools.py
    # and is no longer part of mcp_core

    # inference - heavy, imports anthropic SDK
    clear_modules(["common", "anthropic"])
    with runner.measure(
        "import", "from common.mcp_core.inference import InferenceClient", priority=2
    ):
        from common.mcp_core.inference import InferenceClient

    # memory - imports sqlite
    clear_modules(["common"])
    with runner.measure("import", "from common.mcp_core.memory import ProjectMemory", priority=2):
        from common.mcp_core.memory import ProjectMemory

    # context - imports context files
    clear_modules(["common"])
    with runner.measure("import", "from common.mcp_core.context import ProjectContext", priority=2):
        from common.mcp_core.context import ProjectContext

    with runner.measure(
        "import", "from common.mcp_core.context.registry import ContextRegistry", priority=2
    ):
        from common.mcp_core.context.registry import ContextRegistry

    # utils - imports logging utilities
    clear_modules(["common"])
    with runner.measure("import", "from common.mcp_core.utils import setup_logging", priority=3):
        from common.mcp_core.utils import setup_logging

    with runner.measure(
        "import", "from common.mcp_core.utils.path_safety import is_safe_path", priority=3
    ):
        from common.mcp_core.utils.path_safety import is_safe_path

    with runner.measure("function", "is_safe_path('/project/file.py')", priority=3):
        from common.mcp_core.utils.path_safety import is_safe_path

        is_safe_path("/project/file.py")

    # api key - imports config
    clear_modules(["common"])
    with runner.measure("import", "from common.mcp_core.api import get_api_key", priority=3):
        from common.mcp_core.api import get_api_key

    # instructions - imports markdown files
    clear_modules(["common"])
    with runner.measure(
        "import", "from common.mcp_core.instructions import get_instructions", priority=3
    ):
        from common.mcp_core.instructions import get_instructions

    # lazy_cache - imports cache base
    clear_modules(["common"])
    with runner.measure("import", "from common.mcp_core.lazy_cache import FileCache", priority=3):
        from common.mcp_core.lazy_cache import FileCache

    with runner.measure("import", "from common.mcp_core.lazy_cache import ConfigCache", priority=3):
        from common.mcp_core.lazy_cache import ConfigCache


# =============================================================================
# Priority 3: MEDIUM - Agent Core
# =============================================================================


def run_agent_core_medium(runner: BenchmarkRunner) -> None:
    """PRIORITY 3: MEDIUM - Agent core modules."""

    # schema (Pydantic models)
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.schema import SkillManifest", priority=3):
        from agent.core.schema import SkillManifest

    with runner.measure("import", "from agent.core.schema import SpecGapAnalysis", priority=3):
        from agent.core.schema import SpecGapAnalysis

    # registry
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.registry import get_skill_registry", priority=3):
        from agent.core.registry import get_skill_registry

    with runner.measure("function", "get_skill_registry()", priority=3):
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()

    with runner.measure("function", "list_available_skills()", priority=3):
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        registry.list_available_skills()

    with runner.measure("function", "list_loaded_skills()", priority=4):
        from agent.core.registry import get_skill_registry

        registry = get_skill_registry()
        registry.list_loaded_skills()

    # skill manager
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.skill_manager import SkillManager", priority=3):
        from agent.core.skill_manager import SkillManager

    with runner.measure("function", "SkillManager() instantiation", priority=3):
        from agent.core.skill_manager import SkillManager

        manager = SkillManager()

    with runner.measure("function", "SkillManager.discover()", priority=3):
        from agent.core.skill_manager import SkillManager

        manager = SkillManager()
        manager.discover()

    with runner.measure("function", "SkillManager.list_available()", priority=4):
        from agent.core.skill_manager import SkillManager

        manager = SkillManager()
        manager.list_available()

    # loader
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.loader import SkillLoader", priority=3):
        from agent.core.loader import SkillLoader

    # module_loader
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.module_loader import ModuleLoader", priority=3):
        from agent.core.module_loader import ModuleLoader

    # context_loader
    clear_modules(["agent"])
    with runner.measure(
        "import", "from agent.core.context_loader import ContextLoader", priority=3
    ):
        from agent.core.context_loader import ContextLoader

    # orchestrator
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.orchestrator import Orchestrator", priority=3):
        from agent.core.orchestrator import Orchestrator


# =============================================================================
# Priority 4: LOW - Router & Core Components
# =============================================================================


def run_router_low(runner: BenchmarkRunner) -> None:
    """PRIORITY 4: LOW - Router and core components."""

    # semantic router
    clear_modules(["agent"])
    with runner.measure(
        "import", "from agent.core.router.semantic_router import SemanticRouter", priority=4
    ):
        from agent.core.router.semantic_router import SemanticRouter

    with runner.measure("function", "SemanticRouter() instantiation", priority=4):
        from agent.core.router.semantic_router import SemanticRouter

        router = SemanticRouter()

    with runner.measure("function", "router._build_routing_menu()", priority=4):
        from agent.core.router.semantic_router import SemanticRouter

        router = SemanticRouter()
        router._build_routing_menu()

    # router main
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.router.main import get_router", priority=4):
        from agent.core.router.main import get_router

    # hive mind cache
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.router.cache import HiveMindCache", priority=4):
        from agent.core.router.cache import HiveMindCache

    # vector store
    clear_modules(["agent"])
    with runner.measure(
        "import", "from agent.core.vector_store import get_vector_memory", priority=4
    ):
        from agent.core.vector_store import get_vector_memory

    with runner.measure("function", "get_vector_memory()", priority=4):
        from agent.core.vector_store import get_vector_memory

        vm = get_vector_memory()

    # session
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.session import SessionManager", priority=4):
        from agent.core.session import SessionManager

    # security
    clear_modules(["agent"])
    with runner.measure(
        "import", "from agent.core.security.immune_system import ImmuneSystem", priority=4
    ):
        from agent.core.security.immune_system import ImmuneSystem

    # ux
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.ux import UXManager", priority=4):
        from agent.core.ux import UXManager

    # bootstrap
    clear_modules(["agent"])
    with runner.measure("import", "from agent.core.bootstrap import boot_core_skills", priority=4):
        from agent.core.bootstrap import boot_core_skills


# =============================================================================
# Priority 5: INFO - Tools & Capabilities
# =============================================================================


def run_tools_info(runner: BenchmarkRunner) -> None:
    """PRIORITY 5: INFO - Agent tools and capabilities."""

    # capabilities knowledge
    clear_modules(["agent"])
    with runner.measure(
        "import", "from agent.capabilities.knowledge import ingest_knowledge", priority=5
    ):
        from agent.capabilities.knowledge import ingest_knowledge

    with runner.measure(
        "import", "from agent.capabilities.knowledge.librarian import search_knowledge", priority=5
    ):
        from agent.capabilities.knowledge.librarian import search_knowledge

    # capabilities learning - import functions instead of class
    clear_modules(["agent"])
    with runner.measure(
        "import",
        "from agent.capabilities.learning import harvest_session_insight",
        priority=5,
    ):
        from agent.capabilities.learning import harvest_session_insight

    # capabilities product_owner - import existing exports
    clear_modules(["agent"])
    with runner.measure(
        "import",
        "from agent.capabilities.product_owner import heuristic_complexity",
        priority=5,
    ):
        from agent.capabilities.product_owner import heuristic_complexity


# =============================================================================
# Main
# =============================================================================


def main():
    """Run all benchmarks and output report."""
    setup_import_path()

    runner = BenchmarkRunner("Omni-DevEnv Full Performance")

    print("Running comprehensive benchmarks...")
    print()

    # Run in priority order
    print("P1: Common (CRITICAL)...")
    run_common_critical(runner)
    print(f"  Completed: {len([r for r in runner.results if r['priority'] == 1])} tests")

    print("P2: MCP Core (HIGH)...")
    run_mcp_core_high(runner)
    print(f"  Completed: {len([r for r in runner.results if r['priority'] == 2])} tests")

    print("P3: Agent Core (MEDIUM)...")
    run_agent_core_medium(runner)
    print(f"  Completed: {len([r for r in runner.results if r['priority'] == 3])} tests")

    print("P4: Router & Components (LOW)...")
    run_router_low(runner)
    print(f"  Completed: {len([r for r in runner.results if r['priority'] == 4])} tests")

    print("P5: Tools & Capabilities (INFO)...")
    run_tools_info(runner)
    print(f"  Completed: {len([r for r in runner.results if r['priority'] == 5])} tests")

    report = runner.report()
    print()
    print(report)

    # Save report to .data directory
    root = get_project_root()
    data_dir = root / ".data"
    data_dir.mkdir(exist_ok=True)
    report_path = data_dir / "benchmark_full_report.txt"
    report_path.write_text(report)
    print(f"\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
