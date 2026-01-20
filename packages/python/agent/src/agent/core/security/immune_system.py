"""
agent/core/security/immune_system.py
 Immune System - Central security decision engine.

Makes security decisions based on SecurityReport and ValidationResult.
Uses Rust scanner for SKILL.md parsing.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from agent.core.security.scanner import SecurityScanner, SecurityReport
from agent.core.security.manifest_validator import (
    ManifestValidator,
    ValidationResult,
)
from agent.core.skill_discovery import parse_skill_md
from common.config.settings import get_setting


class Decision(Enum):
    """Security decision outcomes."""

    SAFE = "safe"  # Allow, load normally
    WARN = "warn"  # Allow with user warning
    SANDBOX = "sandbox"  # Run in restricted environment
    BLOCK = "block"  # Reject, do not load


@dataclass
class AssessmentResult:
    """Complete security assessment result."""

    decision: Decision
    score: int
    findings_count: int
    warnings_count: int
    is_trusted: bool = False
    reason: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "decision": self.decision.value,
            "score": self.score,
            "findings_count": self.findings_count,
            "warnings_count": self.warnings_count,
            "is_trusted": self.is_trusted,
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class SecurityAssessment:
    """Combined assessment from scanner and validator."""

    skill_name: str
    skill_path: Path
    scanner_report: SecurityReport
    validator_result: ValidationResult
    decision: Decision = Decision.SAFE
    is_trusted_source: bool = False
    user_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "skill_name": self.skill_name,
            "skill_path": str(self.skill_path),
            "decision": self.decision.value,
            "is_trusted_source": self.is_trusted_source,
            "user_warnings": self.user_warnings,
            "scanner_report": self.scanner_report.to_dict(),
            "validator_result": self.validator_result.to_dict(),
        }


# =============================================================================
# Immune System
# =============================================================================


class ImmuneSystem:
    """
    Central security decision engine.

    Combines:
    - Code pattern scanning (SecurityScanner)
    - Manifest validation (ManifestValidator)
    - Trusted source checking

    Usage:
        immune = ImmuneSystem()
        result = immune.assess(skill_path)
        print(f"Decision: {result.decision}, Score: {result.score}")
    """

    # Decision constants
    SAFE = Decision.SAFE
    WARN = Decision.WARN
    SANDBOX = Decision.SANDBOX
    BLOCK = Decision.BLOCK

    # Default thresholds
    BLOCK_THRESHOLD = 30
    WARN_THRESHOLD = 10

    def __init__(self):
        self.scanner = SecurityScanner()
        self.validator = ManifestValidator()

    def assess(self, skill_path: Path) -> SecurityAssessment:
        """
        Perform complete security assessment of a skill.

        Args:
            skill_path: Path to skill directory

        Returns:
            SecurityAssessment with decision
        """
        skill_name = skill_path.name

        # Run security scanner
        scanner_report = self.scanner.scan(skill_path)

        # Validate SKILL.md
        skill_md_path = skill_path / "SKILL.md"

        if skill_md_path.exists():
            validator_result = self.validator.validate_file(skill_md_path)
        else:
            validator_result = ValidationResult(is_valid=False, errors=["No SKILL.md found"])

        # Check trusted sources
        is_trusted, trust_reason = self._check_trusted(skill_path, scanner_report)

        # Make decision
        decision = self._make_decision(scanner_report, validator_result, is_trusted)

        # Generate user warnings
        user_warnings = self._generate_warnings(scanner_report, validator_result, decision)

        return SecurityAssessment(
            skill_name=skill_name,
            skill_path=skill_path,
            scanner_report=scanner_report,
            validator_result=validator_result,
            decision=decision,
            is_trusted_source=is_trusted,
            user_warnings=user_warnings,
        )

    def assess_code(self, code: str, skill_name: str = "unknown") -> SecurityAssessment:
        """
        Assess code directly without full skill directory.

        Args:
            code: Python code to scan
            skill_name: Name of the skill

        Returns:
            SecurityAssessment with decision
        """
        # Run security scanner on code
        scanner_report = self.scanner.scan_code(code, skill_name)

        # No manifest for inline code
        validator_result = ValidationResult(is_valid=True)

        # Check trusted sources (not applicable for inline)
        is_trusted, trust_reason = False, "Inline code not from trusted source"

        # Make decision
        decision = self._make_decision(scanner_report, validator_result, is_trusted)

        # Generate warnings
        user_warnings = self._generate_warnings(scanner_report, validator_result, decision)

        return SecurityAssessment(
            skill_name=skill_name,
            skill_path=Path("."),
            scanner_report=scanner_report,
            validator_result=validator_result,
            decision=decision,
            is_trusted_source=is_trusted,
            user_warnings=user_warnings,
        )

    def _check_trusted(self, skill_path: Path, scanner_report: SecurityReport) -> tuple[bool, str]:
        """Check if skill is from a trusted source."""
        # Check SKILL.md for repository and authors
        skill_md_path = skill_path / "SKILL.md"
        repository = ""
        manifest = {}

        # Use Rust scanner for high-performance parsing
        if skill_md_path.exists():
            try:
                meta = parse_skill_md(skill_path)
                if meta:
                    repository = meta.get("repository", "") or ""
                    manifest = meta
            except Exception:
                pass

        # Use validator to check trusted sources
        is_trusted, reason = self.validator.check_trusted_source(repository, manifest)
        return is_trusted, reason

    def _make_decision(
        self,
        scanner_report: SecurityReport,
        validator_result: ValidationResult,
        is_trusted: bool,
    ) -> Decision:
        """Make final security decision."""
        # Trusted sources bypass most checks
        if is_trusted:
            # Still apply critical threshold
            if scanner_report.total_score >= 50:  # Critical only
                return Decision.BLOCK
            elif scanner_report.total_score >= 10:
                return Decision.WARN
            return Decision.SAFE

        # Check critical findings first
        critical_findings = [f for f in scanner_report.findings if f.severity == "critical"]
        if critical_findings:
            return Decision.BLOCK

        # Check validator block
        if validator_result.is_blocked:
            return Decision.BLOCK

        # Check score thresholds
        if scanner_report.total_score >= self.BLOCK_THRESHOLD:
            return Decision.BLOCK
        elif scanner_report.total_score >= self.WARN_THRESHOLD:
            return Decision.WARN

        # Check validator warnings
        if validator_result.is_warning:
            return Decision.WARN

        # Default to safe
        return Decision.SAFE

    def _generate_warnings(
        self,
        scanner_report: SecurityReport,
        validator_result: ValidationResult,
        decision: Decision,
    ) -> list[str]:
        """Generate human-readable warnings."""
        warnings = []

        # Scanner warnings
        if scanner_report.findings:
            by_severity = {
                "critical": [],
                "high": [],
                "medium": [],
                "low": [],
            }
            for f in scanner_report.findings:
                if f.severity in by_severity:
                    by_severity[f.severity].append(f)

            if by_severity["critical"]:
                warnings.append(
                    f"⚠️ CRITICAL: {len(by_severity['critical'])} critical security patterns detected"
                )
            if by_severity["high"]:
                warnings.append(
                    f"⚠️ HIGH: {len(by_severity['high'])} high-severity patterns detected"
                )
            if by_severity["medium"]:
                warnings.append(
                    f"ℹ️ MEDIUM: {len(by_severity['medium'])} medium-severity patterns detected"
                )

        # Manifest warnings
        for warning in validator_result.warnings:
            if warning.severity == "danger":
                warnings.append(f"🚨 DANGEROUS PERMISSION: {warning.permission} = {warning.value}")
            else:
                warnings.append(f"⚠️ PERMISSION: {warning.permission} = {warning.value}")

        # Decision-based messages
        if decision == Decision.BLOCK:
            warnings.insert(0, "🚫 SKILL BLOCKED: Security concerns detected")
        elif decision == Decision.WARN:
            warnings.insert(0, "⚠️ SKILL WARNING: Proceed with caution")
        elif decision == Decision.SANDBOX:
            warnings.insert(0, "🔒 SANDBOX MODE: Skill will run in restricted environment")

        return warnings

    def format_assessment(self, assessment: SecurityAssessment) -> str:
        """Format assessment for display."""
        lines = [
            f"🔒 Security Assessment for: {assessment.skill_name}",
            f"   Decision: {assessment.decision.value.upper()}",
            f"   Score: {assessment.scanner_report.total_score}",
            f"   Findings: {len(assessment.scanner_report.findings)}",
            f"   Trusted Source: {'Yes' if assessment.is_trusted_source else 'No'}",
            "",
        ]

        if assessment.user_warnings:
            lines.append("Warnings:")
            for warning in assessment.user_warnings:
                lines.append(f"   {warning}")
            lines.append("")

        # Show critical findings
        critical = [f for f in assessment.scanner_report.findings if f.severity == "critical"]
        if critical:
            lines.append("Critical Findings:")
            for f in critical:
                lines.append(f"   Line {f.line_number}: {f.description}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# Convenience Functions
# =============================================================================


def assess_skill(skill_path: str) -> SecurityAssessment:
    """
    Convenience function to assess a skill.

    Args:
        skill_path: Path to skill directory

    Returns:
        SecurityAssessment
    """
    immune = ImmuneSystem()
    return immune.assess(Path(skill_path))


def quick_check(skill_path: Path) -> Decision:
    """
    Quick security check returning only decision.

    Args:
        skill_path: Path to skill directory

    Returns:
        Decision
    """
    immune = ImmuneSystem()
    return immune.assess(skill_path).decision
