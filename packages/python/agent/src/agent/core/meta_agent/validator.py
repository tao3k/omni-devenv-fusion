"""
src/agent/core/meta_agent/validator.py
 Sandbox Validator for generated skills.

Executes generated skills and tests in an isolated environment
to verify code correctness before saving to the skills directory.
"""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of validating a skill in the sandbox."""

    success: bool
    stdout: str
    stderr: str
    error_summary: str
    duration_ms: float = 0.0


class SandboxValidator:
    """
    Executes generated skills and tests in an isolated temporary environment.

    This validator:
    1. Creates a temporary directory mirroring skill structure
    2. Writes the generated skill code and tests
    3. Runs pytest in the project's uv environment
    4. Returns detailed results for the refinement loop
    """

    def __init__(self, project_root: Path | None = None):
        """
        Initialize the validator.

        Args:
            project_root: Root directory of the project (defaults to project root)
        """
        if project_root is None:
            from common.gitops import get_project_root

            project_root = get_project_root()

        self.project_root = Path(project_root)

    def validate(
        self,
        skill_name: str,
        skill_code: str,
        test_code: str,
        timeout_seconds: int = 30,
    ) -> ValidationResult:
        """
        Write code to a temp dir and run pytest.

        Args:
            skill_name: Name of the skill being validated
            skill_code: Python code for the skill implementation
            test_code: Python code for the test
            timeout_seconds: Maximum time to allow for test execution

        Returns:
            ValidationResult with success status and error details
        """
        import time

        t0 = time.perf_counter()

        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)

            # Setup standard skill structure
            scripts_dir = work_dir / "scripts"
            tests_dir = work_dir / "tests"
            scripts_dir.mkdir(parents=True)
            tests_dir.mkdir(parents=True)

            # Write files
            (scripts_dir / "__init__.py").touch()
            (scripts_dir / f"{skill_name}.py").write_text(skill_code, encoding="utf-8")
            (tests_dir / f"test_{skill_name}.py").write_text(test_code, encoding="utf-8")

            # Build environment with PYTHONPATH including agent source
            import os

            env = {
                **os.environ,
                "PYTHONPATH": str(self.project_root / "packages/python/agent/src"),
            }

            # Command: uv run pytest <temp_test_file>
            cmd = [
                "uv",
                "run",
                "pytest",
                str(tests_dir / f"test_{skill_name}.py"),
                "-v",
                "--tb=short",
            ]

            try:
                result = subprocess.run(
                    cmd,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    env=env,
                )

                success = result.returncode == 0
                error_summary = ""

                if not success:
                    # Extract last lines of stderr/stdout as summary
                    error_output = result.stderr or result.stdout
                    error_summary = self._extract_error_summary(error_output)

                duration_ms = (time.perf_counter() - t0) * 1000

                return ValidationResult(
                    success=success,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    error_summary=error_summary,
                    duration_ms=duration_ms,
                )

            except subprocess.TimeoutExpired:
                duration_ms = (time.perf_counter() - t0) * 1000
                logger.warning("validation_timeout", skill=skill_name, timeout=timeout_seconds)
                return ValidationResult(
                    success=False,
                    stdout="",
                    stderr="",
                    error_summary=f"Test execution timed out after {timeout_seconds} seconds",
                    duration_ms=duration_ms,
                )

            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000
                logger.error("validation_crash", skill=skill_name, error=str(e))
                return ValidationResult(
                    success=False,
                    stdout="",
                    stderr="",
                    error_summary=f"Validator crash: {e}",
                    duration_ms=duration_ms,
                )

    def _extract_error_summary(self, output: str, max_length: int = 800) -> str:
        """
        Extract a useful error summary from test output.

        Args:
            output: Full test output (stdout or stderr)
            max_length: Maximum length of returned summary

        Returns:
            Concise error summary
        """
        if not output:
            return "No output from test runner"

        # Look for common error patterns
        lines = output.strip().split("\n")

        # Priority: FAILED, ERROR, then last 10 lines
        for i, line in enumerate(lines):
            if line.startswith("FAILED") or line.startswith("ERROR"):
                # Extract context around the failure
                start = max(0, i - 2)
                end = min(len(lines), i + 15)
                summary = "\n".join(lines[start:end])
                if len(summary) > max_length:
                    summary = summary[:max_length] + "...\n(truncated)"
                return summary

        # If no clear failure marker, take last N lines
        if len(lines) > 20:
            summary = "\n".join(lines[-20:])
        else:
            summary = "\n".join(lines)

        if len(summary) > max_length:
            summary = summary[:max_length] + "...\n(truncated)"

        return summary


async def validate_and_refine(
    skill_name: str,
    skill_code: str,
    test_code: str,
    requirement: str,
    skill_manager: Any,
    project_root: Path | None = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Validate skill code and refine if necessary using the Meta skill.

    This is the main entry point for 's self-repair loop.

    Args:
        skill_name: Name of the skill
        skill_code: Python code for the skill implementation
        test_code: Python code for the test
        requirement: Original requirement for context
        skill_manager: SkillManager instance (for calling meta.refine_code)
        project_root: Project root path
        max_retries: Maximum refinement attempts

    Returns:
        Dict with:
            - success: Whether final validation passed
            - code: Final (possibly refined) skill code
            - attempts: Number of validation attempts
            - error: Error message if failed
    """
    validator = SandboxValidator(project_root)

    # Initialize result to satisfy type checker
    result = ValidationResult(success=False, stdout="", stderr="", error_summary="")

    for attempt in range(max_retries + 1):
        logger.info(
            "validating_skill",
            skill=skill_name,
            attempt=attempt + 1,
            max_attempts=max_retries + 1,
        )

        # Validate
        result = validator.validate(skill_name, skill_code, test_code)

        if result.success:
            logger.info(
                "skill_validation_passed",
                skill=skill_name,
                duration_ms=result.duration_ms,
            )
            return {
                "success": True,
                "code": skill_code,
                "attempts": attempt + 1,
                "duration_ms": result.duration_ms,
            }

        # Validation failed - try to refine
        logger.warning(
            "skill_validation_failed",
            skill=skill_name,
            error_summary=result.error_summary[:200],
        )

        if attempt < max_retries and skill_manager is not None:
            logger.info("refining_skill_via_meta", skill=skill_name)

            try:
                # Call the meta skill to refine the code
                refine_result = await skill_manager.run(
                    "meta",
                    "refine_code",
                    {
                        "requirement": requirement,
                        "code": skill_code,
                        "error": result.stdout + "\n" + result.stderr,
                    },
                )

                # Check if refinement returned valid code
                if refine_result and not refine_result.startswith("# Error"):
                    skill_code = refine_result
                    logger.info("refinement_completed", skill=skill_name, attempt=attempt + 1)
                    continue
                else:
                    logger.error(
                        "refinement_failed",
                        skill=skill_name,
                        error=refine_result[:200] if refine_result else "Empty result",
                    )

            except Exception as e:
                logger.error("refinement_exception", skill=skill_name, error=str(e))

        # Either no more retries, or refinement failed
        break

    # Final failure - use result.error_summary (it's initialized above)
    return {
        "success": False,
        "code": skill_code,
        "attempts": max_retries + 1,
        "error": result.error_summary,
    }


__all__ = [
    "SandboxValidator",
    "ValidationResult",
    "validate_and_refine",
]
