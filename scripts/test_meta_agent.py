#!/usr/bin/env python3
"""
Phase 59: The Meta-Agent - Self-Healing Test Script

This script demonstrates the Meta-Agent's ability to:
1. Detect failing tests
2. Analyze the root cause
3. Automatically fix the code
4. Verify the fix
5. Reflect on the process

The test scenario:
- broken_math.py contains intentional bugs
- test_broken_math.py tests will fail
- Meta-Agent will analyze and fix the bugs
- Re-run tests to verify

Usage:
    python scripts/test_meta_agent.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages/python/agent/src"))

from agent.core.meta_agent import MetaAgent, MissionContext


# ============================================================================
# Test Scenario: Broken Math Library
# ============================================================================

BROKEN_MATH_PY = '''"""Broken math library for testing Meta-Agent self-healing."""

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a - b  # BUG: Should be a + b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    result = 0
    for i in range(a):
        result += b
    return result


def factorial(n: int) -> int:
    """Calculate factorial."""
    if n <= 1:
        return 1
    return n * factorial(n - 1)  # BUG: Should be factorial(n - 1)


def is_even(n: int) -> bool:
    """Check if number is even."""
    return n % 2 == 1  # BUG: Should be == 0
'''

TEST_BROKEN_MATH_PY = '''"""Tests for broken math library."""

import pytest
from scripts.broken_math import add, multiply, factorial, is_even


def test_add():
    """Test addition."""
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_multiply():
    """Test multiplication."""
    assert multiply(3, 4) == 12
    assert multiply(0, 5) == 0
    assert multiply(5, 0) == 0


def test_factorial():
    """Test factorial."""
    assert factorial(0) == 1
    assert factorial(1) == 1
    assert factorial(5) == 120
    assert factorial(7) == 5040


def test_is_even():
    """Test even detection."""
    assert is_even(2) == True
    assert is_even(4) == True
    assert is_even(3) == False
    assert is_even(0) == True
'''


class SimpleLLMProvider:
    """Simple LLM provider that uses pattern matching for fix generation."""

    async def analyze_failure(self, failure_summary: str) -> str:
        """Analyze the failure and suggest root cause."""
        failures = failure_summary.split("\n")

        analysis = []
        for failure in failures:
            if "add" in failure.lower() and "5" in failure:
                analysis.append(
                    {
                        "file": "broken_math.py",
                        "function": "add",
                        "issue": "Wrong operator",
                        "description": "Using subtraction (-) instead of addition (+)",
                        "fix": "return a + b",
                    }
                )
            elif "factorial" in failure.lower():
                analysis.append(
                    {
                        "file": "broken_math.py",
                        "function": "factorial",
                        "issue": "Missing recursive call",
                        "description": "factorial(n - 1) call is missing parentheses",
                        "fix": "return n * factorial(n - 1)",
                    }
                )
            elif "is_even" in failure.lower():
                analysis.append(
                    {
                        "file": "broken_math.py",
                        "function": "is_even",
                        "issue": "Wrong modulo check",
                        "description": "Checking == 1 instead of == 0 for even numbers",
                        "fix": "return n % 2 == 0",
                    }
                )

        return str(analysis)

    async def generate_fix(self, analysis: str, target_path: Path) -> dict:
        """Generate fix plan based on analysis."""
        import ast
        import re

        fixes = []
        analysis_str = str(analysis)

        # Parse the analysis (simplified)
        if '"add"' in analysis_str or "add" in analysis_str.lower():
            fixes.append(
                {
                    "path": "broken_math.py",
                    "old_code": "return a - b  # BUG: Should be a + b",
                    "new_code": "return a + b  # Fixed by Meta-Agent",
                }
            )

        if "factorial" in analysis_str.lower():
            fixes.append(
                {
                    "path": "broken_math.py",
                    "old_code": "return n * factorial(n - 1)  # BUG: Should be factorial(n - 1)",
                    "new_code": "return n * factorial(n - 1)  # Fixed by Meta-Agent",
                }
            )

        if "is_even" in analysis_str.lower():
            fixes.append(
                {
                    "path": "broken_math.py",
                    "old_code": "return n % 2 == 1  # BUG: Should be == 0",
                    "new_code": "return n % 2 == 0  # Fixed by Meta-Agent",
                }
            )

        return {"changes": fixes}


def setup_test_scenario():
    """Create the broken math library and tests."""
    print("Setting up test scenario...")

    # Create broken_math.py
    math_file = PROJECT_ROOT / "scripts" / "broken_math.py"
    math_file.write_text(BROKEN_MATH_PY)
    print(f"  Created: {math_file}")

    # Create test file
    test_file = PROJECT_ROOT / "scripts" / "test_broken_math.py"
    test_file.write_text(TEST_BROKEN_MATH_PY)
    print(f"  Created: {test_file}")

    return math_file, test_file


def run_initial_tests():
    """Run the initial tests to verify they fail."""
    print("\n" + "=" * 60)
    print("Running initial tests (expecting failures)...")
    print("=" * 60)

    result = subprocess.run(
        ["python", "-m", "pytest", "scripts/test_broken_math.py", "-v"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode != 0  # True if tests failed


async def run_meta_agent():
    """Run the Meta-Agent to fix the broken code."""
    print("\n" + "=" * 60)
    print("Phase 59: The Meta-Agent - Self-Healing Test")
    print("=" * 60)

    # Setup LLM provider
    llm_provider = SimpleLLMProvider()

    # Create Meta-Agent
    meta = MetaAgent(project_root=PROJECT_ROOT)
    meta.set_llm_provider(llm_provider)

    # Run mission
    result = await meta.run_mission(
        mission_description="Fix broken math library bugs",
        test_command="python -m pytest scripts/test_broken_math.py -v",
        target_path="scripts",
    )

    return result


def verify_fixes():
    """Verify that the fixes work."""
    print("\n" + "=" * 60)
    print("Verifying fixes...")
    print("=" * 60)

    result = subprocess.run(
        ["python", "-m", "pytest", "scripts/test_broken_math.py", "-v"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    return result.returncode == 0  # True if tests passed


def show_fixed_code():
    """Show the fixed code."""
    print("\n" + "=" * 60)
    print("Fixed Code:")
    print("=" * 60)

    math_file = PROJECT_ROOT / "scripts" / "broken_math.py"
    if math_file.exists():
        print(math_file.read_text())


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("Phase 59: The Meta-Agent Test")
    print("=" * 60)
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    import asyncio

    # Step 1: Setup test scenario
    setup_test_scenario()

    # Step 2: Run initial tests (should fail)
    tests_failed = run_initial_tests()
    if not tests_failed:
        print("\n[ERROR] Tests should have failed but they passed!")
        return 1

    print("\n[OK] Initial tests failed as expected")

    # Step 3: Run Meta-Agent to fix
    result = asyncio.run(run_meta_agent())

    print("\n" + "=" * 60)
    print("Mission Summary:")
    print("=" * 60)
    print(f"  Mission ID: {result.mission_id}")
    print(f"  Iterations: {result.iterations}")
    print(f"  Test Results: {len(result.test_results)} tests")
    print(f"  Passed: {sum(1 for r in result.test_results if r.status.value == 'PASS')}")
    print(f"  Failed: {sum(1 for r in result.test_results if r.status.value == 'FAIL')}")

    # Step 4: Verify fixes
    tests_passed = verify_fixes()

    # Step 5: Show final code
    if tests_passed:
        show_fixed_code()

    print("\n" + "=" * 60)
    print("Result:")
    print("=" * 60)

    if tests_passed:
        print("[SUCCESS] Meta-Agent successfully fixed the bugs!")
        print("\nThis demonstrates:")
        print("  1. Test-first development")
        print("  2. Automated failure analysis")
        print("  3. Intelligent fix generation")
        print("  4. Verification and reflection")
        return 0
    else:
        print("[PARTIAL] Some tests still failing")
        print("The Meta-Agent needs more iterations or LLM improvements")
        return 1


if __name__ == "__main__":
    sys.exit(main())
