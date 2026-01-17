"""
_template/scripts/commands.py - Skill Commands

Phase 63+: Commands defined directly with @skill_command decorator.
No tools.py needed - this is the single source of skill commands.

Architecture:
    scripts/
    ├── __init__.py      # Module loader (importlib.util)
    └── commands.py      # Skill commands (direct definitions)

Usage:
    from agent.skills._template.scripts import commands
    commands.example(...)
"""

from agent.skills.decorators import skill_command


@skill_command(
    name="example",
    category="read",
    description="""
    Executes an example command with a single parameter.

    Args:
        param: The parameter value to process. Defaults to `default`.

    Returns:
        A formatted string result with the parameter value.
    """,
)
def example(param: str = "default") -> str:
    return f"Example: {param}"


@skill_command(
    name="example_with_options",
    category="read",
    description="""
    Executes an example command with optional boolean and integer parameters.

    Args:
        enabled: Whether the feature is enabled. Defaults to `true`.
        value: The numeric value to use. Defaults to `42`.

    Returns:
        A dictionary containing the `enabled` and `value` results.
    """,
)
def example_with_options(enabled: bool = True, value: int = 42) -> dict:
    return {
        "enabled": enabled,
        "value": value,
    }


@skill_command(
    name="process_data",
    category="write",
    description="""
    Processes a list of data strings by optionally filtering out empty entries.

    Args:
        data: The list of input data strings to process.
        filter_empty: Whether to remove empty strings from the result.
                      Defaults to `true`.

    Returns:
        The processed list of data strings with empty entries removed if
        `filter_empty` is `true`.
    """,
)
def process_data(data: list[str], filter_empty: bool = True) -> list[str]:
    if filter_empty:
        return [item for item in data if item.strip()]
    return data
