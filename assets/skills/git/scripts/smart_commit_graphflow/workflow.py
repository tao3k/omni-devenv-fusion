"""
workflow.py - Smart Commit Workflow Builder

Builds the LangGraph StateGraph for the smart commit workflow.
Uses unified Rust LanceDB CheckpointStore for persistent state.

Architecture: Check -> Handle Submodules -> Lefthook -> User Approval -> Commit

Workflow Flow:
1. check: Validates staged files and scan results
2. handle_submodules: Detects and processes submodule changes
3. commit_submodules: Commits changes in each submodule (if needed)
4. lefthook_pre_commit: Runs pre-commit hooks
5. User reviews and approves
6. Main commit is executed
"""

from typing import Any

from langgraph.graph import END, StateGraph

from omni.core.skills.state import GraphState

from ._enums import WorkflowRouting
from .nodes import (
    _check_state_node,
    _commit_submodules_node,
    _handle_submodules_node,
    _lefthook_pre_commit_node,
    _return_state,
    _route_state,
)


def _build_workflow() -> Any:
    """Build the Smart Commit workflow graph.

    Returns:
        StateGraph: The compiled workflow graph ready for execution
    """
    # Import checkpointer here to avoid circular imports
    try:
        from omni.langgraph.checkpoint.saver import get_default_checkpointer as _get_checkpointer

        _CHECKPOINT_AVAILABLE = True
        _memory = _get_checkpointer()
    except ImportError:
        _CHECKPOINT_AVAILABLE = False
        _memory = None

    builder = StateGraph(GraphState)

    # Add all nodes
    builder.add_node("check", _check_state_node)
    builder.add_node("handle_submodules", _handle_submodules_node)
    builder.add_node("commit_submodules", _commit_submodules_node)
    builder.add_node("lefthook_pre_commit", _lefthook_pre_commit_node)
    builder.add_node("empty", _return_state)
    builder.add_node("lefthook_error", _return_state)
    builder.add_node("security_warning", _return_state)
    builder.add_node("prepared", _return_state)

    # Set entry point
    builder.set_entry_point("check")

    # Check node routes to different states based on validation
    builder.add_conditional_edges(
        "check",
        _route_state,
        {
            WorkflowRouting.EMPTY: "empty",
            WorkflowRouting.LEFTHOOK_ERROR: "lefthook_error",
            WorkflowRouting.SECURITY_WARNING: "security_warning",
            WorkflowRouting.PREPARED: "handle_submodules",
        },
    )

    # Handle submodules routes to commit_submodules or proceed directly
    builder.add_conditional_edges(
        "handle_submodules",
        _route_state,
        {
            WorkflowRouting.SUBMODULE_PENDING: "commit_submodules",
            WorkflowRouting.PREPARED: "lefthook_pre_commit",
        },
    )

    # After committing submodules, proceed to lefthook_pre_commit
    builder.add_edge("commit_submodules", "lefthook_pre_commit")

    # All terminal states go to END
    for node in ["empty", "lefthook_error", "security_warning", "prepared"]:
        builder.add_edge(node, END)

    # lefthook_pre_commit is also terminal (user then needs to approve)
    builder.add_edge("lefthook_pre_commit", END)

    return builder


def _get_diagram() -> str:
    """Generate a Mermaid diagram of the workflow.

    Returns:
        str: Mermaid diagram showing the workflow structure
    """
    return """graph TD
    A[Start: git.smart_commit action=start] --> B[git add -A → lefthook → re-stage]
    B --> C{Check Results}
    C -->|Empty| D[empty: Nothing to commit]
    C -->|Lefthook Failed| E[lefthook_error: Fix errors]
    C -->|Security Issues| F[security_warning: Review files]
    C -->|Prepared| G[handle_submodules: Check for submodule changes]
    G --> H{Submodule Routing}
    H -->|No changes| I[lefthook_pre_commit]
    H -->|Has changes| J[commit_submodules: Commit changes in each submodule]
    J --> I
    I --> K[User reviews changes]
    K --> L[User approves with message]
    L --> M[git.smart_commit action=approve]
    M --> N[git commit executes]
    N --> O[Done]"""


# Module-level compiled workflow (lazy initialization)
_smart_commit_graph = None
_app = None


def get_workflow() -> Any:
    """Get the compiled workflow graph.

    Returns:
        Compiled StateGraph with checkpointer
    """
    global _smart_commit_graph, _app

    if _smart_commit_graph is None:
        _smart_commit_graph = _build_workflow()

        # Import checkpointer
        try:
            from omni.langgraph.checkpoint.saver import (
                get_default_checkpointer as _get_checkpointer,
            )

            _memory = _get_checkpointer()
            _app = _smart_commit_graph.compile(checkpointer=_memory)
        except ImportError:
            _app = _smart_commit_graph.compile()

    return _app


def get_graph() -> Any:
    """Get the uncompiled workflow graph.

    Returns:
        StateGraph (not compiled)
    """
    global _smart_commit_graph

    if _smart_commit_graph is None:
        _smart_commit_graph = _build_workflow()

    return _smart_commit_graph


__all__ = [
    "_build_workflow",
    "_get_diagram",
    "get_workflow",
    "get_graph",
]
