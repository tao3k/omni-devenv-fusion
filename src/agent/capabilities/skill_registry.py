# src/agent/capabilities/skill_registry.py
"""
The Skill Registry - Discovers and manages composable Skills.

Phase 13: The Skill-First Reformation

A Skill is a self-contained package that includes:
- Procedural knowledge (guide.md)
- MCP tools (tools.py)
- Validation rules (prompts.md)
- Metadata (manifest.json)

This module provides discovery, loading, and management of Skills.

Usage:
    from agent.capabilities.skill_registry import SkillRegistry, list_skills

    registry = SkillRegistry()
    skills = registry.list_skills()
    skill = registry.load_skill("git_operations")
"""
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class SkillCategory(str, Enum):
    """Categories for organizing skills."""
    DEVELOPMENT = "development"
    ARCHITECTURE = "architecture"
    DEBUGGING = "debugging"
    WORKFLOW = "workflow"
    INTEGRATION = "integration"


@dataclass
class SkillManifest:
    """Metadata describing a Skill."""
    name: str
    version: str
    description: str
    category: SkillCategory
    tools: List[str] = field(default_factory=list)
    context_files: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    prompts: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "SkillManifest":
        """Create a SkillManifest from a dictionary (e.g., parsed from manifest.json)."""
        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            category=SkillCategory(data.get("category", "development")),
            tools=data.get("tools", []),
            context_files=data.get("context_files", []),
            dependencies=data.get("dependencies", []),
            prompts=data.get("prompts", []),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category.value,
            "tools": self.tools,
            "context_files": self.context_files,
            "dependencies": self.dependencies,
            "prompts": self.prompts,
        }


@dataclass
class SkillContext:
    """The full context provided by a loaded Skill."""
    manifest: SkillManifest
    guide_content: str = ""
    tool_definitions: Dict[str, Any] = field(default_factory=dict)
    prompts: List[str] = field(default_factory=list)
    loaded: bool = False


class SkillRegistry:
    """
    Discovers and manages available Skills.

    The registry scans the agent/skills/ directory for skills,
    parses their manifests, and provides access to skill metadata.
    """

    SKILLS_DIR = Path(__file__).parent.parent.parent.parent / "agent" / "skills"

    def __init__(self, skills_dir: Optional[Path] = None):
        """Initialize the registry with an optional custom skills directory."""
        self.skills_dir = skills_dir or self.SKILLS_DIR
        self._cache: Dict[str, SkillManifest] = {}
        self._loaded_skills: Dict[str, SkillContext] = {}

    def list_skills(self) -> List[SkillManifest]:
        """
        List all available skills in the registry.

        Returns:
            List of SkillManifest objects for all discovered skills
        """
        if self._cache:
            return list(self._cache.values())

        skills = []
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return skills

        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                manifest_path = skill_dir / "manifest.json"
                if manifest_path.exists():
                    try:
                        data = json.loads(manifest_path.read_text())
                        manifest = SkillManifest.from_dict(data)
                        skills.append(manifest)
                        self._cache[manifest.name] = manifest
                        logger.info(f"Discovered skill: {manifest.name} v{manifest.version}")
                    except (json.JSONDecodeError, ValueError) as e:
                        logger.error(f"Failed to parse manifest for {skill_dir.name}: {e}")

        return skills

    def get_skill_manifest(self, name: str) -> Optional[SkillManifest]:
        """
        Get the manifest for a specific skill by name.

        Args:
            name: The skill name (e.g., "git_operations")

        Returns:
            SkillManifest if found, None otherwise
        """
        # Check cache first
        if name in self._cache:
            return self._cache[name]

        # Load all skills to find the one we want
        self.list_skills()
        return self._cache.get(name)

    def load_skill(self, name: str) -> Optional[SkillContext]:
        """
        Load a skill and its associated context.

        Args:
            name: The skill name to load

        Returns:
            SkillContext with guide, tools, and prompts, or None if not found
        """
        if name in self._loaded_skills:
            return self._loaded_skills[name]

        manifest = self.get_skill_manifest(name)
        if not manifest:
            logger.warning(f"Skill not found: {name}")
            return None

        skill_dir = self.skills_dir / name
        context = SkillContext(manifest=manifest)

        # Load guide.md if present
        guide_path = skill_dir / "guide.md"
        if guide_path.exists():
            context.guide_content = guide_path.read_text()
            logger.info(f"Loaded guide for skill: {name}")

        # Load prompts.md if present
        prompts_path = skill_dir / "prompts.md"
        if prompts_path.exists():
            context.prompts = prompts_path.read_text().split("\n---\n")
            logger.info(f"Loaded {len(context.prompts)} prompts for skill: {name}")

        # Load tool definitions from tools.py if present
        tools_path = skill_dir / "tools.py"
        if tools_path.exists():
            # Tools are loaded dynamically by the MCP server
            context.tool_definitions = {"path": str(tools_path)}
            logger.info(f"Found tools module for skill: {name}")

        context.loaded = True
        self._loaded_skills[name] = context

        return context

    def unload_skill(self, name: str) -> None:
        """
        Unload a skill from the active context.

        Args:
            name: The skill name to unload
        """
        if name in self._loaded_skills:
            del self._loaded_skills[name]
            logger.info(f"Skill unloaded: {name}")

    def get_loaded_skills(self) -> List[SkillContext]:
        """Get all currently loaded skills."""
        return list(self._loaded_skills.values())

    def find_skills_for_task(self, task_description: str) -> List[SkillManifest]:
        """
        Recommend skills for a given task description.

        This is a simple keyword-based matcher. A more sophisticated
        version could use embeddings for semantic matching.

        Args:
            task_description: Description of what the user wants to do

        Returns:
            List of SkillManifest objects that may be relevant
        """
        task_lower = task_description.lower()
        relevant = []

        # Keyword mappings
        keywords = {
            "git": ["git", "commit", "branch", "diff", "log", "push", "pull"],
            "python": ["python", "pip", "virtualenv", "pytest", "pydantic"],
            "filesystem": ["file", "read", "write", "edit", "search", "glob"],
            "architecture": ["design", "structure", "component", "pattern"],
            "debugging": ["debug", "error", "bug", "traceback", "log"],
        }

        for skill in self.list_skills():
            score = 0
            skill_keywords = keywords.get(skill.name, [])
            for kw in skill_keywords:
                if kw in task_lower:
                    score += 1
            if score > 0:
                relevant.append((skill, score))

        # Sort by score descending
        relevant.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in relevant]

    def get_skill_tools(self, name: str) -> List[str]:
        """
        Get the list of tools provided by a skill.

        Args:
            name: The skill name

        Returns:
            List of tool names
        """
        manifest = self.get_skill_manifest(name)
        return manifest.tools if manifest else []


