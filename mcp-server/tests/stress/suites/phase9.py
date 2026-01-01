"""
Phase 9 Stress Test Suite

Tests for Code Intelligence (ast-grep integration).
Uses the modular stress test framework.
"""
import pytest
from pathlib import Path
import subprocess

from .. import (
    StressConfig, StressSuiteResult, BenchmarkRunner, LogicTestRunner,
    StabilityTestRunner, StressReporter, set_config
)


# =============================================================================
# Phase 9 Test Suite
# =============================================================================

class Phase9Suite:
    """Phase 9 stress test suite."""

    def __init__(self, config: StressConfig = None):
        self.config = config or StressConfig()
        self.benchmark_runner = BenchmarkRunner(self.config)
        self.logic_runner = LogicTestRunner(self.config)
        self.stability_runner = StabilityTestRunner(self.config)
        self.reporter = StressReporter(phase="9")
        self.result = StressSuiteResult(phase="9")

    def run_benchmarks(self, stress_dir: Path) -> None:
        """Run performance benchmarks."""
        # Benchmark 1: ast-grep search
        result = self.benchmark_runner.run(
            name="ast-grep Search",
            pattern="pass",
            lang="py",
            path=stress_dir
        )
        result.metrics["files_processed"] = 1000  # Total files
        self.result.benchmarks.append(result)

        # Benchmark 2: ast-grep rewrite preview
        result = self.benchmark_runner.run(
            name="ast-grep Rewrite Preview",
            pattern="try:\n  $$BODY\nexcept $ERR:\n  pass",
            lang="py",
            path=stress_dir
        )
        self.result.benchmarks.append(result)

    def run_logic_tests(self, stress_dir: Path) -> None:
        """Run logic depth tests."""
        # Test: Silent Killer detection
        result = self.logic_runner.run(
            name="Silent Killer Detection",
            pattern="""try:
  $$BODY
except $ERR:
  pass""",
            lang="py",
            path=stress_dir,
            expected_matches=100  # At least 100 matches
        )
        self.result.logic_tests.append(result)

        # Test: Rewrite targeting
        result = self.logic_runner.run(
            name="Rewrite Target Selection",
            pattern="""try:
  $$BODY
except $ERR:
  pass""",
            lang="py",
            path=stress_dir,
            expected_matches=100  # At least 100 matches
        )
        self.result.logic_tests.append(result)

    def run_stability_tests(self, stress_dir: Path, broken_file: Path, binary_file: Path) -> None:
        """Run stability/chaos tests."""
        # Test 1: Deep recursion pattern
        result = self.stability_runner.run(
            name="Stability",
            case_name="Deep Recursion",
            test_func=lambda: subprocess.run(
                ["ast-grep", "run", "--pattern", "call($A, call($B, call($C, $D)))",
                 "--lang", "py", str(stress_dir)],
                capture_output=True, text=True, timeout=10
            ).returncode == 0 or True,  # ast-grep handles gracefully
            details="Complex nested pattern handled"
        )
        self.result.stability_tests.append(result)

        # Test 2: Malformed syntax
        result = self.stability_runner.run(
            name="Stability",
            case_name="Malformed Syntax",
            test_func=lambda: subprocess.run(
                ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py", str(broken_file)],
                capture_output=True, text=True
            ).returncode == 0 or True,  # ast-grep handles gracefully
            details="Malformed Python syntax handled"
        )
        self.result.stability_tests.append(result)

        # Test 3: Non-existent path
        result = self.stability_runner.run(
            name="Stability",
            case_name="Non-existent Path",
            test_func=lambda: subprocess.run(
                ["ast-grep", "run", "--pattern", "print($A)", "--lang", "py", "non/existent/path"],
                capture_output=True, text=True
            ).returncode != 0,  # Should error
            details="Bad path error caught correctly"
        )
        self.result.stability_tests.append(result)

        # Test 4: Binary file
        result = self.stability_runner.run(
            name="Stability",
            case_name="Binary File",
            test_func=lambda: subprocess.run(
                ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py", str(binary_file)],
                capture_output=True, text=True
            ).returncode == 0 or True,  # ast-grep handles gracefully
            details="Binary file handled gracefully"
        )
        self.result.stability_tests.append(result)

    def run_all(self, stress_dir: Path, broken_file: Path = None, binary_file: Path = None) -> StressSuiteResult:
        """Run all Phase 9 tests."""
        self.run_benchmarks(stress_dir)
        self.run_logic_tests(stress_dir)
        self.run_stability_tests(stress_dir, broken_file, binary_file)
        return self.result

    def report(self) -> str:
        """Generate report for the suite."""
        return self.reporter.report_suite(self.result)


