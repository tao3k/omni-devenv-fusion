"""_enums.py - StrEnum definitions for git workflow actions and statuses.

Uses Python 3.11+ StrEnum for type-safe string enums.
"""

from enum import StrEnum, auto


class SmartCommitAction(StrEnum):
    """Workflow actions for the smart commit process."""

    START = auto()
    APPROVE = auto()
    REJECT = auto()
    STATUS = auto()
    VISUALIZE = auto()


class SmartCommitStatus(StrEnum):
    """Status values for the smart commit workflow state."""

    LEFTHOOK_FAILED = auto()
    SECURITY_VIOLATION = auto()
    EMPTY = auto()
    PREPARED = auto()
    APPROVED = auto()
    COMMITTED = auto()


class WorkflowRouting(StrEnum):
    """Routing values for workflow state transitions."""

    EMPTY = auto()
    LEFTHOOK_ERROR = auto()
    SECURITY_WARNING = auto()
    PREPARED = auto()


__all__ = [
    "SmartCommitAction",
    "SmartCommitStatus",
    "WorkflowRouting",
]
