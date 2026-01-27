"""
simulator.py - Level 2 Immune Defense: Dynamic Simulation

Uses Rust's omni-security (Docker/NsJail) for isolated execution testing.
Runs LLM-generated test cases in a sandbox to verify skill functionality.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from omni.foundation.bridge.rust_immune import RustImmuneBridge, is_rust_available
from omni.foundation.config.logging import get_logger

logger = get_logger("omni.immune.simulator")


class SimulationResult:
    """Result of a skill simulation run."""

    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        duration_ms: int = 0,
    ):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_ms = duration_ms

    @property
    def passed(self) -> bool:
        """Check if simulation passed."""
        return self.success

    def __repr__(self) -> str:
        status = "PASSED" if self.success else "FAILED"
        return f"SimulationResult({status}, exit_code={self.exit_code}, ms={self.duration_ms})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
        }


class SkillSimulator:
    """
    Level 2 Defense: Functional Verification via Isolated Sandbox.

    This simulator:
    1. Generates a test case for the skill using the LLM
    2. Executes the test in a Rust-managed sandbox (Docker/NsJail)
    3. Reports pass/fail based on execution result

    The sandbox is:
    - Isolated: No network, limited filesystem access
    - Timed: Prevents infinite loops
    - Monitored: Captures stdout/stderr for analysis
    """

    def __init__(self, llm_client: Any | None = None):
        """
        Initialize the simulator.

        Args:
            llm_client: Optional LLM client for generating test cases.
                       If None, uses a simple echo test.
        """
        self.llm = llm_client
        self._sandbox_available: bool | None = None

    async def verify_skill(self, skill_path: Path) -> SimulationResult:
        """
        Verify a skill by running it in the sandbox.

        Args:
            skill_path: Path to the skill file to test

        Returns:
            SimulationResult indicating success/failure
        """
        logger.info(f"Launching sandbox for: {skill_path.name}")

        if not is_rust_available():
            logger.warning("Rust core unavailable - cannot run sandbox")
            return SimulationResult(
                success=False,
                stderr="Sandbox unavailable: Rust core not loaded",
            )

        if not RustImmuneBridge.run_sandbox(str(skill_path)).get("available", True):
            # Check sandbox availability
            check = RustImmuneBridge.run_sandbox(str(skill_path))
            if not check.get("success", True) and "not found" in check.get("stderr", ""):
                logger.warning("Sandbox runtime (Docker/NsJail) not available on this system")
                return SimulationResult(
                    success=False,
                    stderr="Sandbox runtime not available",
                )

        # Generate test case
        test_code = await self._generate_test_case(skill_path)

        # Write test to temp directory and run in sandbox
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Copy skill file
            skill_copy = temp_path / skill_path.name
            skill_copy.write_text(skill_path.read_text())

            # Write test file
            test_file = temp_path / "test_simulation.py"
            test_file.write_text(test_code)

            logger.info(f"Executing in sandbox: {test_file}")

            # Run in sandbox
            result = RustImmuneBridge.run_sandbox(str(test_file))

            return SimulationResult(
                success=result.get("success", False),
                stdout=result.get("stdout", ""),
                stderr=result.get("stderr", ""),
                exit_code=result.get("exit_code", 0),
                duration_ms=result.get("duration_ms", 0),
            )

    async def _generate_test_case(self, skill_path: Path) -> str:
        """
        Generate a test case for the skill.

        If LLM client is available, uses it to generate a comprehensive test.
        Otherwise, uses a simple smoke test.
        """
        source_code = skill_path.read_text()

        if self.llm is None:
            # Simple smoke test - just try to import and call the main function
            return self._simple_smoke_test(source_code, skill_path)

        # Generate comprehensive test using LLM
        return await self._llm_generate_test(source_code, skill_path)

    def _simple_smoke_test(self, source_code: str, skill_path: Path) -> str:
        """
        Generate a simple smoke test that imports and runs the skill.
        """
        skill_name = skill_path.stem

        return f'''#!/usr/bin/env python3
"""
Auto-generated smoke test for {skill_name}
"""

import sys
import os

# Add the skill directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    # Try to import the skill module
    import {skill_name}

    # Check for main function
    if hasattr({skill_name}, 'main'):
        {skill_name}.main()
        print("TEST_PASSED")
    elif hasattr({skill_name}, 'run'):
        {skill_name}.run()
        print("TEST_PASSED")
    else:
        # Just try to import successfully
        print("TEST_PASSED")

except Exception as e:
    print(f"TEST_FAILED: {{e}}", file=sys.stderr)
    sys.exit(1)
'''

    async def _llm_generate_test(self, source_code: str, skill_path: Path) -> str:
        """
        Generate a comprehensive test using the LLM.
        """
        prompt = (
            f"You are a QA Engineer for an Agentic OS.\n"
            f"Here is a newly generated Python Skill:\n"
            f"```python\n{source_code}\n```\n"
            f"Write a standalone Python test script `test_simulation.py` that:\n"
            f"1. Tests the main functionality of this skill\n"
            f"2. Uses unittest or simple assertions\n"
            f"3. Prints 'TEST_PASSED' on success\n"
            f"4. Prints error message and exits with non-zero code on failure\n"
            f"5. Is fully self-contained (no external imports)\n"
            f"Return ONLY the Python code, no markdown."
        )

        try:
            response = await self.llm.complete(
                prompt, system_prompt="Output valid Python code only."
            )
            code = response.get("content", "")

            # Extract code from markdown if present
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0]
            elif "```" in code:
                code = code.split("```")[1].split("```")[0]

            return code.strip()

        except Exception as e:
            logger.error(f"LLM test generation failed: {e}")
            return self._simple_smoke_test(source_code, skill_path)

    def check_sandbox_available(self) -> bool:
        """Check if sandbox is available on this system."""
        if self._sandbox_available is not None:
            return self._sandbox_available

        try:
            # Try to create a sandbox runner and check availability
            import omni_core_rs

            runner = omni_core_rs.PySandboxRunner()
            self._sandbox_available = runner.is_available()
            return self._sandbox_available
        except Exception:
            self._sandbox_available = False
            return False


# Module-level convenience
async def verify_skill(skill_path: Path, llm_client: Any | None = None) -> SimulationResult:
    """Verify a skill in the sandbox."""
    simulator = SkillSimulator(llm_client)
    return await simulator.verify_skill(skill_path)


__all__ = [
    "SimulationResult",
    "SkillSimulator",
    "verify_skill",
]
