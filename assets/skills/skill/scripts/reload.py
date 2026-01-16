"""
skill/scripts/reload.py - Dynamic Skill Reload Command

Provides dynamic skill reloading via MCP tool:
- @omni("skill.reload", {"name": "git"})
"""

from agent.skills.decorators import skill_script


@skill_script(
    name="reload",
    category="admin",
    description="""
    Reloads a skill from disk to pick up the latest changes.

    ⚠️  **Use sparingly!** The system has hot-reload (auto-reloads on first use).
    Only reload when:
    - Cache issues occur (old data persists)
    - Modified configs/tools don't take effect
    - A @skill_script decorator's description was updated (LLM needs new schema)
    - Explicit debugging required

    If the skill was unloaded, this will load it. If it was modified,
    this will reload the updated version.

    Args:
        name: Skill name to reload. Defaults to `git`.

    Returns:
        Status message with reload result:
        - `success`: Skill was previously loaded and is now reloaded.
        - `not_loaded`: Skill was not loaded, has been loaded now.
        - `not_found`: Skill does not exist in `assets/skills/`.

    Examples:
        @omni("skill.reload", {"name": "git"})  # Only if git tools show stale data
        @omni("skill.reload", {"name": "filesystem"})  # Only after modifying scripts/
    """,
)
async def reload_skill(name: str = "git") -> str:
    from agent.core.skill_manager.manager import _get_singleton_manager

    manager = _get_singleton_manager()

    import os

    skill_path = os.path.join("assets/skills", name)
    if not os.path.isdir(skill_path):
        return f"""**Skill Not Found**

Skill `{name}` does not exist in `assets/skills/`. Use `omni skill discover` to find available skills."""

    result = manager.reload(name)

    if result is True:
        return f"""**Skill Reloaded**

Successfully reloaded skill: `{name}`

The latest changes from disk are now active."""
    elif result is None:
        return f"""**Skill Loaded**

Skill `{name}` was not loaded before. It has been loaded now.

Use `@omni("git.status")` to verify."""
    else:
        return f"""**Reload Failed**

Could not reload skill `{name}`. Check logs for details."""
