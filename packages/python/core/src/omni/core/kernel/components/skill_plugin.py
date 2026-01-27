"""
kernel/components/skill_plugin.py - Skill Plugin Interface

Skill Plugin interface for integrating Skills into the Kernel microkernel architecture:
- Unified lifecycle management (initialize -> ready -> shutdown)
- Command registration
- Discovery and invocation through the Kernel

Usage:
    from agent.core.kernel.components.skill_plugin import ISkillPlugin

    class MySkill(ISkillPlugin):
        @property
        def skill_name(self) -> str:
            return "my_skill"

        @property
        def version(self) -> str:
            return "1.0.0"

        async def initialize(self):
            # Setup code
            pass
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ISkillPlugin(ABC):
    """Skill plugin interface - integrated into the Kernel microkernel architecture.

    All Skills should implement this interface to participate in Kernel lifecycle management.
    For existing skills, maintain Trinity Architecture (scripts/ + @skill_command),
    automatically wrapped as plugins by SkillLoader.
    """

    # =============================================================================
    # Required Properties
    # =============================================================================

    @property
    @abstractmethod
    def skill_name(self) -> str:
        """Skill name (e.g., 'git', 'memory', 'filesystem')"""

    @property
    @abstractmethod
    def version(self) -> str:
        """Skill version (e.g., '1.0.0')"""

    # =============================================================================
    # Optional Properties
    # =============================================================================

    @property
    def description(self) -> str:
        """Skill short description."""
        return f"Skill: {self.skill_name}"

    @property
    def category(self) -> str:
        """Skill category (e.g., 'tools', 'storage', 'workflow')"""
        return "general"

    # =============================================================================
    # Lifecycle Methods
    # =============================================================================

    async def initialize(self) -> None:
        """Initialization stage - called after Skill is loaded, before ready.

        Used for:
        - Loading configuration
        - Establishing database connections
        - Initializing resources
        """
        pass

    async def ready(self) -> None:
        """Ready stage - called before Skill is ready to accept requests.

        Used for:
        - Validating dependencies
        - Warming up caches
        """
        pass

    async def shutdown(self) -> None:
        """Shutdown stage - called before Skill is unloaded.

        Used for:
        - Saving state
        - Closing connections
        - Cleaning up resources
        """
        pass

    async def reload(self) -> None:
        """Reload - called after Skill configuration changes.

        Default implementation: shutdown -> initialize -> ready
        """
        await self.shutdown()
        await self.initialize()
        await self.ready()

    # =============================================================================
    # Command Registration
    # =============================================================================

    def get_commands(self) -> dict[str, Any]:
        """Get command mapping.

        Returns:
            Mapping of command names to functions
        """
        return {}

    def get_tools(self) -> list[dict[str, Any]]:
        """Get MCP tool definitions.

        Returns:
            List of tool definitions (conforming to MCP schema)
        """
        return []

    # =============================================================================
    # Metadata
    # =============================================================================

    def get_metadata(self) -> dict[str, Any]:
        """Get Skill metadata.

        Returns:
            Dictionary containing name, version, description, etc.
        """
        return {
            "name": self.skill_name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
        }


class SkillPluginWrapper(ISkillPlugin):
    """Wrapper for wrapping existing Skill scripts as plugins.

    Automatically extracts @skill_command functions from scripts/*.py,
    wrapping them into a unified plugin interface.
    """

    def __init__(
        self,
        skill_name: str,
        scripts_dir: Path,
        version: str = "1.0.0",
    ) -> None:
        """Initialize the Skill plugin wrapper.

        Args:
            skill_name: Skill name
            scripts_dir: Path to scripts/ directory
            version: Skill version
        """
        self._skill_name = skill_name
        self._scripts_dir = scripts_dir
        self._version = version
        self._commands: dict[str, Any] = {}
        self._loaded = False

    @property
    def skill_name(self) -> str:
        return self._skill_name

    @property
    def version(self) -> str:
        return self._version

    @property
    def description(self) -> str:
        """Read description from SKILL.md or use default."""
        skill_md = self._scripts_dir.parent / "SKILL.md"
        if skill_md.exists():
            try:
                import frontmatter

                with open(skill_md, encoding="utf-8") as f:
                    post = frontmatter.load(f)
                return post.metadata.get("description", f"Skill: {self._skill_name}")
            except Exception:
                pass
        return f"Skill: {self._skill_name}"

    async def initialize(self) -> None:
        """Load Skill scripts and extract commands."""
        if self._loaded:
            return

        # Import all scripts in the skill's scripts directory
        from .skill_loader import load_skill_scripts

        self._commands = await load_skill_scripts(self._skill_name, self._scripts_dir)
        self._loaded = True

    def get_commands(self) -> dict[str, Any]:
        """Get loaded commands."""
        return self._commands

    def get_tools(self) -> list[dict[str, Any]]:
        """Generate MCP tool definitions."""
        tools = []
        for name, func in self._commands.items():
            config = getattr(func, "_skill_config", None)
            if config:
                tools.append(
                    {
                        "name": f"{self._skill_name}.{name}",
                        "description": config.get("description", f"Execute {name}"),
                        "inputSchema": config.get("input_schema", {"type": "object"}),
                    }
                )
        return tools

    def get_metadata(self) -> dict[str, Any]:
        """Get Skill metadata."""
        metadata = super().get_metadata()
        metadata.update(
            {
                "scripts_dir": str(self._scripts_dir),
                "command_count": len(self._commands),
            }
        )
        return metadata
