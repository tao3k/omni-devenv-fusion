"""
agent/skills/_template/tools.py
Template Skill - Scaffold for creating new skills.

Phase 25: Omni CLI Architecture
Passive Skill Implementation - Exposes EXPOSED_COMMANDS dictionary.
"""


# =============================================================================
# Core Tools
# =============================================================================


async def example_tool(param: str) -> str:
    """
    An example tool for the template skill.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value
    """
    return f"Result: {param}"


# =============================================================================
# EXPOSED_COMMANDS - Omni CLI Entry Point
# =============================================================================

EXPOSED_COMMANDS = {
    "example_tool": {
        "func": example_tool,
        "description": "An example tool for the template skill.",
        "category": "read",
    },
}


# =============================================================================
# Legacy Export for Compatibility
# =============================================================================

__all__ = [
    "example_tool",
    "EXPOSED_COMMANDS",
]
