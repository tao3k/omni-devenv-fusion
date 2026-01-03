"""
src/agent/core/skill_registry.py
The Kernel of the Skill-Centric OS.

Responsible for:
1. Discovery: Scanning agent/skills/ for capabilities.
2. Loading: Importing tool modules and registering them with MCP.
3. Context: Providing the procedural knowledge (guides) to the Brain.
"""
import os
import json
import importlib
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import structlog
from mcp.server.fastmcp import FastMCP

from agent.core.schema import SkillManifest
from common.mcp_core.gitops import get_project_root

logger = structlog.get_logger(__name__)


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
        self.skills_dir = self.project_root / "agent" / "skills"
        self.loaded_skills: Dict[str, SkillManifest] = {}
        self._initialized = True

        # Ensure skills dir exists
        self.skills_dir.mkdir(parents=True, exist_ok=True)

    def list_available_skills(self) -> List[str]:
        """Scan the skills directory for valid skills."""
        skills = []
        if not self.skills_dir.exists():
            return []

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                skills.append(item.name)
        return sorted(skills)

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

    def load_skill(self, skill_name: str, mcp: FastMCP) -> Tuple[bool, str]:
        """
        Dynamically load a skill into the MCP server.

        Returns:
            (success, message)
        """
        if skill_name in self.loaded_skills:
            return True, f"Skill '{skill_name}' is already loaded."

        manifest = self.get_skill_manifest(skill_name)
        if not manifest:
            return False, f"Skill '{skill_name}' not found or invalid."

        # 1. Check dependencies
        for dep in manifest.dependencies:
            if dep not in self.loaded_skills:
                # Recursively load dependency
                success, msg = self.load_skill(dep, mcp)
                if not success:
                    return False, f"Failed to load dependency '{dep}': {msg}"

        # 2. Import and register tools
        try:
            # Add project root to path if needed so we can import 'agent.skills...'
            if str(self.project_root) not in sys.path:
                sys.path.insert(0, str(self.project_root))

            module = importlib.import_module(manifest.tools_module)

            # Expect a 'register' function
            if hasattr(module, "register"):
                module.register(mcp)
            else:
                return False, f"Module {manifest.tools_module} has no 'register(mcp)' function."

            self.loaded_skills[skill_name] = manifest
            logger.info(f"Skill loaded: {skill_name}")
            return True, f"Skill '{skill_name}' loaded successfully."

        except Exception as e:
            logger.error(f"Failed to load skill {skill_name}", error=str(e))
            return False, str(e)

    def get_skill_context(self, skill_name: str) -> str:
        """
        Retrieve the 'Procedural Knowledge' (guide.md) for a skill.
        This is what we inject into the LLM context.
        """
        manifest = self.loaded_skills.get(skill_name) or self.get_skill_manifest(skill_name)
        if not manifest:
            return ""

        guide_path = self.skills_dir / skill_name / manifest.guide_file
        content = ""

        if guide_path.exists():
            content += f"--- {skill_name.upper()} GUIDE ---\n"
            content += guide_path.read_text(encoding="utf-8") + "\n"

        if manifest.prompts_file:
            prompts_path = self.skills_dir / skill_name / manifest.prompts_file
            if prompts_path.exists():
                content += f"\n--- {skill_name.upper()} PROMPTS ---\n"
                content += prompts_path.read_text(encoding="utf-8") + "\n"

        return content


# Singleton Accessor
_registry = None


def get_skill_registry():
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
