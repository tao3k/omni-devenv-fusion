"""
_template/tools.py - Template Skill Router (Phase 36)

This is the ROUTER layer - it only dispatches to implementation scripts.
All actual logic is in the scripts/ directory.

Architecture (Controller Layer Pattern):
    tools.py    -> Router (just dispatches, validates params)
    scripts/    -> Controllers (actual implementation)

Naming Convention:
    @skill_command(name="<command>", ...)
    - Command names are just the function name (e.g., "example")
    - MCP Server automatically prefixes with skill name: "_template.example"

Usage:
    from agent.skills._template.scripts import example

Note: We use absolute imports to work with ModuleLoader's package setup.
The scripts module is loaded as agent.skills._template.scripts.xxx

To create a new skill:
    cp -r assets/skills/_template assets/skills/my_skill
    # Then rename _template to my_skill in tools.py and SKILL.md
"""

from agent.skills.decorators import skill_command


# =============================================================================
# READ Operations (Router Layer)
# =============================================================================


@skill_command(
    name="example",
    category="read",
    description="An example command for the template skill.",
)
def example(param: str = "default") -> str:
    """
    An example command for the template skill.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value
    """
    from agent.skills._template.scripts import example as example_mod

    return example_mod.example_command(param)


@skill_command(
    name="example_with_options",
    category="read",
    description="Example command with optional parameters.",
)
def example_with_options(enabled: bool = True, value: int = 42) -> dict:
    """
    Example command with optional parameters.

    Args:
        enabled: Whether the feature is enabled
        value: The value to use

    Returns:
        Dictionary with results
    """
    from agent.skills._template.scripts import example as example_mod

    return example_mod.example_with_options(enabled=enabled, value=value)


@skill_command(
    name="process_data",
    category="write",
    description="Process a list of data strings.",
)
def process_data(data: list[str], filter_empty: bool = True) -> dict:
    """
    Process a list of data strings.

    Args:
        data: Input data strings
        filter_empty: Whether to remove empty strings

    Returns:
        Dictionary with processed data and metadata
    """
    from agent.skills._template.scripts import example as example_mod

    result = example_mod.process_data(data, filter_empty=filter_empty)
    return {
        "processed": result,
        "count": len(result),
        "original_count": len(data),
    }


# =============================================================================
# VIEW Operations (Router Layer)
# =============================================================================


@skill_command(
    name="help",
    category="view",
    description="Show full skill context and guidelines.",
)
def help() -> str:
    """
    Show full skill context and guidelines.
    """
    from common.skills_path import SKILLS_DIR
    from repomix import repomix

    skill_dir = SKILLS_DIR(skill="_template")
    output = repomix(skill_dir, style="xml", include=["SKILL.md", "tools.py", "README.md"])
    return output


# =============================================================================
# SIDECAR EXECUTION EXAMPLE (For Heavy Dependencies)
# =============================================================================
# If your skill has heavy dependencies (like crawl4ai, playwright, pandas),
# use the Sidecar Execution Pattern via Swarm to avoid polluting the main agent.
#
# Example:
#
# @skill_command(
#     name="_template.heavy_operation",
#     category="write",
#     description="Execute heavy computation in isolated environment.",
# )
# def heavy_operation(input_data: str) -> dict:
#     """
#     Execute heavy operation using Swarm sidecar execution.
#
#     This keeps the main agent clean of heavy dependencies.
#     """
#     from agent.core.swarm import get_swarm
#
#     return get_swarm().execute_skill(
#         skill_name="_template",
#         command="heavy.py",
#         args={"input": input_data},
#         mode="sidecar_process",
#         timeout=120,
#     )
#
# Then create scripts/heavy.py with the actual implementation:
#
# """scripts/heavy.py - Heavy computation (runs in uv isolation)"""
# import pandas as pd
# import heavy_library
#
# def heavy_computation(input_data: str) -> dict:
#     # Your heavy computation here
#     result = heavy_library.process(input_data)
#     return {"result": result}
#
# if __name__ == "__main__":
#     import json
#     import sys
#     args = json.loads(sys.argv[1])
#     result = heavy_computation(**args)
#     print(json.dumps({"success": True, "data": result}))
#
# Usage:
#   @omni("_template.heavy_operation", {"input": "data"})
#
