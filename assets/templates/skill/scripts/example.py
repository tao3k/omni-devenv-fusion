"""
{{ skill_name }}/scripts/example.py - Example implementation

This is an isolated script module. Use relative imports to access
shared utilities within the {{ skill_name }}/scripts/ namespace.

Best practices:
1. Keep functions atomic and focused
2. Use type hints
3. Add docstrings
4. Import from . (same package) for shared utilities
"""

from typing import Optional


def example_command(param: str) -> str:
    """Example command implementation."""
    return f"Example: {param}"


def example_with_options(enabled: bool = True, value: int = 42) -> dict:
    """Example with optional parameters."""
    return {
        "enabled": enabled,
        "value": value,
    }
