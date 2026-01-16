"""
state_utils.py - State Schema Utilities for LangGraph

Advanced State Schema with Reducers for parallel writes and custom state management.

Usage:
    from agent.core.orchestrator.state_utils import create_reducer_state_schema

    # Create state with reducers
    state_schema = create_reducer_state_schema(
        GraphState,
        {
            "files": operator.add,  # Accumulates list items
            "results": lambda d, u: d.update(u) or d,  # Merges dicts
        }
    )
"""

from __future__ import annotations

import operator
from typing import Any, Callable, Dict, TypeVar, Annotated
from typing_extensions import TypedDict

from ..state import GraphState

T = TypeVar("T")


def create_reducer_state_schema(
    base_schema: type[GraphState] | None = None,
    reducers: Dict[str, Callable] | None = None,
) -> type[TypedDict]:
    """
    Create a state schema with explicit reducers for parallel writes.

    Reducers define how multiple node updates to the same state key are combined.
    This is essential for patterns like:
    - Collecting results from parallel nodes
    - Appending to lists from multiple sources
    - Merging dictionaries from multiple updates

    Args:
        base_schema: Base state class to extend (defaults to GraphState)
        reducers: Dict mapping state keys to reducer functions

    Returns:
        A new TypedDict class with reducer annotations

    Example:
        # Accumulate files from parallel linting tasks
        state_schema = create_reducer_state_schema(
            GraphState,
            {
                "files": operator.add,  # List concatenation
                "results": lambda d, u: d.update(u) or d,  # Dict merge
            }
        )

        # Build with the schema
        builder = DynamicGraphBuilder(skill_manager, state_schema=state_schema)
    """
    base = base_schema or GraphState
    reducers = reducers or {}

    # Create the reduced state class dynamically
    class ReducedState(TypedDict):
        pass

    # Copy annotations from base, applying reducers where specified
    for key, value in getattr(base, "__annotations__", {}).items():
        if key in reducers:
            ReducedState.__annotations__[key] = Annotated[value, reducers[key]]
        else:
            ReducedState.__annotations__[key] = value

    return ReducedState


def create_accumulating_list_schema(
    base_schema: type[GraphState] | None = None,
    list_keys: list[str] | None = None,
) -> type[TypedDict]:
    """
    Create a state schema where specified keys accumulate into lists.

    This is a convenience function for the common pattern of collecting
    values from multiple parallel nodes into a list.

    Args:
        base_schema: Base state class (defaults to GraphState)
        list_keys: Keys that should accumulate into lists

    Returns:
        A new TypedDict class with list accumulation

    Example:
        # Create schema where 'findings' and 'errors' accumulate
        state_schema = create_accumulating_list_schema(
            GraphState,
            list_keys=["findings", "errors"]
        )

        builder = DynamicGraphBuilder(skill_manager, state_schema=state_schema)
    """
    list_keys = list_keys or []
    reducers = {key: operator.add for key in list_keys}
    return create_reducer_state_schema(base_schema, reducers)


def create_merge_dict_schema(
    base_schema: type[GraphState] | None = None,
    dict_keys: list[str] | None = None,
) -> type[TypedDict]:
    """
    Create a state schema where specified keys merge dictionaries.

    This is useful when multiple nodes need to update different fields
    of the same dictionary without overwriting each other.

    Args:
        base_schema: Base state class (defaults to GraphState)
        dict_keys: Keys that should merge dictionaries

    Returns:
        A new TypedDict class with dict merging

    Example:
        # Create schema where 'metadata' and 'results' merge dicts
        state_schema = create_merge_dict_schema(
            GraphState,
            dict_keys=["metadata", "results"]
        )
    """
    dict_keys = dict_keys or []
    reducers = {key: lambda d, u: d.update(u) or d for key in dict_keys}
    return create_reducer_state_schema(base_schema, reducers)


__all__ = [
    "create_reducer_state_schema",
    "create_accumulating_list_schema",
    "create_merge_dict_schema",
]
