"""
agent/core/security/manifest_validator.py
Phase 28: Manifest Validator for skill permission audit.

Validates skill manifest.json for dangerous permissions.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PermissionWarning:
    """A permission warning."""

    permission: str
    value: str
    severity: str  # "warning", "danger"
    message: str


@dataclass
class ValidationResult:
    """Result of manifest validation."""

    is_valid: bool
    is_blocked: bool = False
    is_warning: bool = False
    warnings: list[PermissionWarning] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "is_valid": self.is_valid,
            "is_blocked": self.is_blocked,
            "is_warning": self.is_warning,
            "warnings": [
                {
                    "permission": w.permission,
                    "value": w.value,
                    "severity": w.severity,
                    "message": w.message,
                }
                for w in self.warnings
            ],
            "errors": self.errors,
        }


# =============================================================================
# Manifest Schema
# =============================================================================

MANIFEST_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "author": {"type": "string"},
        "repository": {"type": "string"},
        "permissions": {
            "type": "object",
            "properties": {
                "network": {"type": ["boolean", "string"]},
                "filesystem": {"type": ["boolean", "string"]},
                "shell": {"type": ["boolean", "string"]},
                "exec": {"type": ["boolean", "string"]},
                "environment": {"type": ["boolean", "string"]},
                "subprocess": {"type": ["boolean", "string"]},
            },
        },
    },
    "required": ["name", "version"],
}

# Suspicious permission patterns
DANGEROUS_PERMISSIONS = {
    "exec": {
        "severity": "danger",
        "message": "exec permission allows arbitrary code execution - high risk",
    },
    "shell": {
        "severity": "danger",
        "message": "shell permission allows command execution - high risk",
    },
    "filesystem": {
        "severity": "warning",
        "message": "filesystem write permission allows file modification",
    },
    "network": {
        "severity": "warning",
        "message": "network permission allows external connections",
    },
    "subprocess": {
        "severity": "warning",
        "message": "subprocess permission allows running external commands",
    },
    "environment": {
        "severity": "warning",
        "message": "environment access allows modifying system environment",
    },
}


# =============================================================================
# Manifest Validator
# =============================================================================


class ManifestValidator:
    """
    Validate skill manifest for security.

    Usage:
        validator = ManifestValidator()
        result = validator.validate(manifest_dict)
        print(f"Valid: {result.is_valid}, Blocked: {result.is_blocked}")
    """

    # Thresholds for permission-based blocking
    BLOCK_THRESHOLD = 3  # 3+ warnings = block
    WARN_THRESHOLD = 1  # 1+ warnings = warn

    def validate(self, manifest: dict, skill_path: Optional[Path] = None) -> ValidationResult:
        """
        Validate a skill manifest.

        Args:
            manifest: Manifest dictionary
            skill_path: Optional path to skill directory for additional checks

        Returns:
            ValidationResult with permission flags
        """
        result = ValidationResult(is_valid=True)

        # Check required fields
        if "name" not in manifest:
            result.errors.append("Manifest missing required field: name")
            result.is_valid = False

        if "version" not in manifest:
            result.errors.append("Manifest missing required field: version")
            result.is_valid = False

        # Check permissions
        permissions = manifest.get("permissions", {})
        for perm, value in permissions.items():
            if perm in DANGEROUS_PERMISSIONS:
                perm_info = DANGEROUS_PERMISSIONS[perm]

                # Check if permission is dangerous
                if value is True:
                    result.warnings.append(
                        PermissionWarning(
                            permission=perm,
                            value=str(value),
                            severity=perm_info["severity"],
                            message=perm_info["message"],
                        )
                    )
                elif value == "write" and perm == "filesystem":
                    result.warnings.append(
                        PermissionWarning(
                            permission=perm,
                            value=value,
                            severity="danger",
                            message="filesystem.write allows writing to disk - high risk",
                        )
                    )
                elif value == "read" and perm == "filesystem":
                    # Read is less dangerous
                    if perm == "filesystem":
                        result.warnings.append(
                            PermissionWarning(
                                permission=perm,
                                value=value,
                                severity="warning",
                                message="filesystem.read allows reading files",
                            )
                        )

        # Determine block/warn status
        danger_count = sum(1 for w in result.warnings if w.severity == "danger")
        warning_count = sum(1 for w in result.warnings if w.severity == "warning")

        result.is_blocked = (
            danger_count >= 2 or danger_count + warning_count >= self.BLOCK_THRESHOLD
        )
        result.is_warning = danger_count >= 1 or warning_count >= self.WARN_THRESHOLD

        return result

    def validate_file(self, manifest_path: Path) -> ValidationResult:
        """
        Validate a manifest file.

        Args:
            manifest_path: Path to manifest.json

        Returns:
            ValidationResult with permission flags
        """
        result = ValidationResult(is_valid=True)

        if not manifest_path.exists():
            result.errors.append(f"Manifest not found: {manifest_path}")
            result.is_valid = False
            return result

        try:
            content = manifest_path.read_text(encoding="utf-8")
            manifest = json.loads(content)
        except json.JSONDecodeError as e:
            result.errors.append(f"Invalid JSON in manifest: {e}")
            result.is_valid = False
            return result

        return self.validate(manifest, manifest_path.parent)

    def check_trusted_source(self, repository: str, manifest: dict) -> tuple[bool, str]:
        """
        Check if a skill is from a trusted source.

        Args:
            repository: Repository URL
            manifest: Skill manifest

        Returns:
            (is_trusted, reason)
        """
        from common.settings import get_setting

        trusted_sources = get_setting("security.trusted_sources", [])

        for trusted in trusted_sources:
            if trusted in repository:
                return True, f"Source '{trusted}' is trusted"

        return False, "Source is not in trusted list"


# =============================================================================
# Convenience Functions
# =============================================================================


def validate_skill_manifest(
    manifest_path: str, block_threshold: int = 3, warn_threshold: int = 1
) -> ValidationResult:
    """
    Convenience function to validate a skill manifest.

    Args:
        manifest_path: Path to manifest.json
        block_threshold: Number of warnings to trigger block
        warn_threshold: Number of warnings to trigger warn

    Returns:
        ValidationResult
    """
    validator = ManifestValidator()
    validator.BLOCK_THRESHOLD = block_threshold
    validator.WARN_THRESHOLD = warn_threshold
    return validator.validate_file(Path(manifest_path))


def quick_scan(skill_path: Path) -> ValidationResult:
    """
    Quick manifest scan without detailed validation.

    Args:
        skill_path: Path to skill directory

    Returns:
        ValidationResult with basic checks
    """
    manifest_path = skill_path / "manifest.json"

    if not manifest_path.exists():
        return ValidationResult(
            is_valid=True, is_blocked=False, is_warning=False, warnings=[], errors=[]
        )

    return validate_skill_manifest(str(manifest_path))
