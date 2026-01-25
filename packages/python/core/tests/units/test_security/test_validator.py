"""Tests for SecurityValidator (Python wrapper for Rust PermissionGatekeeper)."""

import pytest

from omni.core.security import SecurityError, SecurityValidator


class TestSecurityValidator:
    """Tests for SecurityValidator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = SecurityValidator()

    def test_validate_allowed_exact(self):
        """Test validation when permission is exactly granted."""
        # Tool name format: "category.action" matches permission "category:action"
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="filesystem.read_files",
                skill_permissions=["filesystem:read_files"],
            )
            is True
        )

    def test_validate_allowed_wildcard(self):
        """Test validation with wildcard permission."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="filesystem.read_files",
                skill_permissions=["filesystem:*"],
            )
            is True
        )

    def test_validate_denied_no_permissions(self):
        """Test validation fails with no permissions (Zero Trust)."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="filesystem.read_files",
                skill_permissions=[],
            )
            is False
        )

    def test_validate_denied_none_permissions(self):
        """Test validation fails with None permissions."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="filesystem.read_files",
                skill_permissions=None,
            )
            is False
        )

    def test_validate_denied_wrong_permission(self):
        """Test validation fails with wrong permission."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="filesystem.read_files",
                skill_permissions=["filesystem:write_file"],
            )
            is False
        )

    def test_validate_admin_permission(self):
        """Test validation with admin permission."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="any.tool",
                skill_permissions=["*"],
            )
            is True
        )

    def test_validate_multiple_permissions(self):
        """Test validation with multiple permissions."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="git.status",
                skill_permissions=["git:status", "filesystem:*"],
            )
            is True
        )

    def test_validate_wrong_category(self):
        """Test validation fails for wrong category."""
        assert (
            self.validator.validate(
                skill_name="my_skill",
                tool_name="git.status",
                skill_permissions=["filesystem:*"],
            )
            is False
        )

    def test_validate_or_raise_allowed(self):
        """Test validate_or_raise doesn't raise when allowed."""
        # Should not raise
        self.validator.validate_or_raise(
            skill_name="my_skill",
            tool_name="filesystem.read_files",
            skill_permissions=["filesystem:read_files"],
        )

    def test_validate_or_raise_denied(self):
        """Test validate_or_raise raises SecurityError when denied."""
        with pytest.raises(SecurityError) as exc_info:
            self.validator.validate_or_raise(
                skill_name="my_skill",
                tool_name="filesystem.read_files",
                skill_permissions=[],
            )

        assert "my_skill" in str(exc_info.value)
        assert "filesystem.read_files" in str(exc_info.value)


class TestSecurityError:
    """Tests for SecurityError exception."""

    def test_error_message(self):
        """Test that error message is properly formatted."""
        error = SecurityError(
            skill_name="calculator",
            tool_name="filesystem.read_files",
            required_permission="filesystem:read",
        )

        assert "calculator" in str(error)
        assert "filesystem.read_files" in str(error)
        assert "filesystem:read" in str(error)
        assert "not authorized" in str(error)

    def test_error_attributes(self):
        """Test that error has expected attributes."""
        error = SecurityError(
            skill_name="test_skill",
            tool_name="test_tool",
            required_permission="test:action",
        )

        assert error.skill_name == "test_skill"
        assert error.tool_name == "test_tool"
        assert error.required_permission == "test:action"
