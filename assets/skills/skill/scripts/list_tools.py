"""
List all registered MCP tools from loaded skills.
"""


def format_tools_list(compact: bool = False) -> str:
    """
    Format a list of all registered MCP tools.

    Args:
        compact: If True, show minimal output (name only)

    Returns:
        Formatted markdown string with all tools
    """
    from agent.core.skill_manager import get_skill_manager

    manager = get_skill_manager()

    # Collect all tools
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
        # Minimal format: just tool names
        lines = [f"# 🔧 Tools ({len(tools)})", ""]
        for tool in sorted(tools, key=lambda x: x["skill"]):
            lines.append(f"- `{tool['skill']}.{tool['command']}`")
        return "\n".join(lines)

    # Full format with descriptions
    lines = ["# 🔧 Registered MCP Tools", ""]
    lines.append(f"**Total**: {len(tools)} tools from {len(manager.list_loaded())} loaded skills")
    lines.append("")

    # Group by skill
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
    lines.append('**Usage**: `@omni("skill.command", {{"arg": "value"}})`')

    return "\n".join(lines)