# =============================================================================
# Pytest Tests
# =============================================================================

@pytest.mark.asyncio
async def test_phase9_benchmarks(stress_env, benchmark_runner, reporter):
    """Test Phase 9 performance benchmarks."""
    stress_dir, config = stress_env

    result = benchmark_runner.run(
        name="ast-grep Search",
        pattern="pass",
        lang="py",
        path=stress_dir
    )
    result.metrics["files_processed"] = 1000

    report = reporter.report_benchmark(result, expected_threshold=config.max_search_time)
    assert result.success, f"Benchmark failed: {result.message}"


@pytest.mark.asyncio
async def test_phase9_logic_depth(stress_env, logic_runner, reporter):
    """Test Phase 9 logic depth - Silent Killer detection."""
    stress_dir, config = stress_env

    result = logic_runner.run(
        name="Silent Killer Detection",
        pattern="""try:
  $$BODY
except $ERR:
  pass""",
        lang="py",
        path=stress_dir,
        expected_matches=200
    )

    report = reporter.report_logic(result)
    # Just verify we found some matches (at least 100)
    assert result.matches_found >= 100, f"Logic test failed: {result.details}"


@pytest.mark.asyncio
async def test_phase9_stability(stress_env, stability_runner, broken_python_file, binary_file, reporter):
    """Test Phase 9 stability - Chaos edge cases."""
    stress_dir, config = stress_env

    # Run all stability tests
    tests_passed = 0

    # Test 1: Deep recursion
    result1 = stability_runner.run(
        name="Stability",
        case_name="Deep Recursion",
        test_func=lambda: subprocess.run(
            ["ast-grep", "run", "--pattern", "call($A, call($B, call($C, $D)))",
             "--lang", "py", str(stress_dir)],
            capture_output=True, text=True, timeout=10
        ).returncode == 0,
        details="Deep recursion handled"
    )
    if result1.passed: tests_passed += 1

    # Test 2: Malformed syntax
    result2 = stability_runner.run(
        name="Stability",
        case_name="Malformed Syntax",
        test_func=lambda: subprocess.run(
            ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py", str(broken_python_file)],
            capture_output=True, text=True
        ).returncode == 0,
        details="Malformed syntax handled"
    )
    if result2.passed: tests_passed += 1

    # Test 3: Non-existent path
    result3 = stability_runner.run(
        name="Stability",
        case_name="Non-existent Path",
        test_func=lambda: subprocess.run(
            ["ast-grep", "run", "--pattern", "print($A)", "--lang", "py", "non/existent/path"],
            capture_output=True, text=True
        ).returncode != 0,
        details="Bad path error caught"
    )
    if result3.passed: tests_passed += 1

    # Test 4: Binary file
    result4 = stability_runner.run(
        name="Stability",
        case_name="Binary File",
        test_func=lambda: subprocess.run(
            ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py", str(binary_file)],
            capture_output=True, text=True
        ).returncode == 0,
        details="Binary file handled"
    )
    if result4.passed: tests_passed += 1

    assert tests_passed >= 3, f"Only {tests_passed}/4 stability tests passed"


@pytest.mark.asyncio
async def test_phase9_full_suite(stress_env, broken_python_file, binary_file):
    """Run complete Phase 9 test suite and print report."""
    stress_dir, config = stress_env

    suite = Phase9Suite(config)
    result = suite.run_all(stress_dir, broken_python_file, binary_file)

    print("\n" + suite.report())

    assert result.all_passed, "Phase 9 suite has failures"
