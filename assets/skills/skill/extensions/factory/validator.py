"""
validator.py
 Sandbox Validator for generated skills.

Executes generated skills and tests in an isolated environment
to verify code correctness before saving to the skills directory.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog

from common.gitops import get_project_root
from common.skills_path import SKILLS_DIR

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

    def __init__(self):
        """Initialize the validator using SSOT paths."""
        self.project_root = get_project_root()
        self.skills_dir = SKILLS_DIR()

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
        t0 = time.perf_counter()

        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = Path(temp_dir)

            # Setup standard skill structure
            scripts_dir = work_dir / "scripts"
            tests_dir = work_dir / "tests"
            scripts_dir.mkdir(parents=True)
            tests_dir.mkdir(parents=True)

            # Convert skill name to valid Python module name (hyphens to underscores)
            skill_module_name = skill_name.replace("-", "_")

            # Write files
            (scripts_dir / "__init__.py").touch()
            (scripts_dir / f"{skill_module_name}.py").write_text(skill_code, encoding="utf-8")
            (tests_dir / f"test_{skill_module_name}.py").write_text(test_code, encoding="utf-8")

            # Build PYTHONPATH for uv run (includes temp work_dir for scripts import)
            existing_path = os.environ.get("PYTHONPATH", "")
            agent_src = str(self.project_root / "packages/python/agent/src")
            skills_path = str(self.skills_dir)
            work_dir_path = str(work_dir)

            if existing_path:
                new_path = f"{work_dir_path}:{agent_src}:{skills_path}:{existing_path}"
            else:
                new_path = f"{work_dir_path}:{agent_src}:{skills_path}"

            env = {**os.environ, "PYTHONPATH": new_path}

            # Command: uv run pytest <temp_test_file>
            cmd = [
                "uv",
                "run",
                "pytest",
                str(tests_dir / f"test_{skill_module_name}.py"),
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
                    error_summary=f"Test timed out after {timeout_seconds}s",
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
        """Extract useful error summary from test output."""
        if not output:
            return "No output from test runner"

        lines = output.strip().split("\n")

        # Priority: FAILED, ERROR, then last 20 lines
        for i, line in enumerate(lines):
            if line.startswith(("FAILED", "ERROR")):
                start = max(0, i - 2)
                end = min(len(lines), i + 15)
                summary = "\n".join(lines[start:end])
                return summary[:max_length] + (
                    "...\n(truncated)" if len(summary) > max_length else ""
                )

        # If no clear failure marker, take last N lines
        summary = "\n".join(lines[-20:]) if len(lines) > 20 else "\n".join(lines)
        return summary[:max_length] + ("...\n(truncated)" if len(summary) > max_length else "")


async def validate_and_refine(
    skill_name: str,
    skill_code: str,
    test_code: str,
    requirement: str,
    skill_manager: Any,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Validate skill code and refine if necessary using the Meta skill.

    This is the main entry point for self-repair loop.
    """
    validator = SandboxValidator()
    result = ValidationResult(success=False, stdout="", stderr="", error_summary="")

    for attempt in range(max_retries + 1):
        logger.info(
            "validating_skill", skill=skill_name, attempt=attempt + 1, max_attempts=max_retries + 1
        )

        result = validator.validate(skill_name, skill_code, test_code)

        if result.success:
            logger.info("skill_validation_passed", skill=skill_name, duration_ms=result.duration_ms)
            return {
                "success": True,
                "code": skill_code,
                "attempts": attempt + 1,
                "duration_ms": result.duration_ms,
            }

        logger.warning(
            "skill_validation_failed", skill=skill_name, error_summary=result.error_summary[:200]
        )

        if attempt < max_retries and skill_manager is not None:
            logger.info("refining_skill_via_meta", skill=skill_name)
            try:
                refine_result = await skill_manager.run(
                    "meta",
                    "refine_code",
                    {
                        "requirement": requirement,
                        "code": skill_code,
                        "error": result.stdout + "\n" + result.stderr,
                    },
                )
                if refine_result and not refine_result.startswith("# Error"):
                    skill_code = refine_result
                    logger.info("refinement_completed", skill=skill_name, attempt=attempt + 1)
                    continue
            except Exception as e:
                logger.error("refinement_exception", skill=skill_name, error=str(e))

        break

    return {
        "success": False,
        "code": skill_code,
        "attempts": max_retries + 1,
        "error": result.error_summary,
    }


__all__ = ["SandboxValidator", "ValidationResult", "validate_and_refine"]
