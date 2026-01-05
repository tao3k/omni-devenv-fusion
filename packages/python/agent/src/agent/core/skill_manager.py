"""
src/agent/core/skill_manager.py
Omni CLI - Single Entry Point for All Skills.

Phase 25: Omni CLI Architecture
Replaces Phase 24's direct tool registration with a unified command router.

Architecture:
- SkillManager (central command) scans skills and builds registry
- Skills expose EXPOSED_COMMANDS dictionary (no @mcp.tool decorators)
- Single omni_run(command, args) tool handles all operations

Usage:
    skill_manager = SkillManager()
    skill_manager.load_skills()
    result = skill_manager.run("git", "git_status_report", {})
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
import logging

from common.mcp_core.settings import get_setting, get_project_root

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
        tools_path = skill_dir / "tools.py"
        module_name = f"agent.skills.{skill_dir.name}.tools"

        # Check if already loaded
        if module_name in sys.modules:
            return module_name

        try:
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
        Extract EXPOSED_COMMANDS from a skill module.

        Skills should define:
            EXPOSED_COMMANDS = {
                "command_name": {
                    "func": function_reference,
                    "description": "What this command does",
                    "category": "read|write|workflow|evolution"
                },
                ...
            }

        Args:
            module: The loaded skill module
            skill_name: Name of the skill for logging

        Returns:
            Dictionary of command name -> SkillCommand
        """
        commands = {}

        # Check for EXPOSED_COMMANDS
        if hasattr(module, "EXPOSED_COMMANDS"):
            exposed = module.EXPOSED_COMMANDS
            if isinstance(exposed, dict):
                for cmd_name, cmd_info in exposed.items():
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
                            logger.debug(f"Loaded command: {skill_name}.{cmd_name}")
                        else:
                            logger.warning(
                                f"Command {cmd_name} in {skill_name} has no callable func"
                            )
                    else:
                        logger.warning(f"Invalid command format for {cmd_name} in {skill_name}")
            else:
                logger.warning(f"EXPOSED_COMMANDS in {skill_name} is not a dict")
        else:
            logger.warning(f"Skill {skill_name} has no EXPOSED_COMMANDS defined")

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

    def run(
        self,
        skill_name: str,
        command_name: str,
        args: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute a command from a skill.

        This is the main entry point for executing skill commands.

        Args:
            skill_name: Name of the skill (e.g., "git")
            command_name: Name of the command (e.g., "git_status_report")
            args: Optional arguments to pass to the command function

        Returns:
            String result from the command execution
        """
        command = self.get_command(skill_name, command_name)
        if command is None:
            return f"Error: Command {skill_name}.{command_name} not found"

        try:
            import asyncio

            func = command.func
            args = args or {}

            if asyncio.iscoroutinefunction(func):
                # Run async function - handle both with and without running event loop
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop, safe to use asyncio.run()
                    result = asyncio.run(func(**args))
                else:
                    # Already in an event loop, create a new thread with its own event loop
                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(asyncio.run, func(**args))
                        result = future.result()
            else:
                # Run sync function
                result = func(**args)

            return result

        except TypeError as e:
            # Handle missing arguments
            return f"Error executing {skill_name}.{command_name}: {e}"
        except Exception as e:
            logger.error(f"Error executing {skill_name}.{command_name}: {e}")
            return f"Error: {e}"

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
