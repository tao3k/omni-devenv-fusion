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

            # Handle "service:*" pattern
            if pattern.endswith(":*"):
                prefix = pattern[:-2]
                tool_prefix = tool_name.split(".")[0] if "." in tool_name else tool_name
                if tool_prefix == prefix:
                    return True

            # Handle "service:method" vs "service.method"
            normalized_pattern = pattern.replace(":", ".")
            if tool_name == normalized_pattern:
                return True

        return False


class SecurityError(Exception):
    """Raised when a skill attempts unauthorized tool access."""

    def __init__(
        self,
        skill_name: str,
        tool_name: str,
        required_permission: str,
        protocol_guidance: str | None = None,
    ):
        self.skill_name = skill_name
        self.tool_name = tool_name
        self.required_permission = required_permission
        self.protocol_guidance = protocol_guidance

        message = (
            f"SecurityError: Skill '{skill_name}' is not authorized to use '{tool_name}'.\n"
            f"Required permission: '{required_permission}'.\n"
        )

        if protocol_guidance:
            message += (
                "\n[PROTOCOL ALIGNMENT GUIDANCE]\n"
                f"It appears you are drifting from the '{skill_name}' protocol rules.\n"
                f"Authorized behavior for this skill:\n{protocol_guidance}\n"
                "\nPlease re-align your strategy with these rules."
            )
        else:
            message += f"Add this permission to SKILL.md frontmatter to enable."

        super().__init__(message)


class ProtocolAlignmentError(SecurityError):
    """Specialized error for when the LLM forgets skill-specific tool constraints."""

    pass


class SecurityValidator:
    """
    Validates skill tool calls against declared permissions and protocol alignment.

    Uses Rust's PermissionGatekeeper for high-performance checking.
    """

    def __init__(self, overload_threshold: int = 5):
        """Initialize the validator.

        Args:
            overload_threshold: Number of active skills before triggering a context warning.
        """
        self._failure_counts = {}
        self._active_skills = set()
        self._overload_threshold = overload_threshold
        self._last_warning_count = 0

    def reset_active_skills(self) -> None:
        """Reset the tracked active skills (call this on session reset)."""
        self._active_skills.clear()
        self._last_warning_count = 0

    def validate(
        self,
        skill_name: str,
        tool_name: str,
        skill_permissions: list[str] | None = None,
    ) -> bool:
        """
        Validate if a skill is authorized to use a tool.
        """
        permissions = skill_permissions or []
        is_valid = _check_permission(tool_name, permissions)

        # Track active skills to detect context clutter
        if skill_name and skill_name != "ROOT":
            self._active_skills.add(skill_name)

        if not is_valid:
            # Track failures for cognitive drift detection
            key = (skill_name, tool_name)
            self._failure_counts[key] = self._failure_counts.get(key, 0) + 1

        return is_valid

    def get_overload_warning(self, proactive: bool = False) -> str | None:
        """Check if too many skills are active and return a warning if so.

        Args:
            proactive: If True, only returns warning if the count has increased
                      to avoid spamming every successful message.
        """
        count = len(self._active_skills)
        if count > self._overload_threshold:
            if proactive and count <= self._last_warning_count:
                return None

            self._last_warning_count = count
            skills_list = ", ".join(sorted(list(self._active_skills)))
            return (
                f"\n[COGNITIVE LOAD WARNING]\n"
                f"Active Skills: {count} ({skills_list}).\n"
                "Context clutter detected. Accuracy may decrease. Consider disabling unused skills."
            )
        return None

    def validate_or_raise(
        self,
        skill_name: str,
        tool_name: str,
        skill_permissions: list[str] | None = None,
        protocol_guidance: str | None = None,
    ) -> None:
        """
        Validate permission or raise SecurityError with protocol guidance.
        """
        if not self.validate(skill_name, tool_name, skill_permissions):
            # Check for overload to add to the error message
            overload_warning = self.get_overload_warning()
            guidance = protocol_guidance or ""
            if overload_warning:
                guidance = f"{guidance}\n{overload_warning}"

            raise SecurityError(
                skill_name=skill_name,
                tool_name=tool_name,
                required_permission=tool_name,
                protocol_guidance=guidance if guidance else None,
            )

    def is_rust_available(self) -> bool:
        """Check if Rust core is available."""
        return _RUST_AVAILABLE


__all__ = ["SecurityError", "SecurityValidator"]
