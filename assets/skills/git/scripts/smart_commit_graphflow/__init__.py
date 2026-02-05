"""
smart_commit_graphflow - Smart Commit Workflow Module

A modular LangGraph-based workflow for git commits with:
- Automatic staging and security scanning
- Lefthook pre-commit integration
- Submodule change detection and commit support
- Human-in-the-loop approval
- Persistent state via Rust LanceDB checkpoint store

Submodules:
- commands.py: @skill_command entry point (smart_commit)
- nodes.py: All workflow node functions
- state.py: GraphState schema definitions
- workflow.py: Workflow graph builder
- _enums.py: Action, status, and routing enums
"""

from ._enums import (
    SmartCommitAction,
    SmartCommitStatus,
    WorkflowRouting,
)
from .commands import smart_commit
from .nodes import (
    _check_state_node,
    _commit_submodules_node,
    _handle_submodules_node,
    _lefthook_pre_commit_node,
    _return_state,
    _route_state,
)
from .state import (
    SmartCommitGraphState,
    create_initial_state,
)
from .workflow import (
    _build_workflow,
    _get_diagram,
    get_graph,
    get_workflow,
)

__all__ = [
    # Commands
    "smart_commit",
    # Enums
    "SmartCommitAction",
    "SmartCommitStatus",
    "WorkflowRouting",
    # Nodes
    "_check_state_node",
    "_commit_submodules_node",
    "_handle_submodules_node",
    "_lefthook_pre_commit_node",
    "_return_state",
    "_route_state",
    # State
    "SmartCommitGraphState",
    "create_initial_state",
    # Workflow
    "_build_workflow",
    "_get_diagram",
    "get_graph",
    "get_workflow",
]
