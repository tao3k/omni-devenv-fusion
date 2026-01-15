# agent/core/meta_agent.py
"""
 The Meta-Agent - Autonomous Build-Test-Improve Loop

The Meta-Agent implements a self-directed TDD cycle:
1. **Test**: Run tests and capture failures
2. **Analyze**: Understand what's broken using LLM
3. **Fix**: Generate and apply fixes
4. **Verify**: Re-run tests to confirm修复
5. **Reflect**: Log the experience for future learning

Philosophy:
- Tests are the source of truth
- Failures are learning opportunities
- Self-improvement through systematic reflection

Usage:
    from agent.core.meta_agent import MetaAgent, Mission

    # Single mission
    meta = MetaAgent()
    result = await meta.run_mission("Fix failing tests in scripts/test_math.py")

    # Continuous improvement loop
    await meta.run_continuous_improvement(max_iterations=5)
"""

from __future__ import annotations

import ast
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataclasses import dataclass

# In uv workspace, 'common' package is available directly
from common.gitops import get_project_root


# Lazy imports
_cached_logger: Any = None


def _get_logger() -> Any:
    """Get logger lazily."""
    global _cached_logger
    if _cached_logger is None:
        import structlog

        _cached_logger = structlog.get_logger(__name__)
    return _cached_logger


