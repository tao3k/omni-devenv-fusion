"""
agent/core/security/manifest_validator.py
 SKILL.md Validator for skill permission audit.

Validates skill SKILL.md for dangerous permissions.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter


@dataclass
class PermissionWarning:
    """A permission warning."""

    permission: str
    value: str
    severity: str  # "warning", "danger"
    message: str


@dataclass
class ValidationResult:
    """Result of SKILL.md validation."""

    is_valid: bool
    is_blocked: bool = False
    is_warning: bool = False
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dangerous_permissions: list[PermissionWarning] = field(default_factory=list)
    warning_permissions: list[PermissionWarning] = field(default_factory=list)

    def add_error(self, error: str) -> None:
        """Add an error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str) -> None:
        """Add a warning."""
        self.warnings.append(warning)
        self.is_warning = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_valid": self.is_valid,
            "is_blocked": self.is_blocked,
            "is_warning": self.is_warning,
            "warnings": self.warnings,
            "errors": self.errors,
            "dangerous_permissions": [
                {
                    "permission": p.permission,
                    "value": p.value,
                    "severity": p.severity,
                    "message": p.message,
                }
                for p in self.dangerous_permissions
            ],
            "warning_permissions": [
                {
                    "permission": p.permission,
                    "value": p.value,
                    "severity": p.severity,
                    "message": p.message,
                }
                for p in self.warning_permissions
            ],
        }


class ManifestValidator:
    """
    Validates SKILL.md for dangerous permissions.

    Only supports SKILL.md format.
    """

    # Class constants for threshold values
    BLOCK_THRESHOLD: int = 2  # 2+ dangerous permissions blocks
    WARN_THRESHOLD: int = 1

    def validate(
        self, manifest: dict[str, Any], skill_path: Path | None = None
    ) -> ValidationResult:
        """
        Validate SKILL.md metadata for dangerous permissions.

        Args:
            manifest: SKILL.md frontmatter metadata
            skill_path: Path to skill directory (optional)

        Returns:
            ValidationResult with permission flags
        """
        result = ValidationResult(is_valid=True)

        # Validate required fields
        if "name" not in manifest or not manifest.get("name"):
            result.add_error("Missing required field: name")
        if "version" not in manifest or not manifest.get("version"):
            result.add_error("Missing required field: version")

        # If validation already failed due to missing required fields, return early
        if not result.is_valid:
            return result

        # Define dangerous and warning permissions
        DANGEROUS = {
            "shell": "Allows execution of arbitrary shell commands",
            "filesystem": "Allows read/write access to filesystem",
            "sudo": "Allows execution with elevated privileges",
            "exec": "Allows executing external processes",
        }

        WARNING = {
            "network": "Allows external network access",
            "environment": "Access to environment variables",
            "process": "Information about running processes",
        }

        # Check for dangerous permissions
        permissions = manifest.get("permissions", {})
        for perm, value in permissions.items():
            if perm.lower() in DANGEROUS:
                result.dangerous_permissions.append(
                    PermissionWarning(
                        permission=perm,
                        value=str(value),
                        severity="danger",
                        message=DANGEROUS[perm.lower()],
                    )
                )

            elif perm.lower() in WARNING:
                result.warning_permissions.append(
                    PermissionWarning(
                        permission=perm,
                        value=str(value),
                        severity="warning",
                        message=WARNING[perm.lower()],
                    )
                )

        # Block if too many dangerous permissions
        danger_count = len(result.dangerous_permissions)
        warning_count = len(result.warning_permissions)

        result.is_blocked = danger_count >= self.BLOCK_THRESHOLD
        result.is_warning = danger_count >= 1 or warning_count >= self.WARN_THRESHOLD

        return result

    def validate_file(self, skill_md_path: Path) -> ValidationResult:
        """
        Validate a SKILL.md file.

        Args:
            skill_md_path: Path to SKILL.md

        Returns:
            ValidationResult with permission flags
        """
        result = ValidationResult(is_valid=True)

        if not skill_md_path.exists():
            result.add_error(f"SKILL.md not found: {skill_md_path}")
            return result

        try:
            with open(skill_md_path) as f:
                post = frontmatter.load(f)
            manifest = post.metadata or {}
        except Exception as e:
            result.add_error(f"Failed to parse SKILL.md: {e}")
            return result

        return self.validate(manifest, skill_md_path.parent)

    def check_trusted_source(
        self, source: str, manifest: dict[str, Any] | None = None
    ) -> tuple[bool, str]:
        """
        Check if a skill is from a trusted source.

        Args:
            source: Source URL or identifier
            manifest: SKILL.md frontmatter metadata (optional)

        Returns:
            Tuple of (is_trusted: bool, reason: str)
        """
        # Trusted source patterns
        trusted_domains = ["github.com/omni-dev", "github.com/official"]
        trusted_prefixes = ["official/", "verified/", "core/"]

        # Check source URL
        source_lower = source.lower()
        for domain in trusted_domains:
            if domain in source_lower:
                return True, f"Trusted domain: {domain}"

        for prefix in trusted_prefixes:
            if source_lower.startswith(prefix):
                return True, f"Trusted prefix: {prefix}"

        # Also check manifest authors if provided
        if manifest:
            trusted_sources = ["official", "verified", "core"]
            authors = manifest.get("authors", [])

            for author in authors:
                author_lower = author.lower()
                for trusted in trusted_sources:
                    if trusted in author_lower:
                        return True, f"Trusted author: {author}"

        return False, f"Untrusted source: {source}"


def validate_skill_manifest(
    skill_md_path: str, block_threshold: int = 3, warn_threshold: int = 1
) -> ValidationResult:
    """
    Convenience function to validate a SKILL.md.

    Args:
        skill_md_path: Path to SKILL.md
        block_threshold: Number of warnings to trigger block
        warn_threshold: Number of warnings to trigger warn

    Returns:
        ValidationResult
    """
    validator = ManifestValidator()
    validator.BLOCK_THRESHOLD = block_threshold
    validator.WARN_THRESHOLD = warn_threshold
    return validator.validate_file(Path(skill_md_path))


def quick_scan(skill_path: Path) -> ValidationResult:
    """
    Quick SKILL.md scan without detailed validation.

    Args:
        skill_path: Path to skill directory

    Returns:
        ValidationResult with basic checks
    """
    skill_md_path = skill_path / "SKILL.md"

    if not skill_md_path.exists():
        return ValidationResult(
            is_valid=False,
            is_blocked=False,
            is_warning=False,
            warnings=["No SKILL.md found"],
            errors=["SKILL.md is required"],
        )

    return validate_skill_manifest(str(skill_md_path))


__all__ = [
    "PermissionWarning",
    "ValidationResult",
    "ManifestValidator",
    "validate_skill_manifest",
    "quick_scan",
]
