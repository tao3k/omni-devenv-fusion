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
    Reload a skill from disk to pick up structural changes.

    **When to use:**
    - The skill's `@skill_command` decorator attributes were modified (name, description, category)
    - Hot reload mechanism is not working (changes not reflected after normal file edits)

    **When NOT to use:**
    - Regular script file changes - hot reload handles this automatically
    - Configuration changes - usually picked up automatically

    **Hot Reload Mechanism:**
    - Most changes are automatically detected and reloaded
    - Manual reload is rarely needed for script modifications
    - Decorator metadata changes require explicit reload

    **Important - MCP Client Caching:**
    MCP clients (like Claude Code) cache tool descriptions. After reloading:
    1. Server sends `notifications/tools/list_changed`
    2. Client may not automatically refresh its cached tool list
    3. If descriptions don't update, try: **restart Claude Code session**

    Args:
        - name: str = git - Skill name to reload

    Returns:
        Status message with reload result (success, not_loaded, or not_found).
    """,
)
async def reload_skill(name: str = "git") -> str:
    """Reload a skill from disk to pick up structural changes."""
    import os

    from omni.core.kernel import get_kernel

    kernel = get_kernel()

    skill_path = os.path.join("assets/skills", name)
    if not os.path.isdir(skill_path):
        return f"""**Skill Not Found**

Skill `{name}` does not exist in `assets/skills/`."""

    # Check if skill was previously loaded
    loaded_skills = kernel.skill_context.list_skills()
    was_loaded = name in loaded_skills

    # Reload the skill via kernel
    try:
        await kernel.reload_skill(name)
        return f"""**Skill Reloaded**

Successfully reloaded skill: `{name}`

Hot reload mechanism activated.

**Note:** If the MCP client (Claude Code) still shows old tool descriptions, restart the Claude Code session to clear the cache."""
    except Exception as e:
        return f"""**Reload Failed**

Error reloading skill `{name}`: {e}"""
