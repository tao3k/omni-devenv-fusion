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
        """
        skills = registry.list_available_skills()
        if not skills:
            return "No skills found in agent/skills/."

        descriptions = []
        for skill in skills:
            manifest = registry.get_skill_manifest(skill)
            if manifest:
                descriptions.append(f"- **{skill}**: {manifest.description}")
            else:
                descriptions.append(f"- **{skill}**")

        return "Available Skills:\n" + "\n".join(descriptions)

    @mcp.tool()
    async def load_skill(skill_name: str, use_diff: bool = True) -> str:
        """
        [Skill System] Dynamically load a skill's tools and knowledge.

        Args:
            skill_name: The skill to load
            use_diff: If True (default), show only changes via git diff (token-efficient)
                      If False, show full content (use for first-time loading)
        """
        success, message = registry.load_skill(skill_name, mcp)

        if not success:
            return f"Failed to load '{skill_name}': {message}"

        context = registry.get_skill_context(skill_name, use_diff=use_diff)

        mode_note = "(CHANGES ONLY)" if use_diff else "(FULL CONTENT)"
        return f"""
Skill '{skill_name}' loaded successfully!

{message}

=== PROCEDURAL KNOWLEDGE {mode_note} ({skill_name.upper()}) ===
{context}
==================================================
"""

    @mcp.tool()
    async def read_loaded_skills() -> str:
        """
        [Knowledge] Read loaded skills and inject their knowledge into LLM context.

        Returns the combined prompts.md content from all loaded skills.
        Use this to make LLM remember skill rules and capabilities.
        """
        return registry.get_combined_context()

    @mcp.tool()
    async def get_active_skills() -> str:
        """
        [Skill System] Check which skills are currently loaded in memory.
        Use this to see what's currently active.
        """
        loaded = registry.list_loaded_skills()
        if not loaded:
            return "No skills currently loaded."

        preload = registry.get_preload_skills()

        lines = ["Active Skills:"]
        for skill in loaded:
            status = "[Preloaded]" if skill in preload else "[On-Demand]"
            lines.append(f"- {skill} {status}")

        return "\n".join(lines)

    @mcp.tool()
    async def list_skill_modes() -> str:
        """
        [Skill System] List skills by loading mode (Preload vs On-Demand).
        Use this to understand what's available at startup vs what needs explicit loading.
        """
        preload = registry.get_preload_skills()
        all_skills = registry.list_available_skills()

        lines = ["## Skill Loading Modes (from settings.yaml)", ""]
        lines.append(f"### Preload ({len(preload)}) - Loaded at startup")
        for skill in preload:
            status = "✓" if skill in registry.list_loaded_skills() else "○"
            lines.append(f"  {status} {skill}")

        lines.append(
            f"\n### Available On-Demand ({len([s for s in all_skills if s not in preload])}) - Load when needed"
        )
        for skill in sorted(all_skills):
            if skill not in preload:
                status = "✓" if skill in registry.list_loaded_skills() else "○"
                lines.append(f"  {status} {skill}")

        return "\n".join(lines)

    @mcp.tool()
    async def invoke_skill(skill: str, tool: str, args: dict) -> str:
        """
        [Structured] Execute a skill operation with structured arguments.

        Usage:
        - invoke_skill("filesystem", "list_directory", {"path": "."})
        - invoke_skill("git", "git_status", {})
        - invoke_skill("git", "git_commit", {"message": "feat: add feature"})

        Args:
            skill: The skill name (e.g., "filesystem", "git", "terminal")
            tool: The function name to call (e.g., "list_directory", "git_status")
            args: Arguments as a JSON object/dict
        """
        return await _execute_skill_operation(skill, tool, args, mcp, registry)


async def _execute_skill_operation(
    skill: str, operation: str, kwargs: dict, mcp: FastMCP, registry
) -> str:
    """Common execution logic for skill() and invoke_skill()."""
    # Auto-load skill if not already loaded
    if skill not in registry.loaded_skills:
        success, msg = registry.load_skill(skill, mcp)
        if not success:
            return f"Failed to load skill '{skill}': {msg}"
        # Get the loaded module for auto-load case
        module = registry.module_cache.get(skill)
        if not module:
            return f"Skill '{skill}' loaded but not in module cache."

    # Get the loaded module
    module = registry.module_cache.get(skill)
    if not module:
        return f"Skill '{skill}' not found in module cache."

    # Execute operation (functions are now at module level)
    if hasattr(module, operation):
        func = getattr(module, operation)
        if callable(func):
            try:
                import inspect

                if inspect.iscoroutinefunction(func):
                    result = await func(**kwargs)
                else:
                    result = func(**kwargs)
                return result
            except Exception as e:
                return f"Error executing {operation}: {e}"
        else:
            return f"'{operation}' is not callable."
    else:
        # List available operations in this skill
        available = [
            attr
            for attr in dir(module)
            if not attr.startswith("_") and callable(getattr(module, attr, None))
        ]
        return f"Operation '{operation}' not found in skill '{skill}'. Available: {available}"
