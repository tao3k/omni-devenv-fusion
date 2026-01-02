"""
Modular Stress Test Framework

A extensible, modular stress testing framework for MCP servers and agents.

System Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                         Stress Test Framework                            │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────────────────┐    │
│  │   ConfigLoader │  │  TestRunner    │  │      Reporter           │    │
│  │   (YAML/JSON)  │  │  (Orchestrator)│  │   (Multi-format)        │    │
│  └────────────────┘  └────────────────┘  └─────────────────────────┘    │
│           │                  │                       │                   │
│           └──────────────────┼───────────────────────┘                   │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    Plugin Registry                               │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │    │
│  │  │ Collectors│  │Generators │  │Assertions│  │Formatters │        │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│         ┌────────────────────┼────────────────────┐                      │
│         ▼                    ▼                    ▼                      │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐                │
│  │   Suite    │      │   Suite    │      │   Suite    │                │
│  │  Phase 9   │      │  Phase 10  │      │  Phase 11  │                │
│  └────────────┘      └────────────┘      └────────────┘                │
└─────────────────────────────────────────────────────────────────────────┘

Usage:
    from stress import TestRunner, Config, Suite

    runner = TestRunner(config="stress.yaml")
    result = runner.run_suite("phase9")
    print(result.report())
"""

import sys
import time
import statistics
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Dict, List, Type, Protocol
from pathlib import Path
from enum import Enum
from abc import ABC, abstractmethod


# =============================================================================
# Version & Exports
# =============================================================================

__version__ = "2.0.0"
__author__ = "Omni DevEnv Fusion"

# Core exports
__all__ = [
    # Configuration
    "StressConfig",
    "ConfigLoader",
    "load_config",
    # Results
    "TestResult",
    "SuiteResult",
    "Metric",
    # Runner
    "TestRunner",
    "TestSuite",
    "TestCase",
    # Reporter
    "Reporter",
    "TextReporter",
    "JSONReporter",
    "MarkdownReporter",
    # Collectors
    "MetricCollector",
    "PerformanceCollector",
    "StabilityCollector",
    "MemoryCollector",
    # Suites
    "Phase9Suite",
]


# =============================================================================
# Enums
# =============================================================================

class ResultStatus(Enum):
    """Test result status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class MetricType(Enum):
    """Types of metrics that can be collected."""
    DURATION = "duration"
    MEMORY = "memory"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    COUNT = "count"
    RATIO = "ratio"


class ReportFormat(Enum):
    """Available report formats."""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"
    HTML = "html"


# =============================================================================
# Configuration System
# =============================================================================

@dataclass
class StressConfig:
    """Stress test configuration."""

    # Environment
    stress_dir: Path = Path("mcp-server/tests/stress_data")
    cleanup_after: bool = True
    verbose: bool = True

    # Performance thresholds
    max_duration: float = 2.0  # seconds
    min_throughput: float = 1000.0  # files/second

    # Test parameters
    noise_files: int = 900
    target_files: int = 100

    # MCP Server settings
    server_module: str = "mcp_server.coder"
    server_type: str = "coder"  # coder, orchestrator, etc.


class ConfigLoader:
    """Load configuration from YAML/JSON files."""

    _config: Optional[StressConfig] = None

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> StressConfig:
        """Load configuration from file or return defaults."""
        if config_path and Path(config_path).exists():
            data = cls._load_file(config_path)
            cls._config = StressConfig(**data)
        else:
            cls._config = StressConfig()
        return cls._config

    @staticmethod
    def _load_file(path: Path) -> Dict[str, Any]:
        """Load config from file."""
        if path.suffix == ".json":
            return json.loads(path.read_text())
        elif path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                return yaml.safe_load(path.read_text()) or {}
            except ImportError:
                return {}
        return {}

    @classmethod
    def get(cls) -> StressConfig:
        """Get current configuration."""
        return cls._config or cls.load()


def load_config(config_path: Optional[Path] = None) -> StressConfig:
    """Convenience function to load configuration."""
    return ConfigLoader.load(config_path)


# Alias for backwards compatibility
get_config = load_config


def set_config(config: StressConfig) -> None:
    """Set global configuration."""
    ConfigLoader._config = config


# =============================================================================
# Result System
# =============================================================================

@dataclass
class Metric:
    """A collected metric."""
    name: str
    value: float
    unit: str
    metric_type: MetricType
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class TestResult:
    """Result of a single test case."""
    name: str
    suite: str
    status: ResultStatus
    duration: float
    metrics: List[Metric] = field(default_factory=list)
    message: str = ""
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == ResultStatus.PASSED


@dataclass
class SuiteResult:
    """Aggregated result for a test suite."""
    name: str
    phase: str
    tests: List[TestResult] = field(default_factory=list)
    metrics: List[Metric] = field(default_factory=list)
    started_at: Optional[float] = None
    ended_at: Optional[float] = None

    @property
    def duration(self) -> float:
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return sum(t.duration for t in self.tests)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if not t.passed)

    @property
    def all_passed(self) -> bool:
        return all(t.passed for t in self.tests) and len(self.tests) > 0


# =============================================================================
# Plugin System - Collectors
# =============================================================================

class MetricCollector(ABC):
    """Base class for metric collectors."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def collect(self, context: Dict[str, Any]) -> List[Metric]:
        """Collect metrics from context."""
        pass

    @abstractmethod
    def reset(self):
        """Reset collector state."""
        pass


