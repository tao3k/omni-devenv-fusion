"""
omni.core.config.loader - Configuration Loader

Loads and provides access to skill-related configuration from settings.yaml.

Usage:
    from omni.core.config.loader import get_skill_limits, get_filter_commands, get_active_preload_skills

    limits = get_skill_limits()
    limits.dynamic_tools  # 100

    # Get skills based on mode
    skills = get_active_preload_skills(mode="cli")  # Includes CLI extensions

    # Check if command should be filtered (supports glob patterns)
    if is_filtered("terminal.run_command"):
        print("Filtered!")
"""

from __future__ import annotations

import fnmatch

from omni.foundation.config.logging import get_logger
from pydantic import BaseModel

logger = get_logger("omni.core.config")


class SkillLimitsConfig(BaseModel):
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


class FilterCommandsConfig(BaseModel):
    """Configuration for filtering tools with glob pattern matching.

    Attributes:
        patterns: List of patterns (e.g., "terminal.*" or "!terminal.run_task")
    """

    patterns: list[str] = []


class SkillsConfig(BaseModel):
    """Skills configuration with base preload and CLI extensions."""

    preload: list[str] = []
    cli_extend: list[str] = []


class CommandOverride(BaseModel):
    """Configuration for a specific command override.

    Attributes:
        alias: The friendly name exposed to LLM (e.g., "save_memory")
        append_doc: Additional documentation/behavior hints for LLM
    """

    alias: str | None = None
    append_doc: str | None = None


class OverridesConfig(BaseModel):
    """Collection of command overrides for alias mapping.

    Structure:
        skills:
          overrides:
            memory.remember_insight:
              alias: "save_memory"
              append_doc: "..."
    """

    commands: dict[str, CommandOverride] = {}

    @property
    def aliases(self) -> dict[str, str]:
        """Build reverse lookup: alias -> canonical_name.

        Used for resolving incoming LLM calls.
        """
        return {
            config.alias: cmd_name for cmd_name, config in self.commands.items() if config.alias
        }


# Global config singletons
_limits_config: SkillLimitsConfig | None = None
_filter_config: FilterCommandsConfig | None = None
_skills_config: SkillsConfig | None = None
_overrides_config: OverridesConfig | None = None


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


def load_skills_config() -> SkillsConfig:
    """Load skills configuration (preload and cli.extend).

    Returns:
        SkillsConfig instance
    """
    global _skills_config
    if _skills_config is not None:
        return _skills_config

    try:
        from omni.foundation.config.settings import get_settings

        settings = get_settings()

        # Load base preload
        preload = settings.get("skills.preload", [])
        if not isinstance(preload, list):
            preload = []

        # Load CLI extensions
        cli_config = settings.get("skills.cli", {})
        cli_extend = cli_config.get("extend", []) if isinstance(cli_config, dict) else []

        _skills_config = SkillsConfig(
            preload=preload,
            cli_extend=cli_extend if isinstance(cli_extend, list) else [],
        )

        logger.debug(f"Loaded skills config: preload={preload}, cli_extend={cli_extend}")
        return _skills_config

    except Exception as e:
        logger.warning(f"Failed to load skills config, using defaults: {e}")
        _skills_config = SkillsConfig()
        return _skills_config


def get_active_preload_skills(mode: str = "default") -> list[str]:
    """Get the calculated list of skills to preload based on mode.

    Args:
        mode: "default" (MCP Server) or "cli" (Omni Run)

    Returns:
        Combined list of skill names (deduplicated)
    """
    config = load_skills_config()

    # Base skills (always loaded)
    skills = set(config.preload)

    # Extend for CLI mode
    if mode == "cli":
        skills.update(config.cli_extend)

    return list(skills)


def load_filter_commands() -> FilterCommandsConfig:
    """Load filter commands configuration from settings.yaml.

    Returns:
        FilterCommandsConfig instance with patterns list
    """
    global _filter_config
    if _filter_config is not None:
        return _filter_config

    try:
        from omni.foundation.config.settings import get_settings

        settings = get_settings()

        # Handle both list and dict formats
        raw = settings.get("skills.filter_commands", [])

        if isinstance(raw, dict):
            patterns = raw.get("patterns", raw.get("commands", []))
        elif isinstance(raw, list):
            patterns = raw
        else:
            patterns = []

        _filter_config = FilterCommandsConfig(patterns=patterns)
        logger.debug(f"Loaded filter patterns: {patterns}")
        return _filter_config

    except Exception as e:
        logger.warning(f"Failed to load filter commands config, using defaults: {e}")
        _filter_config = FilterCommandsConfig()
        return _filter_config