# Global registry instance
_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get the global SkillRegistry instance."""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def list_skills() -> List[SkillManifest]:
    """Convenience function to list all available skills."""
    return get_skill_registry().list_skills()


def load_skill(name: str) -> Optional[SkillContext]:
    """Convenience function to load a skill by name."""
    return get_skill_registry().load_skill(name)


def get_skill_manifest(name: str) -> Optional[SkillManifest]:
    """Convenience function to get a skill's manifest."""
    return get_skill_registry().get_skill_manifest(name)


# =============================================================================
# MCP Tool Registration
# =============================================================================

def register_skill_tools(mcp) -> None:
    """Register all skill registry tools with the MCP server."""

    @mcp.tool(name="list_skills")
    async def list_skills_tool() -> str:
        """List all available skills in the registry."""
        skills = list_skills()
        if not skills:
            return "📭 No skills found in the registry."

        lines = ["# 🎯 Available Skills", ""]
        for skill in skills:
            lines.append(f"- **{skill.name}** v{skill.version}")
            lines.append(f"  - {skill.description}")
            lines.append(f"  - Category: `{skill.category.value}`")
            lines.append(f"  - Tools: {', '.join(skill.tools)}")
            lines.append("")

        lines.append(f"Total: {len(skills)} skills")
        return "\n".join(lines)

    @mcp.tool(name="get_skill_manifest")
    async def get_skill_manifest_tool(name: str) -> str:
        """Get the manifest for a specific skill by name."""
        import json
        manifest = get_skill_manifest(name)
        if not manifest:
            return f"❌ Skill '{name}' not found."

        return f"""# 🎯 Skill Manifest: {manifest.name}

**Version**: {manifest.version}
**Category**: {manifest.category.value}

{manifest.description}

## Tools Provided
{', '.join(f'`{t}`' for t in manifest.tools)}

## Context Files
{', '.join(f'`{f}`' for f in manifest.context_files) if manifest.context_files else 'None'}

## Dependencies
{', '.join(manifest.dependencies) if manifest.dependencies else 'None'}
"""

    @mcp.tool(name="load_skill")
    async def load_skill_tool(name: str) -> str:
        """
        Load a skill and its associated context (guide, tools, prompts).

        When a skill is loaded, it provides:
        1. MCP tools defined in its tools.py
        2. Procedural knowledge from guide.md
        3. System prompts from prompts.md
        """
        context = load_skill(name)
        if not context:
            return f"❌ Skill '{name}' not found."

        lines = [f"# 🎯 Skill Loaded: {name}", ""]
        lines.append(f"**Version**: {context.manifest.version}")
        lines.append(f"**Description**: {context.manifest.description}")
        lines.append("")
        lines.append("## Tools Available")
        for tool in context.manifest.tools:
            lines.append(f"- `{tool}`")
        lines.append("")

        if context.guide_content:
            lines.append("## Guide Available")
            lines.append(f"(See `agent/skills/{name}/guide.md` for full content)")
            lines.append("")

        if context.prompts:
            lines.append("## Prompts Loaded")
            lines.append(f"{len(context.prompts)} prompt(s) loaded")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool(name="find_skills_for_task")
    async def find_skills_for_task_tool(task_description: str) -> str:
        """Recommend skills for a given task description."""
        registry = get_skill_registry()
        skills = registry.find_skills_for_task(task_description)

        if not skills:
            return "🤷 No specific skills found for this task. Using default capabilities."

        lines = ["# 🎯 Recommended Skills", ""]
        for skill in skills:
            lines.append(f"- **{skill.name}**: {skill.description}")
            lines.append(f"  - Tools: {', '.join(skill.tools)}")
            lines.append("")

        return "\n".join(lines)

    @mcp.tool(name="get_loaded_skills")
    async def get_loaded_skills_tool() -> str:
        """List all currently loaded skills."""
        registry = get_skill_registry()
        loaded = registry.get_loaded_skills()

        if not loaded:
            return "📭 No skills currently loaded."

        lines = ["# 🎯 Loaded Skills", ""]
        for ctx in loaded:
            lines.append(f"- **{ctx.manifest.name}** v{ctx.manifest.version}")
            if ctx.guide_content:
                lines.append("  - Guide: loaded")
            if ctx.prompts:
                lines.append(f"  - Prompts: {len(ctx.prompts)}")
            lines.append("")

        return "\n".join(lines)

    logger.info("Skill Registry tools registered")


__all__ = [
    "SkillRegistry",
    "SkillManifest",
    "SkillContext",
    "SkillCategory",
    "list_skills",
    "load_skill",
    "get_skill_manifest",
    "get_skill_registry",
    "register_skill_tools",
]