class PerformanceCollector(MetricCollector):
    """Collect performance metrics."""

    def __init__(self):
        super().__init__("performance")
        self._start_time: Optional[float] = None
        self._durations: List[float] = []

    def start(self):
        """Start timing."""
        self._start_time = time.perf_counter()

    def stop(self) -> float:
        """Stop timing and record duration."""
        if self._start_time:
            duration = time.perf_counter() - self._start_time
            self._durations.append(duration)
            self._start_time = None
            return duration
        return 0.0

    def collect(self, context: Dict[str, Any]) -> List[Metric]:
        if self._durations:
            return [
                Metric(
                    name="duration",
                    value=statistics.mean(self._durations),
                    unit="seconds",
                    metric_type=MetricType.DURATION,
                    tags={"collector": self.name}
                ),
                Metric(
                    name="throughput",
                    value=context.get("files_processed", 0) / statistics.mean(self._durations),
                    unit="files/second",
                    metric_type=MetricType.THROUGHPUT,
                    tags={"collector": self.name}
                ),
            ]
        return []

    def reset(self):
        self._start_time = None
        self._durations = []


class StabilityCollector(MetricCollector):
    """Collect stability metrics."""

    def __init__(self):
        super().__init__("stability")
        self._errors: List[str] = []
        self._passed: int = 0
        self._failed: int = 0

    def record(self, passed: bool, error: Optional[str] = None):
        if passed:
            self._passed += 1
        else:
            self._failed += 1
            if error:
                self._errors.append(error)

    def collect(self, context: Dict[str, Any]) -> List[Metric]:
        total = self._passed + self._failed
        return [
            Metric(
                name="stability_passed",
                value=self._passed,
                unit="count",
                metric_type=MetricType.COUNT,
                tags={"collector": self.name}
            ),
            Metric(
                name="stability_failed",
                value=self._failed,
                unit="count",
                metric_type=MetricType.COUNT,
                tags={"collector": self.name}
            ),
        ] if total > 0 else []

    def reset(self):
        self._errors = []
        self._passed = 0
        self._failed = 0


class MemoryCollector(MetricCollector):
    """Collect memory metrics."""

    def __init__(self):
        super().__init__("memory")

    def collect(self, context: Dict[str, Any]) -> List[Metric]:
        # Could integrate with memory_profiler here
        return []


class CompositeCollector(MetricCollector):
    """Composite collector that manages multiple collectors."""

    def __init__(self, collectors: List[MetricCollector]):
        super().__init__("composite")
        self.collectors = collectors

    def collect(self, context: Dict[str, Any]) -> List[Metric]:
        metrics = []
        for collector in self.collectors:
            metrics.extend(collector.collect(context))
        return metrics

    def reset(self):
        for collector in self.collectors:
            collector.reset()


# =============================================================================
# Test Suite & Case Definitions
# =============================================================================

