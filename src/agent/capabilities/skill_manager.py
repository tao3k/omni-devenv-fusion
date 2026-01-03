"""
src/agent/capabilities/skill_manager.py
The Interface between the Brain and the Skill Kernel.
"""
import json
from mcp.server.fastmcp import FastMCP
from agent.core.skill_registry import get_skill_registry


def register_skill_tools(mcp: FastMCP):
    """Register skill management tools."""
    registry = get_skill_registry()

    @mcp.tool()
    async def list_available_skills() -> str:
        """
        [Skill System] List all discoverable skills in the library.
        Use this to find capabilities like 'git', 'python', 'docker', etc.
        """
        skills = registry.list_available_skills()
        if not skills:
            return "No skills found in agent/skills/."

        # Get descriptions from manifests
        descriptions = []
        for skill in skills:
            manifest = registry.get_skill_manifest(skill)
            if manifest:
                descriptions.append(f"- **{skill}**: {manifest.description}")
            else:
                descriptions.append(f"- **{skill}**")

        return "Available Skills:\n" + "\n".join(descriptions)

    @mcp.tool()
    async def load_skill(skill_name: str) -> str:
        """
        [Skill System] Dynamically load a skill's tools and knowledge.

        Call this when you need specific capabilities to perform a task.
        Example: load_skill('git') when user asks to commit changes.

        Returns:
            The 'Procedural Knowledge' (Guide) for the skill, strictly instructing
            how to use the newly loaded tools.
        """
        # 1. Load the tools into MCP
        success, message = registry.load_skill(skill_name, mcp)

        if not success:
            return f"❌ Failed to load '{skill_name}': {message}"

        # 2. Fetch the Guide (Context)
        # This is critical: inject knowledge while loading tools
        context = registry.get_skill_context(skill_name)

        return f"""
✅ Skill '{skill_name}' loaded successfully!

{message}

=== 📖 PROCEDURAL KNOWLEDGE ({skill_name.upper()}) ===
{context}
==================================================
You may now use the tools listed above following these rules.
"""

    @mcp.tool()
    async def get_active_skills() -> str:
        """Check which skills are currently loaded in memory."""
        loaded = list(registry.loaded_skills.keys())
        if not loaded:
            return "No skills currently loaded."
        return f"Active Skills: {', '.join(loaded)}"
