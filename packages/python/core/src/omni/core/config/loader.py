"""
omni.core.config.loader - Configuration Loader

Loads and provides access to skill-related configuration from settings.yaml.

Usage:
    from omni.core.config.loader import get_skill_limits, get_filter_commands

    limits = get_skill_limits()
    limits.dynamic_tools  # 15
    limits.core_min       # 3
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from omni.foundation.config.logging import get_logger

logger = get_logger("omni.core.config")


@dataclass
class SkillLimitsConfig:
    """Configuration for dynamic tool loading limits.

    Attributes:
        dynamic_tools: Maximum number of dynamic tools per request
        core_min: Minimum guaranteed core tools
        rerank_threshold: Threshold for re-ranking tools
        schema_cache_ttl: TTL for tool schema cache in seconds
        auto_optimize: Enable automatic context optimization
    """

    dynamic_tools: int = 15
    core_min: int = 3
    rerank_threshold: int = 20
    schema_cache_ttl: int = 300
    auto_optimize: bool = True


@dataclass
class FilterCommandsConfig:
    """Configuration for commands to filter from core tools."""

    commands: list[str] = field(default_factory=list)


# Global config singletons
_limits_config: SkillLimitsConfig | None = None
_filter_config: FilterCommandsConfig | None = None


def load_skill_limits() -> SkillLimitsConfig:
    """Load skill limits configuration from settings.yaml.

    Returns:
        SkillLimitsConfig instance with loaded values or defaults
    """
    global _limits_config
    if _limits_config is not None:
        return _limits_config

    try:
        from omni.foundation.config.settings import get_settings

        settings = get_settings()

        _limits_config = SkillLimitsConfig(
            dynamic_tools=settings.get("skills.limits.dynamic_tools", 15),
            core_min=settings.get("skills.limits.core_min", 3),
            rerank_threshold=settings.get("skills.limits.rerank_threshold", 20),
            schema_cache_ttl=settings.get("skills.limits.schema_cache_ttl", 300),
            auto_optimize=settings.get("skills.limits.auto_optimize", True),
        )

        logger.debug(f"Loaded skill limits: {_limits_config}")
        return _limits_config

    except Exception as e:
        logger.warning(f"Failed to load skill limits config, using defaults: {e}")
        _limits_config = SkillLimitsConfig()
        return _limits_config


def load_filter_commands() -> FilterCommandsConfig:
    """Load filter commands configuration from settings.yaml.

    Returns:
        FilterCommandsConfig instance with filtered commands list
    """
    global _filter_config
    if _filter_config is not None:
        return _filter_config

    try:
        from omni.foundation.config.settings import get_settings

        settings = get_settings()

        # Handle both list and dict formats
        filter_list = settings.get("skills.filter_commands", [])

        if isinstance(filter_list, dict):
            commands = filter_list.get("commands", [])
        elif isinstance(filter_list, list):
            commands = filter_list
        else:
            commands = []

        _filter_config = FilterCommandsConfig(commands=commands)
        logger.debug(f"Loaded filter commands: {commands}")
        return _filter_config

    except Exception as e:
        logger.warning(f"Failed to load filter commands config, using defaults: {e}")
        _filter_config = FilterCommandsConfig()
        return _filter_config


def reset_config() -> None:
    """Reset config singletons (for testing)."""
    global _limits_config, _filter_config
    _limits_config = None
    _filter_config = None


def is_filtered(command: str) -> bool:
    """Check if a command should be filtered from core tools.

    Args:
        command: Full command name (e.g., "terminal.run_command")

    Returns:
        True if command should be filtered
    """
    filter_config = load_filter_commands()
    return command in filter_config.commands


__all__ = [
    "SkillLimitsConfig",
    "FilterCommandsConfig",
    "load_skill_limits",
    "load_filter_commands",
    "reset_config",
    "is_filtered",
]