class TestStatus(Enum):
    """Status of a test execution."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIP = "SKIP"


@dataclass
class TestResult:
    """Result of a single test execution."""

    name: str
    status: TestStatus
    output: str
    error_message: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class MissionContext:
    """Context for a mission execution."""

    mission_id: str
    target_path: Path
    test_command: str
    created_at: datetime = field(default_factory=datetime.now)
    iterations: int = 0
    test_results: List[TestResult] = field(default_factory=list)


class MetaAgent:
    """
    The Meta-Agent - Autonomous Build-Test-Improve Loop.

     Implements self-directed engineering with continuous
    improvement through TDD cycles.

    Features:
    - Intelligent test analysis
    - Automated fix generation
    - Learning from failures
    - Continuous improvement loops
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        """Initialize the Meta-Agent."""
        self.project_root = project_root or Path(get_project_root())
        self.mission_history: List[MissionContext] = []
        self._llm_provider = None  # Will be set via set_llm_provider()

    def set_llm_provider(self, provider: Any) -> None:
        """
        Set the LLM provider for analysis and fix generation.

        Args:
            provider: An object with analyze_failure() and generate_fix() methods
        """
        self._llm_provider = provider

    async def run_mission(
        self,
        mission_description: str,
        test_command: str,
        target_path: Optional[str] = None,
    ) -> MissionContext:
        """
        Run a single mission: test -> analyze -> fix -> verify -> reflect.

        Args:
            mission_description: Description of what to achieve
            test_command: Command to run tests
            target_path: Path to the code under test

        Returns:
            MissionContext with all results and reflections
        """
        import uuid

        mission_id = str(uuid.uuid4())[:8]
        target = Path(target_path) if target_path else self.project_root

        context = MissionContext(
            mission_id=mission_id,
            target_path=target,
            test_command=test_command,
        )

        _get_logger().info(
            "Mission started",
            mission_id=mission_id,
            description=mission_description,
            target=str(target),
        )

        # Run the TDD loop
        await self._tdd_cycle(context)

        # Reflect on the mission
        await self._reflect(context)

        self.mission_history.append(context)
        return context

    async def run_continuous_improvement(
        self,
        max_iterations: int = 3,
        mission_description: str = "Continuous code improvement",
    ) -> List[MissionContext]:
        """
        Run continuous improvement missions until all tests pass or max iterations reached.

        Args:
            max_iterations: Maximum number of improvement cycles
            mission_description: Base description for each mission

        Returns:
            List of all mission contexts
        """
        results = []

        for i in range(max_iterations):
            mission_desc = f"{mission_description} (iteration {i + 1}/{max_iterations})"

            result = await self.run_mission(
                mission_description=mission_desc,
                test_command="python -m pytest scripts/test_meta_agent.py -v",
                target_path="scripts",
            )

            results.append(result)

            # Check if we're making progress
            if result.iterations == 0:
                _get_logger().info("All tests passed, stopping improvement loop")
                break

            # Check for stagnation (same failures after 2 iterations)
            if len(results) >= 2:
                if self._detect_stagnation(results[-2:], result):
                    _get_logger().warning("Stagnation detected, adding to backlog")
                    await self._log_stagnation(result)

        return results

    async def _tdd_cycle(self, context: MissionContext) -> None:
        """
        Execute one TDD cycle: Test -> Analyze -> Fix -> Verify.

         The Test Loop
         The Analyzer
         The Fixer
         The Verifier
        """
        max_iterations = 5
        context.iterations = 0

        while context.iterations < max_iterations:
            context.iterations += 1

            _get_logger().info(
                "TDD iteration started",
                mission_id=context.mission_id,
                iteration=context.iterations,
            )

            # Step 1: Run Tests
            passed = await self._run_tests(context)

            if passed:
                _get_logger().info(
                    "All tests passed",
                    mission_id=context.mission_id,
                    iterations=context.iterations,
                )
                return

            # Step 2: Analyze Failures
            analysis = await self._analyze_failures(context)

            # Step 3: Generate and Apply Fix
            fix_success = await self._apply_fix(context, analysis)

            # Step 4: Verify
            if fix_success:
                _get_logger().info(
                    "Fix applied, re-verifying",
                    mission_id=context.mission_id,
                )
            else:
                _get_logger().warning(
                    "Fix could not be applied",
                    mission_id=context.mission_id,
                )

        _get_logger().warning(
            "Max iterations reached",
            mission_id=context.mission_id,
            max_iterations=max_iterations,
        )

    async def _run_tests(self, context: MissionContext) -> bool:
        """
        Run the test command and parse results.

        Returns:
            True if all tests passed
        """
        import re
        import time

        start = time.time()

        try:
            result = subprocess.run(
                context.test_command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=str(self.project_root),  # Run from project root
                timeout=120,
            )

            duration_ms = (time.time() - start) * 1000

            # Parse output
            output = result.stdout + result.stderr
            context.test_results = self._parse_pytest_output(output, duration_ms)

            # Check for pass - use exit code and results
            passed = result.returncode == 0

            # If exit code is 0 but no results parsed, consider it passed
            if passed and not context.test_results:
                context.test_results = [
                    TestResult(
                        name="implicit_pass",
                        status=TestStatus.PASS,
                        output="All tests passed (implicit)",
                        duration_ms=duration_ms,
                    )
                ]

            _get_logger().info(
                "Tests completed",
                mission_id=context.mission_id,
                exit_code=result.returncode,
                total=len(context.test_results),
                passed=sum(1 for r in context.test_results if r.status == TestStatus.PASS),
                failed=sum(1 for r in context.test_results if r.status == TestStatus.FAIL),
                duration_ms=duration_ms,
            )

            return passed

        except subprocess.TimeoutExpired:
            _get_logger().error(
                "Test timeout",
                mission_id=context.mission_id,
                command=context.test_command,
            )
            return False
        except Exception as e:
            _get_logger().error(
                "Test execution failed",
                mission_id=context.mission_id,
                error=str(e),
            )
            return False

    def _parse_pytest_output(self, output: str, duration_ms: float) -> List[TestResult]:
        """Parse pytest output to extract test results."""
        results = []

        import re

        # Pattern for FAILED tests: "FAILED scripts/test_broken_math.py::test_add - error"
        failed_pattern = re.compile(r"FAILED\s+([^\s]+)::(\w+)\s*-")

        # Pattern for passed tests in summary
        passed_pattern = re.compile(r"(\d+)\s+passed")

        failed_count = 0
        passed_count = 0

        # Parse summary line for counts
        for line in output.split("\n"):
            line = line.strip()
            if "failed" in line and "passed" in line:
                # Extract counts
                failed_match = re.search(r"(\d+)\s+failed", line)
                passed_match = re.search(r"(\d+)\s+passed", line)
                if failed_match:
                    failed_count = int(failed_match.group(1))
                if passed_match:
                    passed_count = int(passed_match.group(1))
                break

        # Extract individual failed test names
        for line in output.split("\n"):
            if "FAILED" in line:
                match = failed_pattern.search(line)
                if match:
                    module = match.group(1)
                    test_name = match.group(2)
                    results.append(
                        TestResult(
                            name=f"{module}::{test_name}",
                            status=TestStatus.FAIL,
                            output=line,
                            error_message=line,
                            duration_ms=duration_ms,
                        )
                    )

        # Create passed results if we have count and no failed tests
        # (If we have failures, passed count comes from non-failed tests)
        if failed_count == 0 and passed_count > 0:
            for i in range(passed_count):
                results.append(
                    TestResult(
                        name=f"passed_{i}",
                        status=TestStatus.PASS,
                        output="passed",
                        duration_ms=duration_ms,
                    )
                )

        return results

    async def _analyze_failures(self, context: MissionContext) -> Dict[str, Any]:
        """
         The Analyzer - Understand failures using LLM.

        Returns:
            Analysis report with root cause and fix suggestions
        """
        failures = [r for r in context.test_results if r.status == TestStatus.FAIL]

        if not failures:
            return {"status": "no_failures", "analysis": "All tests passed"}

        if self._llm_provider:
            # Use LLM for intelligent analysis
            failure_summary = "\n".join(f"- {f.name}: {f.error_message}" for f in failures)

            try:
                # This would call the LLM with structured prompt
                analysis = await self._llm_provider.analyze_failure(failure_summary)
                return {
                    "status": "analyzed",
                    "analysis": analysis,
                    "failures": [f.name for f in failures],
                }
            except Exception as e:
                _get_logger().warning(f"LLM analysis failed: {e}, using fallback")

        # Fallback: Simple pattern matching
        return self._simple_analyze(failures)

    def _simple_analyze(self, failures: List[TestResult]) -> Dict[str, Any]:
        """Simple failure analysis without LLM."""
        common_issues = {
            "assertion": ("AssertionError", "Test assertion failed"),
            "import": ("ImportError", "Module import failed"),
            "syntax": ("SyntaxError", "Syntax error in code"),
            "attribute": ("AttributeError", "Object attribute missing"),
            "type": ("TypeError", "Type mismatch"),
        }

        analysis = []
        for failure in failures:
            error_lower = (failure.error_message or "").lower()
            for issue_type, (exc_name, desc) in common_issues.items():
                if exc_name.lower() in error_lower or issue_type in error_lower:
                    analysis.append(
                        {
                            "test": failure.name,
                            "issue_type": issue_type,
                            "description": desc,
                            "error": failure.error_message,
                        }
                    )
                    break
            else:
                analysis.append(
                    {
                        "test": failure.name,
                        "issue_type": "unknown",
                        "description": "Unknown error",
                        "error": failure.error_message,
                    }
                )

        return {
            "status": "analyzed",
            "analysis": analysis,
            "failures": [f.name for f in failures],
            "method": "simple_pattern_matching",
        }

    async def _apply_fix(self, context: MissionContext, analysis: Dict[str, Any]) -> bool:
        """
         The Fixer - Generate and apply code fixes.

        Returns:
            True if fix was successfully applied
        """
        if analysis.get("status") == "no_failures":
            return True

        if not self._llm_provider:
            _get_logger().warning("No LLM provider set, cannot generate intelligent fixes")
            return False

        try:
            # Generate fix using LLM
            fix_plan = await self._llm_provider.generate_fix(
                analysis["analysis"], context.target_path
            )

            if not fix_plan:
                _get_logger().warning("No fix generated")
                return False

            # Apply the fix
            for file_change in fix_plan.get("changes", []):
                file_path = context.target_path / file_change["path"]
                if file_path.exists():
                    await self._apply_file_change(file_path, file_change)

            _get_logger().info(
                "Fix applied",
                mission_id=context.mission_id,
                files_changed=len(fix_plan.get("changes", [])),
            )

            return True

        except Exception as e:
            _get_logger().error(f"Fix application failed: {e}")
            return False

    async def _apply_file_change(self, file_path: Path, change: Dict[str, Any]) -> None:
        """Apply a single file change."""
        try:
            content = file_path.read_text()

            # Simple string replacement (would be more sophisticated with AST)
            old_code = change.get("old_code", "")
            new_code = change.get("new_code", "")

            if old_code and new_code:
                content = content.replace(old_code, new_code)
                file_path.write_text(content)
                _get_logger().info(f"Applied change to {file_path}")

        except Exception as e:
            _get_logger().error(f"Failed to apply change to {file_path}: {e}")

    async def _verify_fix(self, context: MissionContext) -> bool:
        """Re-run tests to verify the fix."""
        return await self._run_tests(context)

    async def _reflect(self, context: MissionContext) -> None:
        """
         The Reflector - Log learnings for future improvement.

        This stores the mission experience in the knowledge base.
        """
        passed = all(r.status == TestStatus.PASS for r in context.test_results)

        reflection = {
            "mission_id": context.mission_id,
            "target": str(context.target_path),
            "iterations": context.iterations,
            "passed": passed,
            "failures": [f.name for f in context.test_results if f.status == TestStatus.FAIL],
            "timestamp": datetime.now().isoformat(),
        }

        # Store in knowledge base
        try:
            from agent.core.vector_store import get_vector_memory

            vm = get_vector_memory()
            await vm.add(
                documents=[str(reflection)],
                ids=[f"mission-{context.mission_id}"],
                metadatas=[{"type": "meta_agent_reflection", "success": passed}],
            )
            _get_logger().info(
                "Reflection stored",
                mission_id=context.mission_id,
                success=passed,
            )
        except Exception as e:
            _get_logger().warning(f"Failed to store reflection: {e}")

    def _detect_stagnation(
        self, recent_results: List[MissionContext], current: MissionContext
    ) -> bool:
        """Detect if we're stuck in a loop of failures."""
        if len(recent_results) < 2:
            return False

        # Check if we're making no progress
        current_failures = set(f.name for f in current.test_results if f.status == TestStatus.FAIL)

        for prev in recent_results[:-1]:
            prev_failures = set(f.name for f in prev.test_results if f.status == TestStatus.FAIL)
            if current_failures == prev_failures:
                return True

        return False

    async def _log_stagnation(self, context: MissionContext) -> None:
        """Log stagnation for human review."""
        _get_logger().warning(
            "Stagnation detected - human intervention needed",
            mission_id=context.mission_id,
            iterations=context.iterations,
            failures=[f.name for f in context.test_results if f.status == TestStatus.FAIL],
        )


# Convenience function
async def run_improvement(
    mission_description: str,
    test_command: str,
    target_path: Optional[str] = None,
) -> MissionContext:
    """Quick function to run a single improvement mission."""
    meta = MetaAgent()
    return await meta.run_mission(mission_description, test_command, target_path)


__all__ = [
    "MetaAgent",
    "MissionContext",
    "TestResult",
    "TestStatus",
    "run_improvement",
]
