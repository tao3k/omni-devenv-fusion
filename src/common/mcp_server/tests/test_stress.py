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
import shutil
import time
from pathlib import Path

from rich.console import Console
from rich.theme import Theme
from rich import print as rprint

# Rich theme for consistent styling
custom_theme = Theme({
    "info": "cyan",
    "success": "green",
    "error": "red",
    "warning": "yellow",
    "title": "magenta",
    "setup": "blue",
    "cleanup": "orange3",
    "frame": "bright_cyan",
    "quick": "cyan",
})
console = Console(theme=custom_theme)

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

    console.print(f"\n🔧 [setup]Generating stress test data...[/]")

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

    console.print(f"[setup]Created {noise_files + target_files} files[/]")


def cleanup() -> None:
    """Clean up test environment."""
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
        console.print(f"[cleanup]Removed {TEST_DIR}[/]")


def run_all_suites() -> bool:
    """Run all registered stress test suites."""
    console.print("\n🚀 [frame]Initializing modular stress test framework...[/]")

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

    console.print("\n" + "=" * 60)
    console.print("📊 [title]COMBINED STRESS TEST REPORT[/]")
    console.print("=" * 60)

    for name, result in results.items():
        console.print(f"\n--- [info]{result.name}[/] (Phase {result.phase}) ---")
        console.print(runner.report(result, ReportFormat.TEXT))

    return all_passed


def quick_benchmark() -> dict:
    """Run a quick benchmark of core functionality."""
    console.print("\n⚡ [quick]Running core benchmark...[/]")

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
    console.print("=" * 60)
    console.print("🚀 [title]Modular Stress Test Framework[/]")
    console.print("=" * 60)
    console.print("[info]Version:[/] 2.0.0")
    console.print("[info]Suites:[/] Phase9 (Code Intelligence)")
    console.print("=" * 60)

    try:
        # Setup
        config = StressConfig(stress_dir=TEST_DIR)
        setup_environment(config)

        # Quick benchmark
        bench = quick_benchmark()
        console.print(f"\n⚡ [quick]Benchmark:[/] {bench['files']} files in {bench['duration']:.4f}s")
        console.print(f"⚡ [quick]Found:[/] {bench['matches']} matches")

        # Run all suites
        all_passed = run_all_suites()

        # Summary
        console.print("\n" + "=" * 60)
        console.print("📊 [title]FRAMEWORK SUMMARY[/]")
        console.print("=" * 60)
        console.print(f"[info]Test Data:[/] {TEST_DIR}")
        status = "[success]✅ ALL SUITES PASSED[/]" if all_passed else "[error]❌ SOME SUITES FAILED[/]"
        console.print(f"[info]Status:[/] {status}")
        console.print("=" * 60)

        return 0 if all_passed else 1

    except KeyboardInterrupt:
        console.print("\n🛑 [warning]Test interrupted by user[/]")
        return 130

    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