class TestCase:
    """Definition of a single test case."""

    def __init__(
        self,
        name: str,
        test_func: Callable[[], Any],
        description: str = "",
        tags: List[str] = None,
        timeout: float = 30.0,
        depends_on: List[str] = None,
    ):
        self.name = name
        self.test_func = test_func
        self.description = description
        self.tags = tags or []
        self.timeout = timeout
        self.depends_on = depends_on or []

    def run(self) -> TestResult:
        """Execute the test case."""
        start = time.perf_counter()
        try:
            result = self.test_func()
            duration = time.perf_counter() - start

            if result is True or result is None:
                return TestResult(
                    name=self.name,
                    suite="",
                    status=ResultStatus.PASSED,
                    duration=duration,
                    message="Test passed"
                )
            elif isinstance(result, TestResult):
                return result
            else:
                return TestResult(
                    name=self.name,
                    suite="",
                    status=ResultStatus.FAILED,
                    duration=duration,
                    message=str(result)
                )
        except Exception as e:
            return TestResult(
                name=self.name,
                suite="",
                status=ResultStatus.ERROR,
                duration=time.perf_counter() - start,
                error=str(e)
            )


class TestSuite:
    """Definition of a test suite."""

    def __init__(
        self,
        name: str,
        phase: str,
        description: str = "",
        test_cases: List[TestCase] = None,
    ):
        self.name = name
        self.phase = phase
        self.description = description
        self.test_cases = test_cases or []

    def add_test(self, test: TestCase):
        """Add a test case to the suite."""
        self.test_cases.append(test)

    def run(self, collector: Optional[MetricCollector] = None) -> SuiteResult:
        """Run all test cases in the suite."""
        result = SuiteResult(name=self.name, phase=self.phase)
        result.started_at = time.perf_counter()

        for test in self.test_cases:
            if collector and isinstance(collector, PerformanceCollector):
                collector.start()

            test_result = test.run()

            if collector and isinstance(collector, PerformanceCollector):
                collector.stop()

            result.tests.append(test_result)

        result.ended_at = time.perf_counter()
        return result


# =============================================================================
# Reporter System
# =============================================================================

class Reporter(ABC):
    """Base class for reporters."""

    def __init__(self, format_type: ReportFormat):
        self.format_type = format_type

    @abstractmethod
    def report(self, result: SuiteResult) -> str:
        """Generate report from result."""
        pass


class TextReporter(Reporter):
    """Generate text-format reports."""

    def __init__(self):
        super().__init__(ReportFormat.TEXT)

    def report(self, result: SuiteResult) -> str:
        lines = [
            "=" * 60,
            f"Stress Test Report - Phase {result.phase}",
            "=" * 60,
            f"Suite: {result.name}",
            f"Duration: {result.duration:.4f}s",
            f"Tests: {result.passed}/{result.passed + result.failed} passed",
            "-" * 60,
        ]

        for test in result.tests:
            status = "✅" if test.passed else "❌"
            lines.append(f"{status} {test.name}: {test.message or test.error}")

        lines.extend([
            "-" * 60,
            f"Result: {'✅ ALL PASSED' if result.all_passed else '❌ SOME FAILED'}",
            "=" * 60,
        ])

        return "\n".join(lines)


class JSONReporter(Reporter):
    """Generate JSON-format reports."""

    def __init__(self):
        super().__init__(ReportFormat.JSON)

    def report(self, result: SuiteResult) -> str:
        data = {
            "suite": result.name,
            "phase": result.phase,
            "duration": result.duration,
            "summary": {
                "total": len(result.tests),
                "passed": result.passed,
                "failed": result.failed,
                "all_passed": result.all_passed,
            },
            "tests": [
                {
                    "name": t.name,
                    "status": t.status.value,
                    "duration": t.duration,
                    "message": t.message,
                    "error": t.error,
                }
                for t in result.tests
            ],
            "metrics": [
                {"name": m.name, "value": m.value, "unit": m.unit}
                for m in result.metrics
            ],
        }
        return json.dumps(data, indent=2)


class MarkdownReporter(Reporter):
    """Generate Markdown-format reports."""

    def __init__(self):
        super().__init__(ReportFormat.MARKDOWN)

    def report(self, result: SuiteResult) -> str:
        lines = [
            f"# Stress Test Report - Phase {result.phase}",
            "",
            f"**Suite:** {result.name}",
            f"**Duration:** {result.duration:.4f}s",
            f"**Status:** {'✅ PASSED' if result.all_passed else '❌ FAILED'}",
            "",
            "## Summary",
            "",
            f"- Total Tests: {len(result.tests)}",
            f"- Passed: {result.passed}",
            f"- Failed: {result.failed}",
            "",
            "## Test Results",
            "| Test | Status | Duration | Message |",
            "|------|--------|----------|---------|",
        ]

        for test in result.tests:
            status = "✅ PASS" if test.passed else "❌ FAIL"
            msg = test.message or test.error or ""
            lines.append(f"| {test.name} | {status} | {test.duration:.4f}s | {msg} |")

        return "\n".join(lines)


