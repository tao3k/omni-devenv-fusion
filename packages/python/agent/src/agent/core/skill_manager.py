"""
src/agent/core/skill_manager.py
Phase 25.3: The "Trinity" Architecture

Integrates:
- Code (Hot-Reloading): Lazy mtime-based reload, millisecond response
- Context (RepomixCache): XML-packed skill context for LLM understanding
- State (Registry): Skill registry with metadata

Architecture:
- @skill_command decorator marks functions with metadata
- SkillManager maintains skill registry with mtime tracking
- RepomixCache per skill for deep context injection
- Single omni tool handles all operations

Usage:
    manager = SkillManager()
    manager.load_skills()
    result = await manager.run("git", "status", {})
"""

import asyncio
import importlib
import importlib.util
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from common.settings import get_setting
from common.config_paths import get_project_root
from common.mcp_core.lazy_cache import RepomixCache

logger = logging.getLogger(__name__)

# Get skills directory from settings.yaml
SKILLS_DIR = get_project_root() / get_setting("skills.path", "assets/skills")


@dataclass
class SkillCommand:
    """Represents a single command exposed by a skill."""

    name: str
    func: Callable[..., str]
    description: str
    category: str = "general"


@dataclass
class Skill:
    """Represents a loaded skill with its commands and context cache."""

    name: str
    module_name: str
    path: Path
    mtime: float
    commands: Dict[str, SkillCommand] = field(default_factory=dict)
    # Trinity: Context Cache for deep skill understanding
    context_cache: Optional[RepomixCache] = None


