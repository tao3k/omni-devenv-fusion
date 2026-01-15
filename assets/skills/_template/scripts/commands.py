"""
_template/scripts/commands.py - Skill Commands

Phase 63+: Commands defined directly with @skill_script decorator.
No tools.py needed - this is the single source of skill commands.

Architecture:
    scripts/
    ├── __init__.py      # Module loader (importlib.util)
    └── commands.py      # Skill commands (direct definitions)

Usage:
    from agent.skills._template.scripts import commands
    commands.example(...)
"""

from agent.skills.decorators import skill_script


@skill_script(
    name="example",
    category="read",
    description="Example command with parameter",
)
def example(param: str = "default") -> str:
    """
    Example command implementation.

    Args:
        param: Description of the parameter

    Returns:
        String result
    """
    return f"Example: {param}"


@skill_script(
    name="example_with_options",
    category="read",
    description="Example with optional parameters",
)
def example_with_options(enabled: bool = True, value: int = 42) -> dict:
    """
    Example with optional parameters.

    Args:
        enabled: Whether the feature is enabled
        value: The value to use

    Returns:
        Dictionary with results
    """
    return {
        "enabled": enabled,
        "value": value,
    }


@skill_script(
    name="process_data",
    category="write",
    description="Process a list of data strings",
)
def process_data(data: list[str], filter_empty: bool = True) -> list[str]:
    """
    Process a list of data strings.

    Args:
        data: Input data strings
        filter_empty: Whether to remove empty strings

    Returns:
        Processed data list
    """
    if filter_empty:
        return [item for item in data if item.strip()]
    return data
