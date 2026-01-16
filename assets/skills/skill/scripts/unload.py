"""
skill/scripts/unload.py - Dynamic Skill Unload Command

Provides dynamic skill unloading via MCP tool:
- @omni("skill.unload", {"name": "advanced_search"})
"""

from agent.skills.decorators import skill_script


@skill_script(
    name="unload",
    category="admin",
    description="""
    Unloads a skill from memory.

    The skill files remain on disk but are no longer active.
    Use `skill.reload` to re-activate the skill.

    Args:
        name: Skill name to unload.

    Returns:
        Status message with unload result:
        - `success`: Skill was unloaded successfully.
        - `not_loaded`: Skill was not currently loaded.
        - `pinned`: Cannot unload pinned core skills.

    Examples:
        @omni("skill.unload", {"name": "advanced_search"})

    Note: Core pinned skills (git, terminal, writer, filesystem, note_taker)
    cannot be unloaded.
    """,
)
async def unload_skill(name: str) -> str:
    from agent.core.skill_manager.manager import _get_singleton_manager

    manager = _get_singleton_manager()

    if name not in manager._skills:
        return f"""**Skill Not Loaded**

Skill `{name}` is not currently loaded. Use `omni skill list` to see loaded skills."""

    if name in manager._pinned_skills:
        return f"""**Cannot Unload Pinned Skill**

`{name}` is a core pinned skill and cannot be unloaded. Core skills are essential for system operation."""

    success = manager.unload(name)

    if success:
        return f"""**Skill Unloaded**

Successfully unloaded skill: `{name}`

To reload the skill, use:
- @omni("skill.reload", {{"name": "{name}"}})

Or wait for auto-discovery to reload it on next use."""
    else:
        return f"""**Unload Failed**

Could not unload skill `{name}`. Check logs for details."""
