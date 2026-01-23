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

CRITICAL: The LLM only sees the explicit `description=` parameter.
Multi-line docstrings are NOT visible to LLMs - only line 1!

Description Structure (NEW STANDARD):
    description="""
    One-line summary starting with an action verb.

    **Parameters**:
    - `param_name` (required): Description
    - `optional_param` (optional, default: `value`): Description

    **Returns**: Description of return value.
    """

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


@skill_command(
    name="example",
    category="read",
    description="""
    Execute an example command with a single parameter.

    **Parameters**:
    - `param` (required): The parameter value to process

    **Returns**: A formatted string result with the parameter value.
    """,
)
def example(param: str = "default") -> str:
    return f"Example: {param}"


@skill_command(
    name="example_with_options",
    category="read",
    description="""
    Execute an example command with optional boolean and integer parameters.

    **Parameters**:
    - `enabled` (optional, default: `true`): Whether the feature is enabled
    - `value` (optional, default: `42`): The numeric value to use

    **Returns**: A dictionary containing the `enabled` and `value` results.
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
    Process a list of data strings by optionally filtering out empty entries.

    **Parameters**:
    - `data` (required): The list of input data strings to process
    - `filter_empty` (optional, default: `true`): Whether to remove empty strings

    **Returns**: The processed list of data strings.
    """,
)
def process_data(data: list[str], filter_empty: bool = True) -> list[str]:
    if filter_empty:
        return [item for item in data if item.strip()]
    return data
