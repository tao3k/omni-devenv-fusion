"""
skill/scripts/list_tools.py - List All Registered MCP Tools

Lists all registered MCP tools from loaded skills with descriptions.
"""

from agent.skills.decorators import skill_script


@skill_script(
    name="list_tools",
    category="read",
    description="""
    [CRITICAL] Lists all registered MCP tools with their names, descriptions,
    and usage information. Use this to discover available capabilities.

    Args:
        compact: If `true`, shows minimal output with tool names only.
                 Defaults to `false`.

    Returns:
        Markdown-formatted list of all tools grouped by skill.
        Full format includes tool names, descriptions, and usage examples.
        Compact format shows only `skill.command` names.

    Usage:
        @omni("skill.list_tools", {"compact": true})
        @omni("skill.list_tools", {"compact": false})
    """,
)
def list_tools(compact: bool = False) -> str:
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    tools = []
    for skill_name in manager.list_loaded():
        skill_info = manager.get_info(skill_name)
        if not skill_info:
            continue

        commands = manager.get_commands(skill_name)
        for cmd_name in commands:
            cmd = manager.get_command(skill_name, cmd_name)
            if cmd is None:
                continue

            tools.append(
                {
                    "skill": skill_name,
                    "command": cmd_name,
                    "description": cmd.description or "",
                }
            )

    if compact:
        lines = [f"# Tools ({len(tools)})", ""]
        for tool in sorted(tools, key=lambda x: x["skill"]):
            lines.append(f"- `{tool['skill']}.{tool['command']}`")
        return "\n".join(lines)

    lines = ["# Registered MCP Tools", ""]
    lines.append(f"**Total**: {len(tools)} tools from {len(manager.list_loaded())} loaded skills")
    lines.append("")

    current_skill = None
    for tool in sorted(tools, key=lambda x: x["skill"]):
        if tool["skill"] != current_skill:
            current_skill = tool["skill"]
            lines.append(f"## {current_skill}")
            lines.append("")

        lines.append(f"### `{current_skill}.{tool['command']}`")
        if tool["description"]:
            lines.append(f">{tool['description']}")
        lines.append("")

    lines.append("---")
    lines.append('**Usage**: `@omni("skill.command", {"arg": "value"})`')

    return "\n".join(lines)


def format_tools_list(compact: bool = False) -> str:
    """Alias for list_tools for backward compatibility."""
    return list_tools(compact)
