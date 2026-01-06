"""
src/agent/core/skill_manager.py
Omni CLI - Single Entry Point for All Skills.

Phase 25.1: Macro System (Skill Decorators + DI)
Replaces Phase 25's manual EXPOSED_COMMANDS with @skill_command decorators.

Architecture:
- @skill_command decorator marks functions with metadata and DI support
- SkillManager scans skills and builds registry from decorated functions
- Built-in help macro automatically reads guide.md
- Single omni tool handles all operations

Usage:
    skill_manager = SkillManager()
    skill_manager.load_skills()
    result = await skill_manager.run("git", "status", {})
"""

import asyncio
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

from common.settings import get_setting
from common.config_paths import get_project_root

logger = logging.getLogger(__name__)

# Get skills directory from settings.yaml
SKILLS_DIR = get_project_root() / get_setting("skills.path", "agent/skills")


@dataclass
class SkillCommand:
    """Represents a single command exposed by a skill."""

    name: str
    func: Callable[..., str]
    description: str
    category: str = "general"


@dataclass
class Skill:
    """Represents a loaded skill with its commands."""

    name: str
    module_name: str
    commands: Dict[str, SkillCommand] = field(default_factory=dict)
    loaded: bool = False


class SkillManager:
    """
    Central command manager that scans skills and builds registry.

    Key Methods:
        load_skills() - Scan and load all skills from agent/skills/
        get_command(skill_name, command_name) - Get a specific command
        run(skill_name, command_name, args) - Execute a command
        list_available_skills() - List all loaded skills
        list_commands(skill_name) - List commands for a skill
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
        Dynamically load a skill module from tools.py.

        Args:
            skill_dir: Path to the skill directory

        Returns:
            Module name if successful, None otherwise
        """
        import types

        tools_path = skill_dir / "tools.py"
        module_name = f"agent.skills.{skill_dir.name}.tools"

        # Check if already loaded
        if module_name in sys.modules:
            return module_name

        try:
            # Pre-create parent packages in sys.modules for nested imports to work
            # This allows 'from agent.skills.decorators import ...' to work
            skills_path = skill_dir.parent
            agent_path = skills_path.parent

            # Create and register 'agent' package if not exists
            if "agent" not in sys.modules:
                agent_pkg = types.ModuleType("agent")
                agent_pkg.__path__ = [str(agent_path)]
                agent_pkg.__file__ = str(agent_path / "__init__.py")
                sys.modules["agent"] = agent_pkg

            # Create and register 'agent.skills' package if not exists
            if "agent.skills" not in sys.modules:
                skills_pkg = types.ModuleType("agent.skills")
                skills_pkg.__path__ = [str(skills_path)]
                skills_pkg.__file__ = str(skills_path / "__init__.py")
                sys.modules["agent.skills"] = skills_pkg
                sys.modules["agent"].skills = skills_pkg

            # Create and register 'agent.skills.decorators' module if not exists and file exists
            decorators_path = skills_path / "decorators.py"
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

    def load_skills(self) -> Dict[str, Skill]:
        """
        Scan and load all skills from the skills directory.

        This method:
        1. Discovers all skill directories
        2. Loads each skill's tools.py module
        3. Extracts EXPOSED_COMMANDS from each module
        4. Builds the skill registry

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
            skill_name = skill_dir.name

            # Load the module
            module_name = self._load_skill_module(skill_dir)
            if module_name is None:
                continue

            # Get the module from sys.modules
            module = sys.modules.get(module_name)
            if module is None:
                continue

            # Extract commands
            commands = self._extract_commands(module, skill_name)

            if commands:
                skill = Skill(
                    name=skill_name,
                    module_name=module_name,
                    commands=commands,
                    loaded=True,
                )
                self.skills[skill_name] = skill
                logger.info(f"Loaded skill: {skill_name} with {len(commands)} commands")
            else:
                logger.warning(f"Skill {skill_name} has no commands, skipping")

        self._skills_loaded = True
        logger.info(f"Skill loading complete. Loaded {len(self.skills)} skills")

        return self.skills

    def get_command(self, skill_name: str, command_name: str) -> Optional[SkillCommand]:
        """
        Get a specific command from a skill.

        Args:
            skill_name: Name of the skill (e.g., "git")
            command_name: Name of the command (e.g., "git_status_report")

        Returns:
            SkillCommand if found, None otherwise
        """
        skill = self.skills.get(skill_name)
        if skill is None:
            logger.warning(f"Skill not found: {skill_name}")
            return None

        command = skill.commands.get(command_name)
        if command is None:
            logger.warning(f"Command not found: {skill_name}.{command_name}")
            return None

        return command

    async def run(
        self,
        skill_name: str,
        command_name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute a command from a skill (Async Native).

        This is the main entry point for executing skill commands.

        Built-in commands:
            - help: Returns guide.md content for the skill

        Args:
            skill_name: Name of the skill (e.g., "git")
            command_name: Name of the command (e.g., "git_status_report")
            args: Optional arguments to pass to the command function

        Returns:
            String result from the command execution
        """
        # Built-in: help command returns guide.md
        if command_name == "help":
            return self._get_skill_guide(skill_name)

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
                # Sync function - FastMCP handles this gracefully
                result = func(**args)

            return str(result)

        except TypeError as e:
            # Handle missing arguments
            return f"Error executing {skill_name}.{command_name}: {e}"
        except Exception as e:
            logger.error(f"Error executing {skill_name}.{command_name}: {e}")
            return f"Error: {e}"

    def _get_skill_guide(self, skill_name: str) -> str:
        """
        Get skill guide content (reads guide.md automatically).

        This is a macro - every skill can use @omni("skill.help") to get
        its guide.md content without defining a help function.

        Args:
            skill_name: Name of the skill

        Returns:
            Guide content or error message
        """
        skill = self.skills.get(skill_name)
        if skill is None:
            return f"Skill '{skill_name}' not found"

        # guide.md is in the skill directory
        guide_path = self.skills_dir / skill_name / "guide.md"
        if guide_path.exists():
            return guide_path.read_text()
        else:
            return f"# {skill_name}\n\nNo guide.md found for this skill."

    def list_available_skills(self) -> List[str]:
        """
        List all loaded skills.

        Returns:
            List of skill names
        """
        return list(self.skills.keys())

    def list_commands(self, skill_name: str) -> List[str]:
        """
        List all commands for a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            List of command names
        """
        skill = self.skills.get(skill_name)
        if skill is None:
            return []

        return list(skill.commands.keys())

    def get_skill_info(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Dictionary with skill info or None if not found
        """
        skill = self.skills.get(skill_name)
        if skill is None:
            return None

        return {
            "name": skill.name,
            "module_name": skill.module_name,
            "loaded": skill.loaded,
            "command_count": len(skill.commands),
            "commands": list(skill.commands.keys()),
        }

    def reload_skill(self, skill_name: str) -> bool:
        """
        Reload a single skill.

        Args:
            skill_name: Name of the skill to reload

        Returns:
            True if successful, False otherwise
        """
        skill_dir = self.skills_dir / skill_name
        tools_path = skill_dir / "tools.py"

        if not tools_path.exists():
            logger.error(f"Skill not found: {skill_name}")
            return False

        module_name = f"agent.skills.{skill_name}.tools"

        # Remove old module from sys.modules
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Remove old skill from registry
        if skill_name in self.skills:
            del self.skills[skill_name]

        # Reload the module
        module_name = self._load_skill_module(skill_dir)
        if module_name is None:
            return False

        module = sys.modules.get(module_name)
        if module is None:
            return False

        # Extract commands
        commands = self._extract_commands(module, skill_name)

        if commands:
            skill = Skill(
                name=skill_name,
                module_name=module_name,
                commands=commands,
                loaded=True,
            )
            self.skills[skill_name] = skill
            logger.info(f"Reloaded skill: {skill_name} with {len(commands)} commands")
            return True
        else:
            logger.warning(f"Skill {skill_name} has no commands after reload")
            return False


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
