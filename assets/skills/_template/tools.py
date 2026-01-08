"""
_template/tools.py
Template Skill - Scaffold for creating new skills.

Skill implementation with @skill_command decorators.
"""

from agent.skills.decorators import skill_command


# =============================================================================
# Core Tools
# =============================================================================


@skill_command(
    name="template_example_tool",
    category="read",
    description="An example tool for the template skill.",
)
async def example_tool(param: str) -> str:
    """
    An example tool for the template skill.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value
    """
    return f"Result: {param}"
