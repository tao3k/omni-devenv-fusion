"""
src/agent/capabilities/skill_manager.py
The Interface between the Brain and the Skill Kernel.

One Tool compatible - call directly or route via @omni.
"""

import json
from agent.core.skill_registry import get_skill_registry


async def list_available_skills() -> str:
    """
    [Skill System] List all discoverable skills in the library.
    """
    registry = get_skill_registry()
    skills = registry.list_available_skills()
    if not skills:
        return "No skills found in assets/skills/."

    descriptions = []
    for skill in skills:
        manifest = registry.get_skill_manifest(skill)
        if manifest:
            descriptions.append(f"- **{skill}**: {manifest.description}")
        else:
            descriptions.append(f"- **{skill}**")

    return "Available Skills:\n" + "\n".join(descriptions)


async def load_skill(skill_name: str, use_diff: bool = True) -> str:
    """
    [Skill System] Dynamically load a skill's tools and knowledge.

    Args:
        skill_name: The skill to load
        use_diff: If True (default), show only changes via git diff (token-efficient)
                  If False, show full content (use for first-time loading)
    """
    registry = get_skill_registry()
    # Note: mcp parameter removed for One Tool compatibility
    success, message = registry.load_skill(skill_name, None)

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


async def read_loaded_skills() -> str:
    """
    [Knowledge] Read loaded skills and inject their knowledge into LLM context.

    Returns the combined prompts.md content from all loaded skills.
    Use this to make LLM remember skill rules and capabilities.
    """
    registry = get_skill_registry()
    return registry.get_combined_context()


async def get_active_skills() -> str:
    """
    [Skill System] Check which skills are currently loaded in memory.
    Use this to see what's currently active.
    """
    registry = get_skill_registry()
    loaded = registry.list_loaded_skills()
    if not loaded:
        return "No skills currently loaded."

    preload = registry.get_preload_skills()

    lines = ["Active Skills:"]
    for skill in loaded:
        status = "[Preloaded]" if skill in preload else "[On-Demand]"
        lines.append(f"- {skill} {status}")

    return "\n".join(lines)


async def list_skill_modes() -> str:
    """
    [Skill System] List skills by loading mode (Preload vs On-Demand).
    Use this to understand what's available at startup vs what needs explicit loading.
    """
    registry = get_skill_registry()
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


async def execute_skill_operation(skill: str, operation: str, kwargs: dict) -> str:
    """
    Execute a skill operation.

    Args:
        skill: Skill name
        operation: Function name to call
        kwargs: Arguments to pass
    """
    from agent.core.skill_registry import SkillRegistry

    registry = get_skill_registry()

    # Auto-load skill if not already loaded
    if skill not in registry.loaded_skills:
        success, msg = registry.load_skill(skill, None)
        if not success:
            return f"Failed to load skill '{skill}': {msg}"
        module = registry.module_cache.get(skill)
        if not module:
            return f"Skill '{skill}' loaded but not in module cache."

    module = registry.module_cache.get(skill)
    if not module:
        return f"Skill '{skill}' not found in module cache."

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
        available = [
            attr
            for attr in dir(module)
            if not attr.startswith("_") and callable(getattr(module, attr, None))
        ]
        return f"Operation '{operation}' not found in skill '{skill}'. Available: {available}"
