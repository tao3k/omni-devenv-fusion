"""
lifecycle.py - Skill Lifecycle Management

Handles skill loading, unloading, and reloading.
Uses SkillMemoryManager for LRU + TTL tracking.
"""

import asyncio
import concurrent.futures
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from ..support.models import Skill, SkillCommand
    from ..core.memory_core import SkillMemoryManager


def _get_logger():
    from ...protocols import _get_logger

    return _get_logger()


class SkillLifecycle:
    """
    Manages skill lifecycle: load, unload, reload.

    This class handles the surgical operations for managing skill modules
    in the Python runtime. Uses SkillMemoryManager for LRU + TTL tracking.
    """

    __slots__ = (
        "_skills_dir",
        "_manifest_loader",
        "_mtime_cache",
        "_memory",
        "_notify_change",
        "_fire_and_forget",
    )

    def __init__(
        self,
        skills_dir: Path,
        manifest_loader,
        mtime_cache: dict[str, float],
        memory: "SkillMemoryManager",
        notify_change: Callable[[str, str], None],
        fire_and_forget: Callable[[Any], Any],
    ) -> None:
        self._skills_dir = skills_dir
        self._manifest_loader = manifest_loader
        self._mtime_cache = mtime_cache
        self._memory = memory
        self._notify_change = notify_change
        self._fire_and_forget = fire_and_forget

    # =========================================================================
    # Skill Loading
    # =========================================================================

    def load_skill(
        self,
        skill_path: Path,
        skills: dict[str, "Skill"],
        command_cache: dict[str, "SkillCommand"],
        reload: bool = False,
    ) -> Optional["Skill"]:
        """
        Load a skill from a path.

        Args:
            skill_path: Path to the skill directory
            skills: Skills registry dict (modified in-place)
            command_cache: Command cache dict (modified in-place)
            reload: If True, force reload even if already loaded

        Returns:
            Loaded Skill or None if failed
        """
        from ..support.models import Skill
        from agent.core.protocols import ExecutionMode

        skill_name = skill_path.name

        # Check if already loaded
        if not reload and skill_name in skills:
            return skills[skill_name]

        # Unload existing if reload
        if reload and skill_name in skills:
            self.unload(skill_name, skills, command_cache)

        # Run manifest loading in thread to avoid event loop conflicts
        def _load_manifest():
            return asyncio.run(self._manifest_loader.load_metadata(skill_path))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            metadata = executor.submit(_load_manifest).result()

        if metadata is None:
            _get_logger().error("No SKILL.md found", skill=skill_name)
            return None

        manifest = metadata.to_dict()
        execution_mode = metadata.execution_mode

        # Load commands from scripts/*.py
        script_commands: dict[str, "SkillCommand"] = {}
        scripts_dir = skill_path / "scripts"
        mtime = 0.0

        if scripts_dir.exists() and any(scripts_dir.glob("*.py")):
            script_commands = self._extract_commands_from_scripts(skill_name, scripts_dir)
            if script_commands:
                # Update mtime based on scripts
                try:
                    script_mtimes = [f.stat().st_mtime for f in scripts_dir.glob("*.py")]
                    if script_mtimes:
                        mtime = max(script_mtimes)
                except FileNotFoundError:
                    pass

        if not script_commands:
            _get_logger().warning("No commands found in skill", skill=skill_name)

        # Create skill with lazy context cache
        config_path = skill_path / "repomix.json"
        context_path = skill_path if config_path.exists() else None

        skill = Skill(
            name=skill_name,
            metadata=metadata,
            commands=script_commands,
            module_name=f"agent.skills.{skill_name}",
            path=scripts_dir,
            mtime=mtime,
            execution_mode=execution_mode,
            _context_path=context_path,
            _module=None,
        )

        skills[skill_name] = skill
        self._mtime_cache[skill_name] = mtime

        # Rebuild command cache
        self._rebuild_command_cache(skill_name, script_commands, command_cache)

        # No debug log for successful load - only errors matter

        # Notify observers
        self._notify_change(skill_name, "load")

        # Update LRU tracking via memory manager
        self._memory.touch(skill_name)

        return skill

    def load_manifest(self, skill_path: Path) -> Optional[dict[str, Any]]:
        """Load manifest from SKILL.md."""

        def _load():
            return asyncio.run(self._manifest_loader.load_metadata(skill_path))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            metadata = executor.submit(_load).result()

        if metadata is None:
            return None
        return metadata.to_dict()

    def _ensure_skill_package(self, skill_name: str, skill_path: Path) -> None:
        """Set up the package hierarchy in sys.modules for a skill.

        This enables both relative imports (from .state import ...) and
        absolute imports (from agent.skills.decorators import ...) to work.
        """
        import types
        import importlib.util

        project_root = self._skills_dir.parent.parent
        skills_root = self._skills_dir
        scripts_dir = skill_path / "scripts"

        # Ensure 'agent' package exists
        if "agent" not in sys.modules:
            agent_src = project_root / "packages/python/agent/src/agent"
            agent_pkg = types.ModuleType("agent")
            agent_pkg.__path__ = [str(agent_src)]
            agent_pkg.__file__ = str(agent_src / "__init__.py")
            sys.modules["agent"] = agent_pkg

        # Ensure 'agent.skills' package exists
        if "agent.skills" not in sys.modules:
            skills_pkg = types.ModuleType("agent.skills")
            skills_pkg.__path__ = [str(skills_root)]
            sys.modules["agent.skills"] = skills_pkg

        # Ensure 'agent.skills.<skill_name>' package exists
        skill_pkg_name = f"agent.skills.{skill_name}"
        if skill_pkg_name not in sys.modules:
            skill_pkg = types.ModuleType(skill_pkg_name)
            skill_pkg.__path__ = [str(skill_path)]
            sys.modules[skill_pkg_name] = skill_pkg

        # Ensure 'agent.skills.<skill_name>.scripts' package exists
        scripts_pkg_name = f"agent.skills.{skill_name}.scripts"
        if scripts_pkg_name not in sys.modules:
            scripts_pkg = types.ModuleType(scripts_pkg_name)
            scripts_pkg.__path__ = [str(scripts_dir)]
            scripts_pkg.__file__ = (
                str(scripts_dir / "__init__.py") if scripts_dir.exists() else None
            )
            sys.modules[scripts_pkg_name] = scripts_pkg

        # Pre-load decorators module for @skill_command support
        decorators_name = "agent.skills.decorators"
        if decorators_name not in sys.modules:
            decorators_path = project_root / "packages/python/agent/src/agent/skills/decorators.py"
            if decorators_path.exists():
                spec = importlib.util.spec_from_file_location(decorators_name, str(decorators_path))
                if spec and spec.loader:
                    decorators_mod = importlib.util.module_from_spec(spec)
                    sys.modules[decorators_name] = decorators_mod
                    spec.loader.exec_module(decorators_mod)

    def _extract_commands_from_scripts(
        self,
        skill_name: str,
        scripts_dir: Path,
    ) -> dict[str, "SkillCommand"]:
        """Extract commands from scripts/*.py files."""
        from ..support.models import SkillCommand
        from agent.core.protocols import SkillCategory

        # Set up package hierarchy for this skill
        self._ensure_skill_package(skill_name, scripts_dir.parent)

        result: dict[str, "SkillCommand"] = {}
        for py_file in scripts_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            module_name = f"agent.skills.{skill_name}.scripts.{py_file.stem}"
            package_name = f"agent.skills.{skill_name}.scripts"
            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                import importlib.util

                spec = importlib.util.spec_from_file_location(module_name, py_file)
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # Set __package__ for relative imports to work
                    module.__package__ = package_name
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                else:
                    continue

            for attr_name in dir(module):
                if attr_name.startswith("_"):
                    continue

                attr = getattr(module, attr_name, None)
                # Check for _skill_config dict (not Path from __getattr__ fallback)
                if callable(attr) and hasattr(attr, "_skill_config"):
                    config = getattr(attr, "_skill_config", None)
                    if isinstance(config, dict):
                        cmd_name = config.get("name", attr_name)
                        description = config.get("description", "")
                        category = config.get("category", "general")
                        input_schema = config.get("input_schema", {})
                        inject_root = config.get("inject_root", False)
                        inject_settings = config.get("inject_settings", [])
                        retry_on = config.get("retry_on", (ConnectionError, TimeoutError))
                        max_attempts = config.get("max_attempts", 3)
                        cache_ttl = config.get("cache_ttl", 0.0)
                        pure = config.get("pure", False)

                        result[cmd_name] = SkillCommand(
                            name=cmd_name,
                            func=attr,
                            description=description,
                            category=SkillCategory(category),
                            _skill_name=skill_name,
                            input_schema=input_schema,
                            _script_mode=True,
                            _inject_root=inject_root,
                            _inject_settings=inject_settings,
                            _retry_on=retry_on,
                            _max_attempts=max_attempts,
                            cache_ttl=cache_ttl,
                            pure=pure,
                        )

        return result

    def _rebuild_command_cache(
        self,
        skill_name: str,
        skill_commands: dict[str, "SkillCommand"],
        command_cache: dict[str, "SkillCommand"],
    ) -> None:
        """Rebuild command cache for a skill."""
        for cmd_name, cmd in skill_commands.items():
            full_name = f"{skill_name}.{cmd_name}"
            command_cache[full_name] = cmd
            # Also register alias without skill prefix
            if cmd_name not in command_cache:
                command_cache[cmd_name] = cmd

    # =========================================================================
    # Skill Unloading
    # =========================================================================

    def unload(
        self,
        skill_name: str,
        skills: dict[str, "Skill"],
        command_cache: dict[str, "SkillCommand"],
    ) -> bool:
        """
        Unload a skill by name.

        Performs surgical cleanup:
        1. Removes skill from internal registry
        2. Clears command cache entries
        3. Recursively cleans sys.modules
        4. Notifies observers
        """
        skill = skills.pop(skill_name, None)
        if skill is None:
            return False

        # Clear command cache entries
        keys_to_remove = [k for k in command_cache if k.startswith(f"{skill_name}.")]
        for key in keys_to_remove:
            del command_cache[key]

        # Clear mtime cache
        self._mtime_cache.pop(skill_name, None)

        # Remove from LRU tracking via memory manager
        if skill_name in self._memory.lru_timestamps:
            del self._memory.lru_timestamps[skill_name]

        # Recursive sys.modules cleanup
        if skill.module_name:
            if skill.module_name in sys.modules:
                del sys.modules[skill.module_name]

            prefix = f"agent.skills.{skill_name}."
            modules_to_remove = [m for m in sys.modules if m.startswith(prefix)]
            for mod in modules_to_remove:
                del sys.modules[mod]

        _get_logger().debug("Skill unloaded", skill=skill_name)
        self._notify_change(skill_name, "unload")

        return True

    # =========================================================================
    # Skill Reloading
    # =========================================================================

    def reload(
        self,
        skill_name: str,
        discover_single: Callable[[str], Optional[Path]],
        skills: dict[str, "Skill"],
        command_cache: dict[str, "SkillCommand"],
    ) -> bool | None:
        """
        Reload a skill by name (unload + load).

        Args:
            skill_name: Name of the skill to reload
            discover_single: Function to discover skill path
            skills: Skills registry dict
            command_cache: Command cache dict

        Returns:
            True if reloaded, False if not found, None if not loaded
        """
        if skill_name not in skills:
            _get_logger().warning("Cannot reload: skill not loaded", skill=skill_name)
            return None

        self.unload(skill_name, skills, command_cache)

        skill_path = discover_single(skill_name)
        if skill_path is None:
            _get_logger().warning("Cannot reload: skill path not found", skill=skill_name)
            return False

        self.load_skill(skill_path, skills, command_cache, reload=True)

        _get_logger().info("Skill reloaded", skill=skill_name)
        return True

    # =========================================================================
    # Subprocess Execution
    # =========================================================================

    def execute_in_subprocess(
        self,
        skill_name: str,
        command_name: str,
        args: dict[str, Any] | None,
    ) -> str:
        """
        Execute a command in a subprocess (for subprocess mode skills).
        """
        import json
        import subprocess

        skill_dir = self._skills_dir / skill_name
        manifest = self.load_manifest(skill_dir)

        if not manifest:
            return f"Error: No SKILL.md found for skill {skill_name}"

        entry_point = manifest.get("entry_point", "implementation.py")
        entry_path = skill_dir / entry_point

        if not entry_path.exists():
            return f"Error: Entry point not found at {entry_path}"

        try:
            cmd = [
                "uv",
                "run",
                "--directory",
                str(skill_dir),
                "-q",
                "python",
                entry_point,
                command_name,
                json.dumps(args or {}),
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=120)
            return result.stdout.strip()

        except subprocess.CalledProcessError as e:
            return f"Error (Exit {e.returncode}):\n{e.stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 120 seconds"
        except FileNotFoundError:
            return "Error: 'uv' not found"


__all__ = ["SkillLifecycle"]
