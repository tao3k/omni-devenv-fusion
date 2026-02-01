# core/interface.py
"""
Memory store interfaces and base types.

This module defines the abstract interfaces that all memory stores must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# =============================================================================
# Data Types
# =============================================================================

StorageMode = str  # Type alias for storage mode
STORAGE_MODE_LANCE: StorageMode = "lance"
STORAGE_MODE_FILE: StorageMode = "file"


@dataclass
class Decision:
    """Represents an architectural decision record."""

    id: str
    title: str
    content: str
    problem: str
    solution: str
    rationale: str
    status: str
    author: str
    date: str
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        """Create a Decision from a dictionary."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            problem=data.get("problem", ""),
            solution=data.get("solution", ""),
            rationale=data.get("rationale", ""),
            status=data.get("status", "open"),
            author=data.get("author", "Claude"),
            date=data.get("date", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "problem": self.problem,
            "solution": self.solution,
            "rationale": self.rationale,
            "status": self.status,
            "author": self.author,
            "date": self.date,
            "metadata": self.metadata,
        }


@dataclass
class Task:
    """Represents a task in the memory system."""

    id: str
    title: str
    content: str
    status: str
    assignee: str
    created: str
    metadata: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Create a Task from a dictionary."""
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            status=data.get("status", "pending"),
            assignee=data.get("assignee", "Claude"),
            created=data.get("created", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "assignee": self.assignee,
            "created": self.created,
            "metadata": self.metadata,
        }


@dataclass
class ContextSnapshot:
    """Represents a context snapshot."""

    id: str
    timestamp: str
    data: dict[str, Any]
    metadata: dict[str, Any]


@dataclass
class ActiveContext:
    """Represents active context (status, scratchpad, etc.)."""

    id: str
    type: str
    content: str
    updated: str
    metadata: dict[str, Any]


# =============================================================================
# Store Interfaces
# =============================================================================


class DecisionStore(ABC):
    """Abstract interface for decision storage."""

    @abstractmethod
    def add_decision(
        self,
        title: str,
        content: str = "",
        problem: str = "",
        solution: str = "",
        rationale: str = "",
        status: str = "open",
        author: str = "Claude",
    ) -> dict[str, Any]:
        """Add a new decision."""
        ...

    @abstractmethod
    def list_decisions(self) -> list[dict[str, Any]]:
        """List all decisions."""
        ...

    @abstractmethod
    def get_decision(self, title: str) -> dict[str, Any] | None:
        """Get a specific decision."""
        ...

    @abstractmethod
    def delete_decision(self, title: str) -> bool:
        """Delete a decision."""
        ...


class TaskStore(ABC):
    """Abstract interface for task storage."""

    @abstractmethod
    def add_task(
        self,
        title: str,
        content: str = "",
        status: str = "pending",
        assignee: str = "Claude",
    ) -> dict[str, Any]:
        """Add a new task."""
        ...

    @abstractmethod
    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """List tasks, optionally filtered by status."""
        ...

    @abstractmethod
    def get_task(self, title: str) -> dict[str, Any] | None:
        """Get a specific task."""
        ...

    @abstractmethod
    def delete_task(self, title: str) -> bool:
        """Delete a task."""
        ...


class ContextStore(ABC):
    """Abstract interface for context storage."""

    @abstractmethod
    def save_context(self, context_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Save a context snapshot."""
        ...

    @abstractmethod
    def get_latest_context(self) -> dict[str, Any] | None:
        """Get the latest context snapshot."""
        ...


class ActiveContextStore(ABC):
    """Abstract interface for active context storage."""

    @abstractmethod
    def update_status(
        self,
        phase: str,
        focus: str,
        blockers: str = "None",
        sentiment: str = "Neutral",
    ) -> dict[str, Any]:
        """Update the project status."""
        ...

    @abstractmethod
    def get_status(self) -> str:
        """Get the current project status."""
        ...

    @abstractmethod
    def log_scratchpad(self, entry: str, source: str = "Note") -> dict[str, Any]:
        """Log an entry to the scratchpad."""
        ...


class MemoryStore(DecisionStore, TaskStore, ContextStore, ActiveContextStore, ABC):
    """Unified memory store interface."""

    @abstractmethod
    def migrate_from_file(self, source_dir: Path) -> dict[str, Any]:
        """Migrate from file-based storage."""
        ...

    @abstractmethod
    def get_storage_mode(self) -> StorageMode:
        """Get the current storage mode."""
        ...
