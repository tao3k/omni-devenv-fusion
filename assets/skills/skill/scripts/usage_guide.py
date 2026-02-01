"""
skill/scripts/usage_guide.py - XML Usage Guide Generation

Automates the creation of XML-based Q&A guides for skill commands.
These guides augment standard JSON Schemas to improve LLM accuracy by providing
contextual anchors, FAQs, and explicit constraints.
"""

import json
from typing import Any

from omni.foundation.api.decorators import CommandResult, skill_command


def generate_xml_guide(config: dict) -> str:
    """
    Synthesize an XML usage guide from skill metadata.

    In a production environment, this could be enhanced by an LLM-based
    synthesizer that analyzes the tool's source code.
    """
    name = config.get("name", "unknown")
    description = config.get("description", "")
    schema = config.get("input_schema", {})
    props = schema.get("properties", {})
    required = schema.get("required", [])
    annotations = config.get("annotations", {})

    xml = []
    xml.append(f'<tool_augmentation name="{name}">')

    # 1. Context Section
    xml.append("  <context>")
    # Use the first paragraph of description as high-level purpose
    purpose = (
        description.split("\n\n")[0].strip()
        if "\n\n" in description
        else description.split("\n")[0].strip()
    )
    xml.append(f"    <purpose>{purpose}</purpose>")

    # Add MCP-style hints if present
    if annotations.get("readOnlyHint"):
        xml.append("    <behavior>Read-only: Safe to execute without side effects.</behavior>")
    if annotations.get("destructiveHint"):
        xml.append(
            "    <behavior>Destructive: Performs permanent changes. Confirm with user if unsure.</behavior>"
        )
    xml.append("  </context>")

    # 2. Constraints Section
    xml.append("  <constraints>")
    for p_name, p_meta in props.items():
        desc = p_meta.get("description", "")
        p_type = p_meta.get("type", "any")

        rules = []
        if p_name in required:
            rules.append("MANDATORY")
        if desc:
            rules.append(desc)

        if rules:
            rule_text = " | ".join(rules)
            xml.append(f'    <rule param="{p_name}" type="{p_type}">{rule_text}</rule>')
    xml.append("  </constraints>")

    # 3. FAQ Section (Common Failure Modes)
    xml.append("  <faq>")
    xml.append("    <item>")
    xml.append(f"      <q>What is the primary goal of {name}?</q>")
    xml.append(f"      <a>{purpose}</a>")
    xml.append("    </item>")

    # Search for "When to use" in description to extract Q&A
    if "When to use" in description:
        use_cases = re_extract_section(description, "When to use")
        if use_cases:
            xml.append("    <item>")
            xml.append(f"      <q>In which scenarios should I prefer this tool?</q>")
            xml.append(f"      <a>{use_cases}</a>")
            xml.append("    </item>")

    xml.append("  </faq>")

    # 4. Scenarios Section (Examples)
    xml.append("  <scenarios>")
    # Build a minimal example from required parameters
    example_args = {p: props.get(p, {}).get("default", f"<{p}>") for p in required}
    if not example_args and props:
        # If no required, pick the first property
        first_prop = list(props.keys())[0]
        example_args = {first_prop: props[first_prop].get("default", "<value>")}

    xml.append('    <scenario description="Typical usage pattern">')
    xml.append(f"      <input>{json.dumps(example_args)}</input>")
    xml.append(
        f"      <reasoning>This call triggers the tool with standard parameters for its primary purpose.</reasoning>"
    )
    xml.append("    </scenario>")
    xml.append("  </scenarios>")

    xml.append("</tool_augmentation>")
    return "\n".join(xml)


def re_extract_section(text: str, section_name: str) -> str:
    """Helper to extract sections from markdown-style docstrings."""
    pattern = rf"(?i)\**{section_name}\**:\s*(.+?)(?=\n\n|\n\s*\w+:|\Z))"
    import re

    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip().replace("\n", " ")
    return ""


@skill_command(
    name="generate_usage_guide",
    category="system",
    description="""
    Generate an XML-based Q&A usage guide for a specific skill command.
    
    This guide augments the standard JSON Schema with contextual anchors, 
    FAQ, and semantic constraints to improve LLM tool-calling accuracy.
    
    Args:
        - skill_name: str - The name of the skill (required)
        - command_name: str - The name of the command within the skill (required)
        
    Returns:
        XML string containing the usage guide.
    """,
)
async def generate_usage_guide(skill_name: str, command_name: str) -> CommandResult[str]:
    from omni.core.kernel import get_kernel

    kernel = get_kernel()
    full_id = f"{skill_name}.{command_name}"

    # Try to find the command in the active registry
    handler = kernel.skill_context.get_command(full_id)

    if not handler:
        return CommandResult[str](
            success=False,
            data="",
            error=f"Command '{full_id}' not found. Make sure the skill is loaded.",
        )

    config = getattr(handler, "_skill_config", {})
    if not config:
        return CommandResult[str](
            success=False,
            data="",
            error=f"Command '{full_id}' exists but has no metadata (it might not be a @skill_command).",
        )

    try:
        xml_guide = generate_xml_guide(config)
        return CommandResult[str](success=True, data=xml_guide)
    except Exception as e:
        return CommandResult[str](
            success=False, data="", error=f"Failed to generate guide: {str(e)}"
        )
