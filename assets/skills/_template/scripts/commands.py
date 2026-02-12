"""
_template/scripts/commands.py - Skill Commands Template

No tools.py needed - this is the single source of skill commands.

Architecture:
    scripts/
    ├── __init__.py      # Module loader (importlib.util)
    └── commands.py      # Skill commands (direct definitions)

Usage:
    from omni.skills._template.scripts import commands
    commands.example(...)

================================================================================
ODF-EP Protocol: skill_command Description Standards
================================================================================

Format Rules:
- Each param starts with "- "
- Format: "- name: Type = default - Description"
- Optional params have "= default"
- Use Python type syntax: str, int, bool, list[str], Optional[str]

Action Verbs (First Line):
    Create, Get, Search, Update, Delete, Execute, Run, Load, Save,
    List, Show, Check, Build, Parse, Format, Validate, Generate,
    Apply, Process, Clear, Index, Ingest, Consult, Bridge, Refine,
    Summarize, Commit, Amend, Revert, Retrieve, Analyze, Suggest,
    Write, Read, Extract, Query, Filter, Detect, Navigate, Refactor

Categories:
    read   - Query/retrieve information
    write  - Modify/create content
    workflow - Multi-step operations
    search - Find/search operations
    view   - Display/visualize
================================================================================
"""

from omni.foundation.api.decorators import skill_command
from omni.foundation.api.handlers import graph_node


# =============================================================================
# Basic Skill Commands
# =============================================================================

@skill_command(
    name="example",
    category="read",
    description="""
    Execute an example command with a single parameter.

    Args:
        - param: str - The parameter value to process (required)

    Returns:
        A formatted string result with the parameter value.
    """,
)
def example(param: str) -> str:
    """Simple command - just return the result."""
    return f"Example: {param}"


@skill_command(
    name="example_with_options",
    category="read",
    description="""
    Execute an example command with optional boolean and integer parameters.

    Args:
        - enabled: bool = true - Whether the feature is enabled
        - value: int = 42 - The numeric value to use

    Returns:
        A dictionary containing the enabled and value results.
    """,
)
def example_with_options(enabled: bool = True, value: int = 42) -> dict:
    """Command returning structured data."""
    return {
        "enabled": enabled,
        "value": value,
    }


@skill_command(
    name="process_data",
    category="write",
    description="""
    Process a list of data strings by optionally filtering out empty entries.

    Args:
        - data: list[str] - The list of input data strings to process (required)
        - filter_empty: bool = true - Whether to remove empty strings

    Returns:
        The processed list of data strings.
    """,
)
def process_data(data: list[str], filter_empty: bool = True) -> list[str]:
    """Command with conditional logic."""
    if filter_empty:
        return [item for item in data if item.strip()]
    return data


# =============================================================================
# Error Handling Pattern
# =============================================================================

@skill_command(
    name="validate_input",
    category="read",
    description="""
    Validate input parameters and raise on invalid data.

    Args:
        - name: str - The name to validate (required)
        - age: int - The age to validate (required)

    Returns:
        Validation result message.
    """,
)
def validate_input(name: str, age: int) -> str:
    """Command demonstrating proper error handling."""
    if not name:
        raise ValueError("Name cannot be empty")

    if age < 0:
        raise ValueError("Age cannot be negative")

    return f"Valid: {name} (age {age})"


# =============================================================================
# LangGraph Node Pattern (for workflow skills)
# =============================================================================

# Example TypedDict for workflow state
from typing import TypedDict


class WorkflowState(TypedDict):
    """State for the example workflow."""

    input: str
    processed: str
    steps: int
    error: str | None


@graph_node(name="process")
def node_process(state: WorkflowState) -> WorkflowState:
    """
    Process node - transform input data.

    Error handling: Exceptions are automatically logged and re-raised
    by the graph_node handler for LangGraph error handling.
    """
    if not state.get("input"):
        raise ValueError("Input is required")

    processed = state["input"].upper()
    return {
        "input": state["input"],
        "processed": processed,
        "steps": state.get("steps", 0) + 1,
        "error": None,
    }


@graph_node(name="validate")
async def node_validate(state: WorkflowState) -> WorkflowState:
    """
    Validate processed data (async example).

    All async nodes are also supported by graph_node handler.
    """
    if "error" in state:
        raise RuntimeError(f"Previous error: {state['error']}")

    return {
        "input": state["input"],
        "processed": state["processed"],
        "steps": state.get("steps", 0) + 1,
        "error": None,
    }


__all__ = [
    "example",
    "example_with_options",
    "process_data",
    "validate_input",
    "node_process",
    "node_validate",
]