class SkillManager:
    """
    Central command manager that scans skills and builds registry.

    Phase 25.3 Trinity Architecture:
    - Code (Hot-Reloading): mtime-based lazy reload
    - Context (RepomixCache): XML-packed skill context
    - State (Registry): Skill metadata and commands

    Key Methods:
        load_skills() - Bootstrap all skills
        get_command(skill_name, command_name) - Get with hot-reload check
        run(skill_name, command_name, args) - Execute command
        _ensure_fresh(skill_name) - Hot-reload if file modified
        _get_skill_context(skill_name) - Get XML context via Repomix
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        """
        Initialize SkillManager.

        Args:
            skills_dir: Path to skills directory. Defaults to settings.yaml value.
        """
        if skills_dir is None:
            self.skills_dir = SKILLS_DIR
        else:
            self.skills_dir = Path(skills_dir)

        self.skills: Dict[str, Skill] = {}
        self._skills_loaded = False

    def _discover_skill_directories(self) -> List[Path]:
        """Discover all skill directories in the skills folder."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return []

        skill_dirs = []
        for entry in self.skills_dir.iterdir():
            if entry.is_dir():
                tools_path = entry / "tools.py"
                if tools_path.exists():
                    skill_dirs.append(entry)
                else:
                    logger.debug(f"Skipping {entry.name}: no tools.py found")

        return skill_dirs

    def _load_skill_module(self, skill_dir: Path) -> Optional[str]:
        """
        Low-level module loader with reload support.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            Module name if successful, None otherwise
        """
        import types

        tools_path = skill_dir / "tools.py"
        module_name = f"agent.skills.{skill_dir.name}.tools"

        try:
            # Pre-create parent packages in sys.modules for nested imports to work
            skills_path = skill_dir.parent  # e.g., assets/skills

            # Find the agent source root (packages/python/agent/src/agent)
            # This is where decorators.py lives
            project_root = get_project_root()
            agent_src_path = project_root / "packages/python/agent/src/agent"

            # Create and register 'agent' package if not exists
            if "agent" not in sys.modules:
                agent_pkg = types.ModuleType("agent")
                agent_pkg.__path__ = [str(agent_src_path)]
                agent_pkg.__file__ = str(agent_src_path / "__init__.py")
                sys.modules["agent"] = agent_pkg

            # Create and register 'agent.skills' package if not exists
            if "agent.skills" not in sys.modules:
                skills_pkg = types.ModuleType("agent.skills")
                skills_pkg.__path__ = [str(skills_path)]  # For finding skill modules
                skills_pkg.__file__ = str(skills_path / "__init__.py")
                sys.modules["agent.skills"] = skills_pkg
                sys.modules["agent"].skills = skills_pkg

            # Create and register 'agent.skills.decorators' module if not exists
            decorators_path = agent_src_path / "skills" / "decorators.py"
            if "agent.skills.decorators" not in sys.modules and decorators_path.exists():
                decorators_spec = importlib.util.spec_from_file_location(
                    "agent.skills.decorators", decorators_path
                )
                decorators_module = importlib.util.module_from_spec(decorators_spec)
                sys.modules["agent.skills.decorators"] = decorators_module
                decorators_spec.loader.exec_module(decorators_module)
                sys.modules["agent.skills"].decorators = decorators_module

            spec = importlib.util.spec_from_file_location(module_name, tools_path)
            if spec is None or spec.loader is None:
                logger.error(f"Could not create spec for {module_name}")
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            return module_name

        except Exception as e:
            logger.error(f"Failed to load skill {skill_dir.name}: {e}")
            return None

    def _extract_commands(self, module, skill_name: str) -> Dict[str, SkillCommand]:
        """
        Extract commands from a skill module.

        Supports two patterns:
        1. @skill_command decorators (Phase 25+)
        2. EXPOSED_COMMANDS dictionary (legacy, for backward compatibility)

        Args:
            module: The loaded skill module
            skill_name: Name of the skill for logging

        Returns:
            Dictionary of command name -> SkillCommand
        """
        import inspect

        commands = {}

        # Debug: Count functions in module
        all_funcs = [n for n, o in inspect.getmembers(module) if inspect.isfunction(o)]
        logger.debug(f"[{skill_name}] Found {len(all_funcs)} functions in module")

        # Method 1: Check for @skill_command decorated functions
        for name, obj in inspect.getmembers(module):
            if inspect.isfunction(obj):
                has_marker = getattr(obj, "_is_skill_command", False)
                if has_marker:
                    config = obj._skill_config
                    cmd_name = config.get("name") or name

                    commands[cmd_name] = SkillCommand(
                        name=cmd_name,
                        func=obj,
                        description=config.get("description", ""),
                        category=config.get("category", "general"),
                    )
                    logger.debug(f"[{skill_name}] Loaded decorated command: {cmd_name}")

        # Debug: List functions with markers
        if not commands:
            funcs_with_marker = [
                (n, getattr(o, "_is_skill_command", None))
                for n, o in inspect.getmembers(module)
                if inspect.isfunction(o)
            ]
            logger.debug(f"[{skill_name}] Functions with markers: {funcs_with_marker[:5]}...")

        # Method 2: Check for EXPOSED_COMMANDS (legacy/transition)
        if hasattr(module, "EXPOSED_COMMANDS"):
            exposed = module.EXPOSED_COMMANDS
            if isinstance(exposed, dict):
                for cmd_name, cmd_info in exposed.items():
                    # Skip if already loaded via decorator
                    if cmd_name in commands:
                        continue

                    if isinstance(cmd_info, dict):
                        func = cmd_info.get("func")
                        description = cmd_info.get("description", "")
                        category = cmd_info.get("category", "general")

                        if callable(func):
                            commands[cmd_name] = SkillCommand(
                                name=cmd_name,
                                func=func,
                                description=description,
                                category=category,
                            )
                            logger.debug(f"[{skill_name}] Loaded from EXPOSED_COMMANDS: {cmd_name}")
                        else:
                            logger.warning(
                                f"[{skill_name}] Command {cmd_name} has no callable func"
                            )
                    else:
                        logger.warning(f"[{skill_name}] Invalid command format for {cmd_name}")

        if not commands:
            logger.warning(f"[{skill_name}] No commands found")

        return commands

    def _register_skill(self, skill_dir: Path) -> Optional[Skill]:
        """
        Register or reload a skill (hot-reload aware).

        Args:
            skill_dir: Path to the skill directory

        Returns:
            Skill object if successful, None otherwise
        """
        skill_name = skill_dir.name
        tools_path = skill_dir / "tools.py"
        module_name = f"agent.skills.{skill_name}.tools"

        # Get current modification time
        try:
            current_mtime = tools_path.stat().st_mtime
        except FileNotFoundError:
            logger.error(f"Skill file not found: {tools_path}")
            return None

        # Remove old module from sys.modules for clean reload
        # This avoids importlib.reload issues with dynamically created packages
        if module_name in sys.modules:
            del sys.modules[module_name]
        # Also remove parent package if it exists
        parent_name = f"agent.skills.{skill_name}"
        if parent_name in sys.modules:
            del sys.modules[parent_name]

        # Load module (fresh load handles parent package creation)
        loaded_name = self._load_skill_module(skill_dir)
        if loaded_name is None:
            return None
        module = sys.modules.get(loaded_name)
        if module is None:
            return None

        # Extract commands
        commands = self._extract_commands(module, skill_name)

        # Check for local repomix.json
        config_path = skill_dir / "repomix.json"
        if not config_path.exists():
            config_path = None

        # Create or update skill
        skill = Skill(
            name=skill_name,
            module_name=module_name,
            path=tools_path,
            mtime=current_mtime,
            commands=commands,
            # Initialize RepomixCache (lazy - won't execute until get() called)
            context_cache=RepomixCache(
                target_path=skill_dir,
                config_path=config_path,
            ),
        )

        self.skills[skill_name] = skill
        logger.info(f"🧩 Skill Loaded: {skill_name} ({len(commands)} cmds)")
        return skill

    def _ensure_fresh(self, skill_name: str) -> bool:
        """
        🔥 The Hot-Load Magic.

        Checks file modification time and reloads if necessary.
        This is called before every command execution.

        Args:
            skill_name: Name of the skill to check

        Returns:
            True if skill is loaded and fresh, False if not found
        """
        # 1. Check if skill exists on disk
        skill_path = self.skills_dir / skill_name
        if not skill_path.exists():
            logger.debug(f"Skill not found on disk: {skill_name}")
            return False

        tools_path = skill_path / "tools.py"

        # 2. If not in memory, load it
        if skill_name not in self.skills:
            self._register_skill(skill_path)
            return skill_name in self.skills

        # 3. If in memory, check freshness
        skill = self.skills[skill_name]
        try:
            current_mtime = tools_path.stat().st_mtime
            if current_mtime > skill.mtime:
                logger.info(f"🔥 Hot-Reloading Skill: {skill_name}")
                self._register_skill(skill_path)
        except FileNotFoundError:
            logger.warning(f"Skill file deleted: {skill_name}")
            # Keep the cached version, but mark as potentially stale
            pass

        return True

    def load_skills(self) -> Dict[str, Skill]:
        """
        Bootstrap: Load all skills from the skills directory.

        This is called once at startup.

        Returns:
            Dictionary of skill name -> Skill object
        """
        if self._skills_loaded:
            logger.info("Skills already loaded, returning cached skills")
            return self.skills

        logger.info(f"Loading skills from {self.skills_dir}")

        skill_dirs = self._discover_skill_directories()
        logger.info(f"Found {len(skill_dirs)} skill directories")

        for skill_dir in skill_dirs:
            self._register_skill(skill_dir)

        self._skills_loaded = True
        logger.info(f"Skill loading complete. Loaded {len(self.skills)} skills")

        return self.skills

    def get_command(self, skill_name: str, command_name: str) -> Optional[SkillCommand]:
        """
        Get a specific command from a skill (with hot-reload check).

        Args:
            skill_name: Name of the skill (e.g., "git")
            command_name: Name of the command (e.g., "git_status_report")

        Returns:
            SkillCommand if found, None otherwise
        """
        # Ensure skill is fresh (hot-reload check)
        if not self._ensure_fresh(skill_name):
            logger.warning(f"Skill not found: {skill_name}")
            return None

        skill = self.skills.get(skill_name)
        if skill is None:
            return None

        command = skill.commands.get(command_name)
        if command is None:
            logger.debug(f"Command not found: {skill_name}.{command_name}")
            return None

        return command

    async def run(
        self,
        skill_name: str,
        command_name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute a command from a skill.

        Trinity Entry Point:
        - help: Returns XML context via RepomixCache
        - Other: Executes the command function

        Args:
            skill_name: Name of the skill (e.g., "git")
            command_name: Name of the command (e.g., "git_status_report")
            args: Optional arguments to pass to the command function

        Returns:
            String result from the command execution
        """
        # Trinity: Context command
        if command_name == "help":
            return self._get_skill_context(skill_name)

        command = self.get_command(skill_name, command_name)
        if command is None:
            return f"Error: Command {skill_name}.{command_name} not found"

        try:
            func = command.func
            args = args or {}

            # Native async/await - no ThreadPoolExecutor needed
            if asyncio.iscoroutinefunction(func):
                result = await func(**args)
            else:
                result = func(**args)

            return str(result)

        except TypeError as e:
            return f"Error executing {skill_name}.{command_name}: {e}"
        except Exception as e:
            logger.error(f"Error executing {skill_name}.{command_name}: {e}")
            return f"Error: {e}"

    def _get_skill_context(self, skill_name: str) -> str:
        """
        Trinity: Get deep skill context via RepomixCache.

        Returns XML-packed skill context including:
        - Code (tools.py)
        - Documentation (prompts.md, guide.md, workflows)
        - Configuration (repomix.json, cog.toml)

        Args:
            skill_name: Name of the skill

        Returns:
            XML-packed skill context or error message
        """
        # Ensure skill is registered
        if not self._ensure_fresh(skill_name):
            return f"Skill '{skill_name}' not found"

        skill = self.skills.get(skill_name)
        if skill is None:
            return f"Skill '{skill_name}' not found"

        # Use the skill's RepomixCache
        if skill.context_cache is None:
            # Fallback: should not happen, but handle gracefully
            skill_dir = self.skills_dir / skill_name
            config_path = skill_dir / "repomix.json"
            if not config_path.exists():
                config_path = None
            skill.context_cache = RepomixCache(
                target_path=skill_dir,
                config_path=config_path,
            )

        xml_content = skill.context_cache.get()

        if not xml_content:
            # Fallback to guide.md if repomix fails
            skill_dir = self.skills_dir / skill_name
            guide_path = skill_dir / "guide.md"
            if guide_path.exists():
                return f"# {skill_name}\n\n{guide_path.read_text()}"
            return f"# {skill_name}\n\nNo guide.md or repomix context available."

        return xml_content

    def list_available_skills(self) -> List[str]:
        """List all loaded skills."""
        return list(self.skills.keys())

    def list_commands(self, skill_name: str) -> List[str]:
        """List all commands for a skill."""
        if not self._ensure_fresh(skill_name):
            return []

        skill = self.skills.get(skill_name)
        if skill is None:
            return []

        return list(skill.commands.keys())

    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a skill."""
        if not self._ensure_fresh(skill_name):
            return None

        skill = self.skills.get(skill_name)
        if skill is None:
            return None

        return {
            "name": skill.name,
            "module_name": skill.module_name,
            "loaded": True,
            "command_count": len(skill.commands),
            "commands": list(skill.commands.keys()),
            "mtime": skill.mtime,
        }

    def reload_skill(self, skill_name: str) -> bool:
        """
        Force reload a skill (bypass mtime check).

        Args:
            skill_name: Name of the skill to reload

        Returns:
            True if successful, False otherwise
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            logger.error(f"Skill not found: {skill_name}")
            return False

        # Remove old module from sys.modules
        module_name = f"agent.skills.{skill_name}.tools"
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Remove old skill from registry
        if skill_name in self.skills:
            del self.skills[skill_name]

        # Reload
        return self._register_skill(skill_dir) is not None


# Global skill manager instance
_skill_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """
    Get the global SkillManager instance.

    Returns:
        Initialized SkillManager
    """
    global _skill_manager
    if _skill_manager is None:
        _skill_manager = SkillManager()
        _skill_manager.load_skills()
    return _skill_manager


def run_skill_command(
    skill_name: str,
    command_name: str,
    args: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Convenience function to run a skill command.

    Args:
        skill_name: Name of the skill
        command_name: Name of the command
        args: Optional arguments

    Returns:
        Command result as string
    """
    manager = get_skill_manager()
    return manager.run(skill_name, command_name, args)
