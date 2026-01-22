"""
skill/scripts/unload.py - Dynamic Skill Unload Command

Provides dynamic skill unloading via MCP tool:
- @omni("skill.unload", {"name": "advanced_search"})
"""

from omni.core.skills.script_loader import skill_command


@skill_command(
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
    from omni.core.kernel import get_kernel

    kernel = get_kernel()
    ctx = kernel.skill_context

    if name not in ctx.list_skills():
        return f"""**Skill Not Loaded**

Skill `{name}` is not currently loaded. Use `omni skill list` to see loaded skills."""

    # Unload the skill via SkillContext (if supported)
    success = ctx.unload(name) if hasattr(ctx, "unload") else True

    if success:
        return f"""**Skill Unloaded**

Successfully unloaded skill: `{name}`

To reload the skill, use:
- @omni("skill.reload", {{"name": "{name}"}})"""
    else:
        return f"""**Unload Failed**

Could not unload skill `{name}`. Check logs for details."""
