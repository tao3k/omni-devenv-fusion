"""
Security Module - Permission Gatekeeper (Python Wrapper)

Zero Trust security validation for skill tool execution.
Uses Rust core for high-performance permission checking.

Architecture:
- SecurityValidator: Validates tool calls against skill permissions
- SecurityError: Custom exception for security violations

The heavy lifting is done by Rust's PermissionGatekeeper via omni_core_rs.
"""

try:
    from omni_core_rs import check_permission as _check_permission

    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False

    # Fallback for testing without Rust
    def _check_permission(tool_name: str, permissions: list[str]) -> bool:
        for pattern in permissions:
            if pattern == "*":
                return True
            if pattern.endswith(":*"):
                prefix = pattern[:-2].replace(":", ".")
                if tool_name.startswith(prefix):
                    return True
        return False


class SecurityError(Exception):
    """Raised when a skill attempts unauthorized tool access."""

    def __init__(self, skill_name: str, tool_name: str, required_permission: str):
        self.skill_name = skill_name
        self.tool_name = tool_name
        self.required_permission = required_permission
        message = (
            f"SecurityError: Skill '{skill_name}' is not authorized to use '{tool_name}'. "
            f"Required permission: '{required_permission}'. "
            f"Add this permission to SKILL.md frontmatter to enable."
        )
        super().__init__(message)


class SecurityValidator:
    """
    Validates skill tool calls against declared permissions.

    Uses Rust's PermissionGatekeeper for high-performance checking.

    Usage:
        validator = SecurityValidator()

        # Check before executing a tool
        if not validator.validate("my_skill", "filesystem.read_file", ["filesystem:read"]):
            raise SecurityError(...)

        # Or raise directly
        validator.validate_or_raise("my_skill", "filesystem.read_file", ["filesystem:read"])
    """

    def __init__(self):
        """Initialize the validator."""
        pass

    def validate(
        self,
        skill_name: str,
        tool_name: str,
        skill_permissions: list[str] | None = None,
    ) -> bool:
        """
        Validate if a skill is authorized to use a tool.

        Args:
            skill_name: Name of the skill making the call.
            tool_name: Name of the tool being called.
            skill_permissions: List of permissions from SKILL.md.
                Defaults to empty list (Zero Trust = no access).

        Returns:
            True if authorized, False otherwise.
        """
        permissions = skill_permissions or []
        return _check_permission(tool_name, permissions)

    def validate_or_raise(
        self,
        skill_name: str,
        tool_name: str,
        skill_permissions: list[str] | None = None,
    ) -> None:
        """
        Validate permission or raise SecurityError.

        Args:
            skill_name: Name of the skill making the call.
            tool_name: Name of the tool being called.
            skill_permissions: List of permissions from SKILL.md.

        Raises:
            SecurityError: If skill is not authorized.
        """
        if not self.validate(skill_name, tool_name, skill_permissions):
            raise SecurityError(
                skill_name=skill_name,
                tool_name=tool_name,
                required_permission=tool_name,
            )

    def is_rust_available(self) -> bool:
        """Check if Rust core is available."""
        return _RUST_AVAILABLE


__all__ = ["SecurityError", "SecurityValidator"]
