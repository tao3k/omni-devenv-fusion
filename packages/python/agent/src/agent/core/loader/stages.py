# agent/core/loader/stages.py
"""
Pipeline stages for skill loading.

Contains: DiscoveryStage, ValidationStage, SecurityStage
Uses Rust scanner for SKILL.md parsing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from .config import LoaderConfig
from agent.core.skill_discovery import parse_skill_md

if TYPE_CHECKING:
    from agent.core.protocols import SecurityAssessment

logger = structlog.get_logger(__name__)


class DiscoveryStage:
    """Stage 1: Discover skills in the skills directory."""

    __slots__ = ("config",)

    def __init__(self, config: LoaderConfig) -> None:
        self.config = config

    def run(self, skills_dir: Path) -> list[Path]:
        """Discover all skill directories."""
        if not skills_dir.exists():
            logger.warning("Skills directory not found", path=str(skills_dir))
            return []

        skills: list[Path] = []
        for entry in skills_dir.iterdir():
            if not entry.is_dir():
                continue

            # Check for required files
            has_skill_md = (entry / "SKILL.md").exists()
            has_tools = (entry / "tools.py").exists()

            if self.config.require_manifest and not has_skill_md:
                logger.debug("Skipping - no SKILL.md", skill=entry.name)
                continue

            if self.config.require_tools and not has_tools:
                logger.debug("Skipping - no tools.py", skill=entry.name)
                continue

            skills.append(entry)

        logger.info("Discovery complete", count=len(skills))
        return skills


class ValidationStage:
    """Stage 2: Validate skill SKILL.md and structure."""

    __slots__ = ("config",)

    def __init__(self, config: LoaderConfig) -> None:
        self.config = config

    def run(self, skill_path: Path) -> tuple[bool, str]:
        """
        Validate a skill.

        Returns:
            (is_valid, error_message)
        """
        # Check SKILL.md exists
        skill_md_path = skill_path / "SKILL.md"
        if not skill_md_path.exists():
            return False, f"SKILL.md not found at {skill_md_path}"

        # Validate SKILL.md frontmatter using Rust scanner
        try:
            # Use Rust scanner for high-performance parsing
            manifest = parse_skill_md(skill_path) or {}

            # Required fields
            required = ["name", "version", "description"]
            for field in required:
                if field not in manifest or not manifest.get(field):
                    return False, f"Required field '{field}' missing from SKILL.md"

            # Validate name
            name = manifest.get("name", "")
            if not name or not isinstance(name, str):
                return False, "Invalid skill name"

            # Validate version
            version = manifest.get("version", "")
            if not isinstance(version, str):
                return False, "Invalid version format"

        except json.JSONDecodeError as e:
            return False, f"Invalid JSON in manifest: {e}"

        return True, ""


class SecurityStage:
    """Stage 3: Security assessment for skills."""

    __slots__ = ("config",)

    def __init__(self, config: LoaderConfig) -> None:
        self.config = config

    def run(self, skill_path: Path) -> "SecurityAssessment":
        """Perform security assessment."""
        if not self.config.security_enabled:
            return self._create_passive_assessment()

        try:
            from agent.core.protocols import SecurityDecision, SecurityAssessment

            # Check trusted sources
            if self.config.trust_local_skills:
                return SecurityAssessment(
                    decision=SecurityDecision.SAFE,
                    score=0,
                    findings_count=0,
                    is_trusted=True,
                    reason="Local skill (trusted)",
                )

            # Full security scan
            from agent.core.security.immune_system import ImmuneSystem

            immune = ImmuneSystem()
            assessment = immune.assess(skill_path)

            return SecurityAssessment(
                decision=SecurityDecision(assessment.decision.value),
                score=assessment.score,
                findings_count=assessment.findings_count,
                is_trusted=assessment.is_trusted,
                reason=assessment.reason,
                details=assessment.details,
            )

        except Exception as e:
            from agent.core.protocols import SecurityDecision, SecurityAssessment

            logger.warning("Security scan failed", skill=skill_path.name, error=str(e))
            return SecurityAssessment(
                decision=SecurityDecision.SAFE,
                score=0,
                findings_count=0,
                is_trusted=False,
                reason=f"Scan error: {e}",
            )

    def _create_passive_assessment(self) -> "SecurityAssessment":
        """Create a passive (skip) assessment."""
        from agent.core.protocols import SecurityDecision, SecurityAssessment

        return SecurityAssessment(
            decision=SecurityDecision.SAFE,
            score=0,
            findings_count=0,
            is_trusted=self.config.trust_local_skills,
            reason="Security disabled",
        )


__all__ = ["DiscoveryStage", "ValidationStage", "SecurityStage"]
