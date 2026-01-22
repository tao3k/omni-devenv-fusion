"""
skill/scripts/list_tools.py - List All Registered MCP Tools

Lists all registered MCP tools from loaded skills with descriptions.
"""

from omni.core.skills.script_loader import skill_command


@skill_command(
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
    from omni.core.kernel import get_kernel

    kernel = get_kernel()
    ctx = kernel.skill_context

    # Get tools from skill context
    tools = []
    for skill_name in ctx.list_skills():
        skill_obj = ctx.get_skill(skill_name)
        if skill_obj is None:
            continue

        commands = skill_obj.list_commands() if hasattr(skill_obj, "list_commands") else []
        for cmd_name in commands:
            tools.append(
                {
                    "skill": skill_name,
                    "command": cmd_name,
                    "description": getattr(skill_obj, "description", "") or "",
                }
            )

    if compact:
        lines = [f"# Tools ({len(tools)})", ""]
        for tool in sorted(tools, key=lambda x: x["skill"]):
            lines.append(f"- `{tool['skill']}.{tool['command']}`")
        return "\n".join(lines)

    lines = ["# Registered MCP Tools", ""]
    lines.append(f"**Total**: {len(tools)} tools from {len(ctx.list_skills())} loaded skills")
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
