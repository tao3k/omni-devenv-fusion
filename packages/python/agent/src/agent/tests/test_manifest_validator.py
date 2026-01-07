"""
packages/python/agent/src/agent/tests/test_phase28_manifest_validator.py
Phase 28: Manifest Validator Tests.

Tests cover:
- Schema validation
- Permission audit
- Dangerous permission detection
- Trusted source checking
"""

import pytest
import json
import tempfile
from pathlib import Path

from agent.core.security.manifest_validator import (
    ManifestValidator,
    ValidationResult,
    PermissionWarning,
)


class TestManifestValidatorSchema:
    """Test manifest schema validation."""

    def test_valid_manifest(self):
        """Test validation of a valid manifest."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "description": "A test skill",
        }

        result = validator.validate(manifest)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_name(self):
        """Test rejection of manifest without name."""
        validator = ManifestValidator()

        manifest = {
            "version": "1.0.0",
        }

        result = validator.validate(manifest)

        assert not result.is_valid
        assert any("name" in e.lower() for e in result.errors)

    def test_missing_version(self):
        """Test rejection of manifest without version."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
        }

        result = validator.validate(manifest)

        assert not result.is_valid
        assert any("version" in e.lower() for e in result.errors)


class TestManifestValidatorPermissions:
    """Test permission validation."""

    def test_dangerous_exec_permission(self):
        """Test detection of dangerous exec permission."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "exec": True,
            },
        }

        result = validator.validate(manifest)

        assert result.is_valid
        assert len(result.warnings) >= 1

        # Check for exec warning
        exec_warnings = [w for w in result.warnings if w.permission == "exec"]
        assert len(exec_warnings) >= 1
        assert exec_warnings[0].severity == "danger"

    def test_dangerous_shell_permission(self):
        """Test detection of dangerous shell permission."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "shell": True,
            },
        }

        result = validator.validate(manifest)

        assert len(result.warnings) >= 1
        assert any(w.permission == "shell" for w in result.warnings)

    def test_filesystem_write_permission(self):
        """Test detection of filesystem write permission."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "filesystem": "write",
            },
        }

        result = validator.validate(manifest)

        assert result.is_warning
        assert any(w.permission == "filesystem" for w in result.warnings)

    def test_filesystem_read_permission(self):
        """Test detection of filesystem read permission."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "filesystem": "read",
            },
        }

        result = validator.validate(manifest)

        # Read permission is less severe
        assert len(result.warnings) >= 1
        assert any(w.permission == "filesystem" for w in result.warnings)

    def test_network_permission_warning(self):
        """Test network permission generates warning."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "network": True,
            },
        }

        result = validator.validate(manifest)

        assert result.is_warning
        assert any(w.permission == "network" for w in result.warnings)

    def test_no_permissions(self):
        """Test manifest with no permissions field."""
        validator = ManifestValidator()

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
        }

        result = validator.validate(manifest)

        assert result.is_valid
        assert not result.is_warning
        assert len(result.warnings) == 0


class TestManifestValidatorFile:
    """Test validating manifest files."""

    def test_validate_manifest_file(self):
        """Test validating a manifest.json file."""
        validator = ManifestValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "name": "test-skill",
                        "version": "1.0.0",
                    }
                )
            )

            result = validator.validate_file(manifest_path)

            assert result.is_valid

    def test_missing_manifest_file(self):
        """Test handling of missing manifest file."""
        validator = ManifestValidator()

        result = validator.validate_file(Path("/nonexistent/manifest.json"))

        assert not result.is_valid
        assert any("not found" in e.lower() for e in result.errors)

    def test_invalid_json(self):
        """Test handling of invalid JSON."""
        validator = ManifestValidator()

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text("{ invalid json }")

            result = validator.validate_file(manifest_path)

            assert not result.is_valid
            assert any("json" in e.lower() for e in result.errors)


class TestManifestValidatorTrustedSource:
    """Test trusted source checking."""

    def test_trusted_source(self):
        """Test detection of trusted source."""
        validator = ManifestValidator()

        is_trusted, reason = validator.check_trusted_source(
            "https://github.com/omni-dev/skill-docker",
            {},
        )

        assert is_trusted
        assert "omni-dev" in reason

    def test_untrusted_source(self):
        """Test detection of untrusted source."""
        validator = ManifestValidator()

        is_trusted, reason = validator.check_trusted_source(
            "https://github.com/random-user/skill",
            {},
        )

        assert not is_trusted
        assert "not in trusted list" in reason


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        result = ValidationResult(is_valid=True)

        assert result.is_valid
        assert not result.is_blocked
        assert not result.is_warning
        assert len(result.warnings) == 0
        assert len(result.errors) == 0

    def test_blocked_result(self):
        """Test creating a blocked result."""
        result = ValidationResult(
            is_valid=True,
            is_blocked=True,
            is_warning=False,
        )

        assert result.is_blocked
        assert not result.is_warning

    def test_result_with_warnings(self):
        """Test creating a result with warnings."""
        result = ValidationResult(
            is_valid=True,
            is_warning=True,
            warnings=[
                PermissionWarning(
                    permission="network",
                    value="true",
                    severity="warning",
                    message="Network access allowed",
                ),
            ],
        )

        assert result.is_warning
        assert len(result.warnings) == 1
        assert result.warnings[0].permission == "network"

    def test_result_to_dict(self):
        """Test serialization to dictionary."""
        result = ValidationResult(
            is_valid=True,
            is_warning=True,
            warnings=[
                PermissionWarning(
                    permission="network",
                    value="true",
                    severity="warning",
                    message="Network access",
                ),
            ],
        )

        result_dict = result.to_dict()

        assert "is_valid" in result_dict
        assert "is_blocked" in result_dict
        assert "is_warning" in result_dict
        assert "warnings" in result_dict
        assert len(result_dict["warnings"]) == 1


class TestManifestValidatorThresholds:
    """Test permission threshold behavior."""

    def test_danger_count_blocks(self):
        """Test that 2+ danger permissions triggers block."""
        validator = ManifestValidator()
        validator.BLOCK_THRESHOLD = 3

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "exec": True,  # danger
                "shell": True,  # danger
            },
        }

        result = validator.validate(manifest)

        assert result.is_blocked

    def test_single_danger_warns(self):
        """Test that 1 danger permission triggers warn."""
        validator = ManifestValidator()
        validator.BLOCK_THRESHOLD = 3
        validator.WARN_THRESHOLD = 1

        manifest = {
            "name": "test-skill",
            "version": "1.0.0",
            "permissions": {
                "shell": True,  # danger
            },
        }

        result = validator.validate(manifest)

        assert result.is_warning
        assert not result.is_blocked
