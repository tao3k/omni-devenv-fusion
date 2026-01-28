"""
skill/scripts/list_tools.py - List All Registered MCP Tools (Alias-Aware)

Lists all registered MCP tools from loaded skills with descriptions.
Applies command aliases and documentation overrides from settings.yaml.
Uses common omni tool definition from omni.core.omni_tool.
"""

from omni.foundation.api.decorators import skill_command
from omni.core.omni_tool import get_omni_tool_list_entry


@skill_command(
    name="list_tools",
    category="view",
    description="""
    List all registered MCP tools with names, descriptions, and usage information.
    Applies overrides from settings.yaml.

    Args:
        - compact: bool = false - If true, shows minimal output with tool names only

    Returns:
        Markdown-formatted list of all tools grouped by skill.
    """,
)
def list_tools(compact: bool = False) -> str:
    from omni.core.kernel import get_kernel
    from omni.core.config.loader import load_command_overrides

    kernel = get_kernel()
    ctx = kernel.skill_context
    overrides = load_command_overrides()

    # Get tools from skill context directly for maximum accuracy
    all_commands = ctx.get_core_commands()

    tools = []

    # [MASTER] Add omni - Highest Authority Universal Gateway (from common module)
    tools.append(get_omni_tool_list_entry())

    for full_cmd in all_commands:
        skill_name = full_cmd.split(".", 1)[0] if "." in full_cmd else "core"

        # Apply alias logic
        override = overrides.commands.get(full_cmd)
        display_name = override.alias if override and override.alias else full_cmd

        # Get base description from command object
        cmd_obj = ctx.get_command(full_cmd)
        base_desc = getattr(cmd_obj, "description", "") or f"Execute {full_cmd}"

        # Apply documentation override
        extra_doc = override.append_doc if override else None
        display_desc = f"{base_desc} {extra_doc}" if extra_doc else base_desc

        tools.append(
            {
                "skill": skill_name,
                "command": full_cmd,
                "display_name": display_name,
                "description": display_desc,
                "is_aliased": display_name != full_cmd,
            }
        )

    if compact:
        lines = [f"# Tools ({len(tools)})", ""]
        for tool in sorted(tools, key=lambda x: (x["skill"], x["display_name"])):
            if tool["is_aliased"]:
                lines.append(f"- `{tool['display_name']}` (Alias for `{tool['command']}`)")
            else:
                lines.append(f"- `{tool['command']}`")
        return "\n".join(lines)

    lines = ["# Registered MCP Tools", ""]
    lines.append(f"**Total**: {len(tools)} tools registered")
    lines.append("")

    current_skill = None
    for tool in sorted(tools, key=lambda x: (x["skill"], x["display_name"])):
        if tool["skill"] != current_skill:
            current_skill = tool["skill"]
            lines.append(f"## {current_skill}")
            lines.append("")

        header = f"### `{tool['display_name']}`"
        if tool["is_aliased"]:
            header += f" (Canonical: `{tool['command']}`)"
        lines.append(header)

        if tool["description"]:
            # Clean up newlines for cleaner markdown
            clean_desc = tool["description"].strip()
            lines.append(f">{clean_desc}")
        lines.append("")

    lines.append("---")
    lines.append('**Usage**: `@omni("skill.command", {"arg": "value"})`')

    return "\n".join(lines)


def format_tools_list(compact: bool = False) -> str:
    """Alias for list_tools for backward compatibility."""
    return list_tools(compact)
