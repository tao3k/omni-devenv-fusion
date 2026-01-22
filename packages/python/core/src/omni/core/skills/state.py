"""
omni.core.skills.state - Skill State Types

State containers for skill workflows and graph execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphState:
    """Graph state container for LangGraph workflows.

    Used by smart_commit and other workflow skills.
    """

    project_root: str = "."
    workflow_id: str = ""
    staged_files: list[str] = field(default_factory=list)
    diff_content: str = ""
    status: str = "pending"
    error: str = ""
    lefthook_error: str = ""
    security_issues: list[str] = field(default_factory=list)
    scope_warning: str = ""
    lefthook_report: str = ""
    commit_message: str = ""
    approved: bool = False

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state dict-like interface."""
        return getattr(self, key, default)

    def __getitem__(self, key: str) -> Any:
        """Dict-like access."""
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Dict-like assignment."""
        setattr(self, key, value)

    def __contains__(self, key: str) -> bool:
        """Check if key exists."""
        return hasattr(self, key)

    def __iter__(self):
        """Iterate over keys."""
        return iter(self.__dict__)

    def keys(self):
        """Return state keys."""
        return self.__dict__.keys()

    def values(self):
        """Return state values."""
        return self.__dict__.values()

    def items(self):
        """Return state items."""
        return self.__dict__.items()

    def to_dict(self) -> dict[str, Any]:
        """Convert to regular dict."""
        return dict(self.__dict__)


@dataclass
class WorkflowState:
    """Simple workflow state for non-graph workflows."""

    workflow_id: str = ""
    status: str = "pending"
    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in state."""
        self.data[key] = value


__all__ = ["GraphState", "WorkflowState"]
