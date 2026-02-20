"""Validation registration helpers for ToolsLoader."""

from __future__ import annotations

from typing import Any


def register_command_for_validation(full_name: str, cmd: Any) -> None:
    """Register command config in validation registry (best effort)."""
    try:
        from omni.core.skills.validation import register_skill_command

        config = getattr(cmd, "_skill_config", None)
        if config and isinstance(config, dict):
            register_skill_command(full_name, config)
    except Exception:
        # Validation module may not be available - silent fail is OK.
        pass
