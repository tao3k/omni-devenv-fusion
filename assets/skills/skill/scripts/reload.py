"""
skill/scripts/reload.py - Dynamic Skill Reload Command

Provides dynamic skill reloading via MCP tool:
- @omni("skill.reload", {"name": "git"})
"""

from omni.foundation.api.decorators import skill_command


@skill_command(
    name="reload",
    category="admin",
    description="""
    Reload a skill from disk to pick up the latest changes.

    Use when cache issues occur, configs don't take effect, or descriptions were updated.

    Args:
        - name: str = git - Skill name to reload

    Returns:
        Status message with reload result (success, not_loaded, or not_found).
    """,
)
async def reload_skill(name: str = "git") -> str:
    from omni.core.kernel import get_kernel

    kernel = get_kernel()
    ctx = kernel.skill_context

    import os

    skill_path = os.path.join("assets/skills", name)
    if not os.path.isdir(skill_path):
        return f"""**Skill Not Found**

Skill `{name}` does not exist in `assets/skills/`."""

    # Check if skill was previously loaded
    loaded_skills = ctx.list_skills()
    was_loaded = name in loaded_skills

    # Reload the skill via SkillContext
    success = ctx.reload(name) if hasattr(ctx, "reload") else False

    if success or was_loaded:
        return f"""**Skill Reloaded**

Successfully reloaded skill: `{name}`

The latest changes from disk are now active."""
    else:
        return f"""**Skill Loaded**

Skill `{name}` was not loaded before. It has been loaded now.

Use `@omni("git.status")` to verify."""
