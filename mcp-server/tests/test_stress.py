"""
Modular Stress Test Framework - Main Entry Point

Runs all registered stress test suites:
- Phase 9: Code Intelligence (ast-grep integration)
- Phase 10: Hive Architecture (microservices) - COMPLETED
- Phase 11: ...

Phase 10 includes:
- Auto-healing worker recovery
- Circuit breaker pattern
- Health monitoring with metrics

Run: just stress-test
"""
import sys
import shutil
import time
from pathlib import Path

# Add framework to path
sys.path.insert(0, str(Path(__file__).parent))

from stress import (
    TestRunner, Phase9Suite, StressConfig,
    ReportFormat, create_runner, TestSuite, TestCase
)

# Test data directory
TEST_DIR = Path("mcp-server/tests/stress_data")


def setup_environment(config: StressConfig, noise_files: int = 900, target_files: int = 100) -> None:
    """Generate test files for stress testing."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir(parents=True)

    print(f"\n[SETUP] Generating stress test data...")

    # Generate noise files (distractors)
    for i in range(noise_files):
        (TEST_DIR / f"file_{i}.py").write_text(f"""\
def func_{i}():
    x = {i}
    return x * 2
""")

    # Generate target files (contains patterns to find)
    for i in range(900, 900 + target_files):
        (TEST_DIR / f"target_{i}.py").write_text(f"""\
import logging
logger = logging.getLogger(__name__)

def risky_logic_{i}():
    try:
        process_data({i})
    except ValueError:
        pass  # Silent exception

def another_func_{i}():
    try:
        api_call()
    except Exception:
        pass  # Silent exception
""")

    print(f"[SETUP] Created {noise_files + target_files} files")


def cleanup() -> None:
    """Clean up test environment."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
        print(f"[CLEANUP] Removed {TEST_DIR}")


def run_all_suites() -> bool:
    """Run all registered stress test suites."""
    print("\n[FRAMEWORK] Initializing modular stress test framework...")

    config = StressConfig(
        stress_dir=TEST_DIR,
        verbose=True,
        max_duration=2.0
    )

    runner = create_runner(config)

    # Add additional suites here as they are developed
    # runner.register_suite(Phase10Suite(config))
    # runner.register_suite(Phase11Suite(config))

    # Run all suites
    results = runner.run_all()

    # Generate combined report
    all_passed = all(r.all_passed for r in results.values())

    print("\n" + "=" * 60)
    print("📊 COMBINED STRESS TEST REPORT")
    print("=" * 60)

    for name, result in results.items():
        print(f"\n--- {result.name} (Phase {result.phase}) ---")
        print(runner.report(result, ReportFormat.TEXT))

    return all_passed


def quick_benchmark() -> dict:
    """Run a quick benchmark of core functionality."""
    print("\n[QUICK] Running core benchmark...")

    import subprocess
    start = time.perf_counter()
    result = subprocess.run(
        ["ast-grep", "run", "--pattern", "def $NAME", "--lang", "py", str(TEST_DIR)],
        capture_output=True, text=True, timeout=30
    )
    duration = time.perf_counter() - start

    return {
        "duration": duration,
        "files": len(list(TEST_DIR.glob("*.py"))),
        "matches": result.stdout.count(".py:")
    }


def main() -> int:
    """Main entry point for stress test framework."""
    print("=" * 60)
    print("🚀 Modular Stress Test Framework")
    print("=" * 60)
    print("Version: 2.0.0")
    print("Suites: Phase9 (Code Intelligence)")
    print("=" * 60)

    try:
        # Setup
        config = StressConfig(stress_dir=TEST_DIR)
        setup_environment(config)

        # Quick benchmark
        bench = quick_benchmark()
        print(f"\n[QUICK] Benchmark: {bench['files']} files in {bench['duration']:.4f}s")
        print(f"[QUICK] Found {bench['matches']} matches")

        # Run all suites
        all_passed = run_all_suites()

        # Summary
        print("\n" + "=" * 60)
        print("📊 FRAMEWORK SUMMARY")
        print("=" * 60)
        print(f"Test Data: {TEST_DIR}")
        print(f"Status: {'✅ ALL SUITES PASSED' if all_passed else '❌ SOME SUITES FAILED'}")
        print("=" * 60)

        return 0 if all_passed else 1

    except KeyboardInterrupt:
        print("\n[ABORT] Test interrupted by user")
        return 130

    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
