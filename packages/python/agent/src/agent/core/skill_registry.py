"""
src/agent/core/skill_registry.py
The Kernel of the Skill-Centric OS.
V2: Uses Spec-based loading for precise, pollution-free plugin management.
Phase 13.10: Config-driven preloading + on-demand loading.
Phase 25.1: Supports @skill_command decorator pattern.
"""

import json
import importlib.util
import sys
import types
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import structlog
from mcp.server.fastmcp import FastMCP

from agent.core.schema import SkillManifest
from common.gitops import get_project_root
from common.settings import get_setting

logger = structlog.get_logger(__name__)

# Marker attribute for @skill_command decorated functions
_SKILL_COMMAND_MARKER = "_is_skill_command"


class SkillRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.project_root = get_project_root()
        skills_path = get_setting("skills.path", "assets/skills")
        self.skills_dir = self.project_root / skills_path
        self.loaded_skills: Dict[str, SkillManifest] = {}
        self.module_cache: Dict[str, types.ModuleType] = {}
        self.skill_tools: Dict[str, list[str]] = {}  # Track tool names per skill
        self._initialized = True

        self.skills_dir.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Configuration-Driven Loading (Phase 13.10)
    # =========================================================================

    def get_preload_skills(self) -> List[str]:
        """Get list of skills to preload from settings.yaml."""
        return get_setting("skills.preload", [])

    def preload_all(self, mcp: FastMCP) -> Tuple[int, List[str]]:
        """
        Load all preload skills from settings.yaml.
        Returns: (count of loaded, list of skill names)
        """
        preload_skills = self.get_preload_skills()
        loaded = []
        failed = []

        for skill in preload_skills:
            if skill in self.loaded_skills:
                continue  # Already loaded
            success, msg = self.load_skill(skill, mcp)
            if success:
                loaded.append(skill)
                logger.info(f"Preloaded skill: {skill}")
            else:
                failed.append(skill)
                logger.warning(f"Failed to preload {skill}: {msg}")

        return len(loaded), loaded

    def list_available_skills(self) -> List[str]:
        """Scan the skills directory for valid skills."""
        skills = []
        if not self.skills_dir.exists():
            return []

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                skills.append(item.name)
        return sorted(skills)

    def list_loaded_skills(self) -> List[str]:
        """List currently loaded skills."""
        return list(self.loaded_skills.keys())

    def get_skill_manifest(self, skill_name: str) -> Optional[SkillManifest]:
        """Read and parse a skill's manifest."""
        manifest_path = self.skills_dir / skill_name / "manifest.json"
        if not manifest_path.exists():
            return None

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            return SkillManifest(**data)
        except Exception as e:
            logger.error(f"Failed to parse manifest for {skill_name}", error=str(e))
            return None

    def _load_module_from_path(self, module_name: str, file_path: Path) -> types.ModuleType:
        """
        Load a python module directly from a file path without polluting sys.path.
        Enables hot reloading by re-executing the module code.
        """
        import types

        # Clear any existing module from sys.modules to ensure hot reload works
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Resolve the project root and skills directory
        skills_dir = self.skills_dir

        # Ensure parent packages exist in sys.modules for relative imports
        # This allows 'from agent.skills.decorators import ...' to work
        parts = module_name.split(".")
        for i in range(1, len(parts)):
            parent_name = ".".join(parts[:i])
            if parent_name not in sys.modules:
                parent_mod = types.ModuleType(parent_name)
                # Set __path__ to make it a package (required for subpackage imports)
                parent_mod.__path__ = []
                sys.modules[parent_name] = parent_mod

        # Pre-load the decorators module if the skill imports it
        # This is required for @skill_command decorator to work
        decorators_path = skills_dir / "decorators.py"
        if decorators_path.exists() and "agent.skills.decorators" not in sys.modules:
            decorators_spec = importlib.util.spec_from_file_location(
                "agent.skills.decorators", decorators_path
            )
            decorators_module = importlib.util.module_from_spec(decorators_spec)
            sys.modules["agent.skills.decorators"] = decorators_module
            decorators_spec.loader.exec_module(decorators_module)

        # Create the Spec (The Blueprint)
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            raise ImportError(f"Could not create spec for {file_path}")

        # Create the Module (The Instance)
        module = importlib.util.module_from_spec(spec)

        # Set __package__ to enable relative imports inside the skill
        # Extract package from module name (e.g., "agent.skills.git.tools" -> "agent.skills.git")
        if len(parts) > 1:
            module.__package__ = ".".join(parts[:-1])
        else:
            module.__package__ = ""

        # Register in sys.modules for relative imports inside the skill
        sys.modules[module_name] = module

        # Execute the code (The Activation)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise e

        return module

    def load_skill(self, skill_name: str, mcp: FastMCP) -> Tuple[bool, str]:
        """
        Dynamically load a skill into the MCP server using spec-based loading.
        Supports HOT RELOAD.
        """
        manifest = self.get_skill_manifest(skill_name)
        if not manifest:
            return False, f"Skill '{skill_name}' not found or invalid."

        # 1. Resolve Dependencies
        for dep in manifest.dependencies:
            if dep not in self.loaded_skills:
                success, msg = self.load_skill(dep, mcp)
                if not success:
                    return False, f"Dependency '{dep}' failed: {msg}"

        # 2. Locate the Tools File
        # tools_module="agent.skills.git.tools" -> agent/skills/git/tools.py
        # Handle both "agent.skills" and "assets.skills" prefixes for backward/forward compatibility
        tools_module = manifest.tools_module
        if tools_module.startswith("agent.skills."):
            tools_module = "assets.skills." + tools_module[len("agent.skills.") :]
        relative_path = tools_module.replace(".", "/") + ".py"
        source_path = self.project_root / relative_path

        if not source_path.exists():
            return False, f"Source file not found: {source_path}"

        # 3. Load/Reload Logic
        try:
            module_name = manifest.tools_module

            # Explicitly load from file (bypasses cache because we re-exec)
            module = self._load_module_from_path(module_name, source_path)

            # 4. Registration
            # Phase 25.1: Check for @skill_command decorated functions
            skill_commands = []
            for name in dir(module):
                if name.startswith("_"):
                    continue
                obj = getattr(module, name)
                if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
                    skill_commands.append(name)

            if skill_commands:
                logger.info(
                    f"Skill '{skill_name}' uses @skill_command pattern. Commands: {skill_commands}"
                )
            else:
                return (
                    False,
                    f"Module {source_path.name} has no @skill_command decorated functions.",
                )

            # Update State
            self.loaded_skills[skill_name] = manifest
            self.module_cache[skill_name] = module

            logger.info(f"Skill loaded via Spec: {skill_name}")
            return True, f"Skill '{skill_name}' loaded via Direct Spec (Hot Reload)."

        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}", error=str(e))
            return False, f"Load Error: {str(e)}"

    def get_skill_context(self, skill_name: str, use_diff: bool = False) -> str:
        """
        Retrieve the 'Procedural Knowledge' (guide.md) for a skill.

        Args:
            skill_name: Name of the skill
            use_diff: If True, show only changes via git diff (token-efficient)
        """
        manifest = self.loaded_skills.get(skill_name) or self.get_skill_manifest(skill_name)
        if not manifest:
            return ""

        content = ""

        # Helper to get file content or diff
        def get_file_content_or_diff(file_path: Path, file_label: str) -> str:
            if not file_path.exists():
                return ""
            if use_diff:
                # Use git diff for token-efficient updates
                import subprocess

                try:
                    diff = subprocess.run(
                        ["git", "diff", str(file_path)],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                    )
                    if diff.returncode == 0 and diff.stdout.strip():
                        return (
                            f"\n--- {skill_name.upper()} {file_label} (CHANGED) ---\n{diff.stdout}"
                        )
                    else:
                        return f"\n--- {skill_name.upper()} {file_label} ---\n[Unchanged - not showing]"
                except Exception:
                    # Fallback to full content if git fails
                    pass
            return f"\n--- {skill_name.upper()} {file_label} ---\n{file_path.read_text(encoding='utf-8')}\n"

        # Get guide content
        guide_path = self.skills_dir / skill_name / manifest.guide_file
        content += get_file_content_or_diff(guide_path, "GUIDE")

        # Get prompts content
        if manifest.prompts_file:
            prompts_path = self.skills_dir / skill_name / manifest.prompts_file
            content += get_file_content_or_diff(prompts_path, "SYSTEM PROMPTS")

        return content

    def get_combined_context(self) -> str:
        """
        Aggregate prompts.md from all loaded skills into a single context string.

        This is the "dynamic brain" of the Agent - it contains routing rules
        and policies that Claude must follow for each active skill.

        Returns:
            Combined context string from all loaded skills' prompts.md files.
        """
        if not self.loaded_skills:
            return "# No skills loaded\n\nActive skills will have their prompts.md aggregated here."

        combined = []
        combined.append("# 🧠 Active Skill Policies & Routing Rules")
        combined.append(
            "The following skills are loaded and active. You MUST follow their routing logic.\n"
        )

        for skill_name in sorted(self.loaded_skills.keys()):
            manifest = self.loaded_skills[skill_name]

            # Read prompts.md
            if manifest.prompts_file:
                prompts_path = self.skills_dir / skill_name / manifest.prompts_file
                if prompts_path.exists():
                    content = prompts_path.read_text(encoding="utf-8")
                    combined.append(f"\n## 📦 Skill: {skill_name.upper()}")
                    combined.append(content)
                    combined.append("\n---\n")

        return "\n".join(combined)


_registry = None


def get_skill_registry():
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def get_skill_tools(skill_name: str) -> Dict[str, callable]:
    """
    Get all tool functions from a loaded skill.

    Phase 19: Enables ReAct loop to access dynamically loaded skill tools.
    Phase 25.1: Returns only @skill_command decorated functions.

    Args:
        skill_name: Name of the skill (e.g., "filesystem")

    Returns:
        Dict of tool name -> callable function
    """
    registry = get_skill_registry()
    module = registry.module_cache.get(skill_name)

    if not module:
        return {}

    tools = {}
    # Get all callables with @skill_command decorator (has _is_skill_command attribute)
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if callable(obj) and hasattr(obj, _SKILL_COMMAND_MARKER):
            tools[name] = obj

    return tools