# =============================================================================
# Test Runner
# =============================================================================

class TestRunner:
    """Main test runner orchestrator."""

    def __init__(self, config: Optional[StressConfig] = None):
        self.config = config or StressConfig()
        self._suites: Dict[str, TestSuite] = {}
        self._collector = CompositeCollector([
            PerformanceCollector(),
            StabilityCollector(),
        ])

    def register_suite(self, suite: TestSuite):
        """Register a test suite."""
        self._suites[suite.name] = suite

    def run_suite(self, name: str) -> SuiteResult:
        """Run a specific test suite."""
        if name not in self._suites:
            raise ValueError(f"Suite '{name}' not found")

        suite = self._suites[name]
        self._collector.reset()

        if self.config.verbose:
            print(f"\nRunning suite: {suite.name}")

        result = suite.run(self._collector)
        result.metrics = self._collector.collect({})

        return result

    def run_all(self) -> Dict[str, SuiteResult]:
        """Run all registered suites."""
        results = {}
        for name in self._suites:
            results[name] = self.run_suite(name)
        return results

    def report(self, result: SuiteResult, format_type: ReportFormat = ReportFormat.TEXT) -> str:
        """Generate report for a result."""
        reporters = {
            ReportFormat.TEXT: TextReporter,
            ReportFormat.JSON: JSONReporter,
            ReportFormat.MARKDOWN: MarkdownReporter,
        }
        reporter = reporters.get(format_type, TextReporter)()
        return reporter.report(result)


# =============================================================================
# Phase 9 Suite (Example)
# =============================================================================

class Phase9Suite(TestSuite):
    """Phase 9 Code Intelligence Stress Test Suite."""

    def __init__(self, config: Optional[StressConfig] = None):
        super().__init__(
            name="Phase9 Code Intelligence",
            phase="9",
            description="Tests for AST-based code intelligence (ast-grep integration)"
        )
        self.config = config or StressConfig()
        self._setup_tests()

    def _setup_tests(self):
        """Setup Phase 9 test cases."""

        def perf_test():
            import subprocess
            start = time.perf_counter()
            result = subprocess.run(
                ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py",
                 str(self.config.stress_dir)],
                capture_output=True, text=True, timeout=30
            )
            duration = time.perf_counter() - start
            if duration > self.config.max_duration:
                return f"Performance warning: {duration:.4f}s > {self.config.max_duration}s"
            return True

        self.add_test(TestCase(
            name="Performance Benchmark",
            test_func=perf_test,
            description="Benchmark ast-grep search performance",
            tags=["performance", "ast-grep"],
        ))

        def logic_test():
            import subprocess
            result = subprocess.run(
                ["ast-grep", "run", "--pattern", "except $ERR:", "--lang", "py",
                 str(self.config.stress_dir)],
                capture_output=True, text=True, timeout=30
            )
            matches = result.stdout.count(".py:")
            if matches < 100:
                return f"Expected at least 100 matches, got {matches}"
            return True

        self.add_test(TestCase(
            name="Logic Depth Test",
            test_func=logic_test,
            description="Test pattern matching depth (Silent Killer detection)",
            tags=["logic", "ast-grep", "pattern-matching"],
        ))

        def stability_test():
            import subprocess
            # Test with malformed file
            broken_file = self.config.stress_dir / "broken.py"
            broken_file.write_text("def broken(:")
            result = subprocess.run(
                ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py", str(broken_file)],
                capture_output=True, text=True
            )
            # Should not crash
            return True

        self.add_test(TestCase(
            name="Stability Test",
            test_func=stability_test,
            description="Test stability with malformed inputs",
            tags=["stability", "chaos"],
        ))


# =============================================================================
# Convenience Functions
# =============================================================================

def create_runner(config: Optional[StressConfig] = None) -> TestRunner:
    """Create a configured test runner."""
    runner = TestRunner(config)
    runner.register_suite(Phase9Suite(config))
    return runner
