"""
Stress Test Framework Core

System Architecture:
┌─────────────────────────────────────────────────────────────────┐
│                     Stress Test Framework                        │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Config    │  │   Runner    │  │       Reporter          │  │
│  │  (params)   │  │  (execute)  │  │      (output)           │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│         │              │                     │                   │
│         └──────────────┼─────────────────────┘                   │
│                        ▼                                        │
│              ┌─────────────────────┐                            │
│              │     Fixtures        │                            │
│              │  (pytest hooks)     │                            │
│              └─────────────────────┘                            │
│                        │                                        │
│         ┌──────────────┼──────────────┐                         │
│         ▼              ▼              ▼                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                   │
│  │ Phase 9   │  │ Phase 10  │  │ Phase 11  │                   │
│  │  Suite    │  │  Suite    │  │  Suite    │                   │
│  └───────────┘  └───────────┘  └───────────┘                   │
└─────────────────────────────────────────────────────────────────┘
"""
import time
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from pathlib import Path
import subprocess
import json


# =============================================================================
# Configuration System
# =============================================================================

@dataclass
class StressConfig:
    """Stress test configuration."""
    # File generation
    noise_files: int = 900
    target_files: int = 100
    stress_dir: Path = Path("tests/stress_data")

    # Performance thresholds
    max_search_time: float = 2.0  # seconds
    min_files_per_second: float = 1000.0

    # Test behavior
    cleanup_after: bool = True
    verbose: bool = True


# Global default config
_default_config = StressConfig()


def get_config() -> StressConfig:
    """Get current configuration."""
    return _default_config


def set_config(config: StressConfig) -> None:
    """Set global configuration."""
    global _default_config
    _default_config = config


# =============================================================================
# Result System
# =============================================================================

@dataclass
class BenchmarkResult:
    """Result from a benchmark test."""
    name: str
    duration: float
    success: bool
    metrics: dict = field(default_factory=dict)
    message: str = ""

    @property
    def files_per_second(self) -> float:
        return self.metrics.get("files_processed", 0) / self.duration if self.duration > 0 else 0


@dataclass
class LogicResult:
    """Result from a logic depth test."""
    name: str
    pattern: str
    matches_found: int
    expected_matches: Optional[int]
    success: bool
    details: str = ""


@dataclass
class StabilityResult:
    """Result from a stability/chaos test."""
    name: str
    case_name: str
    passed: bool
    error: Optional[str] = None
    details: str = ""


@dataclass
class StressSuiteResult:
    """Aggregated result for a test suite."""
    phase: str
    benchmarks: list = field(default_factory=list)
    logic_tests: list = field(default_factory=list)
    stability_tests: list = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return (
            all(b.success for b in self.benchmarks) and
            all(l.success for l in self.logic_tests) and
            all(s.passed for s in self.stability_tests)
        )

    @property
    def total_duration(self) -> float:
        return sum(b.duration for b in self.benchmarks)


# =============================================================================
# Runner System
# =============================================================================

class BenchmarkRunner:
    """Run benchmark tests."""

    def __init__(self, config: Optional[StressConfig] = None):
        self.config = config or get_config()

    def run(self, name: str, pattern: str, lang: str, path: Path) -> BenchmarkResult:
        """Execute ast-grep benchmark."""
        start = time.time()
        try:
            result = subprocess.run(
                ["ast-grep", "run", "--pattern", pattern, "--lang", lang, str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            duration = time.time() - start
            output_lines = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0

            return BenchmarkResult(
                name=name,
                duration=duration,
                success=True,
                metrics={"files_processed": output_lines},
                message=f"Completed in {duration:.4f}s"
            )
        except Exception as e:
            return BenchmarkResult(
                name=name,
                duration=time.time() - start,
                success=False,
                message=str(e)
            )


class LogicTestRunner:
    """Run logic depth tests."""

    def __init__(self, config: Optional[StressConfig] = None):
        self.config = config or get_config()

    def run(self, name: str, pattern: str, lang: str, path: Path,
            expected_matches: Optional[int] = None) -> LogicResult:
        """Execute pattern matching test."""
        start = time.time()
        try:
            result = subprocess.run(
                ["ast-grep", "run", "--pattern", pattern, "--lang", lang, str(path)],
                capture_output=True,
                text=True,
                timeout=30
            )
            duration = time.time() - start

            # Count matches
            output = result.stdout
            match_count = len([l for l in output.split("\n") if ":" in l and "target_" in l])

            success = expected_matches is None or match_count >= expected_matches

            return LogicResult(
                name=name,
                pattern=pattern,
                matches_found=match_count,
                expected_matches=expected_matches,
                success=success,
                details=f"Found {match_count} matches in {duration:.4f}s"
            )
        except Exception as e:
            return LogicResult(
                name=name,
                pattern=pattern,
                matches_found=0,
                expected_matches=expected_matches,
                success=False,
                details=str(e)
            )


class StabilityTestRunner:
    """Run stability/chaos tests."""

    def __init__(self, config: Optional[StressConfig] = None):
        self.config = config or get_config()

    def run(self, name: str, case_name: str, test_func: Callable[[], bool],
            details: str = "") -> StabilityResult:
        """Execute stability test case."""
        try:
            passed = test_func()
            return StabilityResult(
                name=name,
                case_name=case_name,
                passed=passed,
                details=details or ("Passed" if passed else "Failed")
            )
        except Exception as e:
            return StabilityResult(
                name=name,
                case_name=case_name,
                passed=False,
                error=str(e)
            )


# =============================================================================
# Reporter System
# =============================================================================

class StressReporter:
    """Generate stress test reports."""

    def __init__(self, phase: str):
        self.phase = phase

    def report_benchmark(self, result: BenchmarkResult, expected_threshold: float = 2.0) -> str:
        """Format benchmark result."""
        status = "✅" if result.success else "❌"
        perf = ""
        if result.success:
            if result.duration > expected_threshold:
                perf = f"  ⚠️  WARNING: >{expected_threshold}s - Consider optimizing"
            else:
                perf = f"  ✅ Performance: Excellent (<{expected_threshold}s)"
        return f"{status} {result.name}: {result.message}\n{perf}"

    def report_logic(self, result: LogicResult) -> str:
        """Format logic test result."""
        if result.success:
            return f"✅ {result.name}: {result.details}"
        else:
            return f"❌ {result.name}: Found {result.matches_found}/expected {result.expected_matches}"

    def report_stability(self, result: StabilityResult) -> str:
        """Format stability test result."""
        status = "✅" if result.passed else "❌"
        return f"{status} {result.case_name}: {result.details or result.error}"

    def report_suite(self, result: StressSuiteResult) -> str:
        """Format full suite report."""
        lines = [
            f"{'=' * 60}",
            f"Phase {result.phase} Stress Test Report",
            f"{'=' * 60}",
            f"Total Duration: {result.total_duration:.4f}s",
            "",
            "--- Benchmarks ---",
        ]

        for b in result.benchmarks:
            lines.append(self.report_benchmark(b))

        lines.extend(["", "--- Logic Tests ---"])
        for l in result.logic_tests:
            lines.append(self.report_logic(l))

        lines.extend(["", "--- Stability Tests ---"])
        for s in result.stability_tests:
            lines.append(self.report_stability(s))

        lines.extend([
            "",
            f"{'=' * 60}",
            f"Overall: {'✅ ALL PASSED' if result.all_passed else '❌ SOME FAILED'}",
            f"{'=' * 60}",
        ])

        return "\n".join(lines)
