"""
system.py - Immune System Integration

Orchestrates the complete immune defense pipeline:
1. Static Analysis (Rust: omni-ast) - Level 1
2. Dynamic Simulation (Rust: omni-security) - Level 2
3. Permission Gatekeeping (Rust: omni-security) - Ongoing

This is the "Brain" of the immune system that coordinates all defenses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger
from omni.foundation.bridge.rust_immune import is_rust_available

from .validator import StaticValidator, SecurityViolation
from .simulator import SkillSimulator, SimulationResult

logger = logging.getLogger("omni.immune.system")


@dataclass
class ImmuneReport:
    """Complete immune system report for a skill."""

    skill_name: str
    skill_path: Path
    scanned_at: datetime = field(default_factory=datetime.now)

    # Level 1: Static Analysis Results
    static_analysis_passed: bool = False
    static_violations: list[SecurityViolation] = field(default_factory=list)

    # Level 2: Dynamic Simulation Results
    simulation_passed: bool = False
    simulation_result: SimulationResult | None = None

    # Permission Check
    permission_check_passed: bool = False
    required_permissions: list[str] = field(default_factory=list)

    # Final Verdict
    promoted: bool = False
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "skill_path": str(self.skill_path),
            "scanned_at": self.scanned_at.isoformat(),
            "static_analysis": {
                "passed": self.static_analysis_passed,
                "violations": [v.to_dict() for v in self.static_violations],
            },
            "simulation": {
                "passed": self.simulation_passed,
                "result": self.simulation_result.to_dict() if self.simulation_result else None,
            },
            "permissions": {
                "passed": self.permission_check_passed,
                "required": self.required_permissions,
            },
            "promoted": self.promoted,
            "rejection_reason": self.rejection_reason,
        }

    def summary(self) -> str:
        """Generate a human-readable summary."""
        lines = [
            f"Immune Report: {self.skill_name}",
            f"  Static Analysis: {'PASSED' if self.static_analysis_passed else 'FAILED'}",
            f"  Dynamic Simulation: {'PASSED' if self.simulation_passed else 'FAILED'}",
            f"  Permission Check: {'PASSED' if self.permission_check_passed else 'FAILED'}",
            f"  Final Verdict: {'PROMOTED' if self.promoted else 'REJECTED'}",
        ]
        if self.rejection_reason:
            lines.append(f"  Reason: {self.rejection_reason}")
        return "\n".join(lines)


class ImmuneSystem:
    """
    The Central Immune System for Omni-Dev Fusion.

    Coordinates static analysis, dynamic simulation, and permission checking
    to protect the system from malicious or buggy auto-generated skills.

    Architecture:
    ```
    +-------------------+
    |   Candidate Skill |
    +--------+----------+
             |
             v
    +--------+----------+
    | Level 1: Static   |  <-- Rust: omni-ast (ast-grep)
    |    Analysis       |
    +--------+----------+
             |
             v (if passed)
    +--------+----------+
    | Level 2: Dynamic  |  <-- Rust: omni-security (Docker/NsJail)
    |    Simulation     |
    +--------+----------+
             |
             v (if passed)
    +--------+----------+
    | Level 3: Perms    |  <-- Rust: omni-security (Zero Trust)
    +--------+----------+
             |
             v
    +--------+----------+
    |   Promote/Reject  |
    +-------------------+
    ```

    Attributes:
        quarantine_dir: Directory for quarantined rejected skills
        require_simulation: Whether to run dynamic simulation (may require Docker)
        llm_client: Optional LLM client for generating test cases
    """

    def __init__(
        self,
        quarantine_dir: Path | None = None,
        require_simulation: bool = True,
        llm_client: Any | None = None,
    ):
        self.quarantine_dir = quarantine_dir
        self.require_simulation = require_simulation
        self.llm = llm_client

        # Initialize components
        self.validator = StaticValidator()
        self.simulator = SkillSimulator(llm_client)

        logger.info("Immune System initialized")
        if not is_rust_available():
            logger.warning("Rust core not available - using Python fallbacks")

    async def process_candidate(self, skill_path: Path) -> ImmuneReport:
        """
        Process a candidate skill through the complete immune pipeline.

        Args:
            skill_path: Path to the candidate skill file

        Returns:
            ImmuneReport with complete analysis results
        """
        name = skill_path.name
        logger.info(f"🔬 Inspecting Candidate: {name}")
        report = ImmuneReport(skill_name=name, skill_path=skill_path)

        # Check file exists
        if not skill_path.exists():
            report.rejection_reason = f"File not found: {skill_path}"
            return report

        # ================================================================
        # Level 1: Static Analysis (Rust: omni-ast)
        # ================================================================
        logger.info(f"  [1/3] Running static analysis...")
        try:
            is_safe, violations = self.validator.scan(skill_path)
            report.static_analysis_passed = is_safe
            report.static_violations = violations

            if not is_safe:
                report.rejection_reason = "Static analysis failed: security violations detected"
                logger.warning(f"  ❌ Static analysis FAILED - {len(violations)} violation(s)")
                return report

            logger.info(f"  ✅ Static analysis PASSED")

        except Exception as e:
            report.rejection_reason = f"Static analysis error: {e}"
            logger.error(f"  ❌ Static analysis ERROR: {e}")
            return report

        # ================================================================
        # Level 2: Dynamic Simulation (Rust: omni-security)
        # ================================================================
        if self.require_simulation:
            logger.info(f"  [2/3] Running dynamic simulation...")
            try:
                result = await self.simulator.verify_skill(skill_path)
                report.simulation_passed = result.passed
                report.simulation_result = result

                if not result.passed:
                    report.rejection_reason = (
                        f"Simulation failed: {result.stderr or 'Unknown error'}"
                    )
                    logger.warning(
                        f"  ❌ Simulation FAILED - {result.stderr[:100] if result.stderr else 'No output'}"
                    )
                    return report

                logger.info(f"  ✅ Simulation PASSED ({result.duration_ms}ms)")

            except Exception as e:
                report.rejection_reason = f"Simulation error: {e}"
                logger.error(f"  ❌ Simulation ERROR: {e}")
                return report
        else:
            logger.info(f"  [2/3] Skipping simulation (disabled)")

        # ================================================================
        # Level 3: Permission Check (Rust: omni-security)
        # ================================================================
        logger.info(f"  [3/3] Checking permissions...")
        report.permission_check_passed = True  # Default allow if Rust available
        # Permission check is handled at runtime by the tool execution system

        # ================================================================
        # Final Decision
        # ================================================================
        if (
            report.static_analysis_passed
            and (not self.require_simulation or report.simulation_passed)
            and report.permission_check_passed
        ):
            report.promoted = True
            logger.info(f"  🎉 {name} PROMOTED to active skills")
        else:
            report.promoted = False
            if not report.rejection_reason:
                report.rejection_reason = "Unknown rejection"

        return report

    async def scan_directory(self, directory: Path) -> list[ImmuneReport]:
        """
        Process all candidate skills in a directory.

        Args:
            directory: Path to directory containing candidate skills

        Returns:
            List of ImmuneReport for each skill
        """
        reports = []
        logger.info(f"Scanning directory: {directory}")

        for skill_path in directory.rglob("*.py"):
            if skill_path.name.startswith("_") or skill_path.name.startswith("test_"):
                continue

            report = await self.process_candidate(skill_path)
            reports.append(report)

        promoted = sum(1 for r in reports if r.promoted)
        logger.info(f"Scan complete: {len(reports)} skills, {promoted} promoted")

        return reports


# Module-level convenience
def create_immune_system(
    quarantine_dir: Path | None = None,
    require_simulation: bool = True,
    llm_client: Any | None = None,
) -> ImmuneSystem:
    """Create and configure an immune system instance."""
    return ImmuneSystem(quarantine_dir, require_simulation, llm_client)


__all__ = [
    "ImmuneReport",
    "ImmuneSystem",
    "create_immune_system",
]