def is_filtered(command: str) -> bool:
    """Check if a command should be filtered using Glob patterns & exclusions.

    Logic:
    1. Check if command matches any BLOCK pattern (e.g., "terminal.*").
    2. If blocked, check if it matches any ALLOW pattern (e.g., "!terminal.run_task").
    3. If allowed, return False (not filtered).

    Args:
        command: Full command name (e.g., "terminal.run_command")

    Returns:
        True if command should be filtered from MCP tools
    """
    config = load_filter_commands()

    # 1. Check if explicitly blocked
    blocked = False
    for pattern in config.patterns:
        if pattern.startswith("!"):
            continue  # Skip allow patterns for blocking check
        if fnmatch.fnmatch(command, pattern):
            blocked = True
            break

    if not blocked:
        return False  # Not blocked by any rule

    # 2. Check for exceptions (Allow list)
    for pattern in config.patterns:
        if not pattern.startswith("!"):
            continue
        # Remove '!' prefix and check match
        allow_pattern = pattern[1:]
        if fnmatch.fnmatch(command, allow_pattern):
            return False  # Whitelisted exception

    return True  # Blocked with no exception


def load_command_overrides() -> OverridesConfig:
    """Load command overrides from settings.yaml.

    This enables "Configuration over Convention" for tool naming.
    LLM sees friendly aliases (save_memory) while kernel uses canonical names
    (memory.remember_insight).

    Structure:
        skills:
          overrides:
            memory.remember_insight:
              alias: "save_memory"
              append_doc: "..."

    Returns:
        OverridesConfig instance with command overrides
    """
    global _overrides_config
    if _overrides_config is not None:
        return _overrides_config

    try:
        from omni.foundation.config.settings import get_settings

        settings = get_settings()

        # Load raw dict from skills.overrides
        raw_overrides = settings.get("skills.overrides", {})

        if not isinstance(raw_overrides, dict):
            _overrides_config = OverridesConfig()
            return _overrides_config

        parsed_commands = {}
        for cmd_name, data in raw_overrides.items():
            if isinstance(data, dict):
                parsed_commands[cmd_name] = CommandOverride(
                    alias=data.get("alias"), append_doc=data.get("append_doc")
                )

        _overrides_config = OverridesConfig(commands=parsed_commands)
        logger.debug(f"Loaded {len(parsed_commands)} command overrides")
        return _overrides_config

    except Exception as e:
        logger.warning(f"Failed to load command overrides: {e}")
        _overrides_config = OverridesConfig()
        return _overrides_config


def resolve_alias(alias: str) -> str | None:
    """Resolve an alias to its canonical command name.

    Args:
        alias: The alias name (e.g., "save_memory")

    Returns:
        The canonical command name (e.g., "memory.remember_insight"), or None if not found
    """
    config = load_command_overrides()
    return config.aliases.get(alias)


def get_command_display(cmd_name: str) -> tuple[str, str]:
    """Get the display name and description for a command.

    Applies alias and append_doc overrides for LLM-facing interface.

    Args:
        cmd_name: The canonical command name

    Returns:
        Tuple of (display_name, display_description)
    """
    config = load_command_overrides()

    if cmd_name in config.commands:
        override = config.commands[cmd_name]
        display_name = override.alias or cmd_name
        base_desc = f"Execute {cmd_name}"
        extra_doc = override.append_doc
        display_desc = f"{base_desc} {extra_doc}" if extra_doc else base_desc
        return display_name, display_desc

    return cmd_name, f"Execute {cmd_name}"


def reset_config() -> None:
    """Reset config singletons (for testing)."""
    global _limits_config, _filter_config, _skills_config, _overrides_config
    _limits_config = None
    _filter_config = None
    _skills_config = None
    _overrides_config = None


__all__ = [
    "CommandOverride",
    "FilterCommandsConfig",
    "OverridesConfig",
    "SkillLimitsConfig",
    "SkillsConfig",
    "get_active_preload_skills",
    "get_command_display",
    "is_filtered",
    "load_command_overrides",
    "load_filter_commands",
    "load_skills_config",
    "load_skill_limits",
    "reset_config",
    "resolve_alias",
]
