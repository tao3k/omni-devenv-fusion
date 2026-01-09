"""
_template/scripts/example.py - Example Implementation

Atomic script implementation for the _template skill.

Best practices:
1. Keep functions atomic and focused
2. Use type hints
3. Add docstrings
4. Import from agent.skills._template.scripts for shared utilities
"""

from typing import Optional


def example_command(param: str = "default") -> str:
    """
    Example command implementation.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value
    """
    return f"Example: {param}"


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
        "timestamp": "2024-01-01T00:00:00",
    }


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
