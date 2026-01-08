"""
agent/tools/orchestrator/types.py
Type definitions for orchestrator tools.

Provides type hints for delegate_mission and related functions.
"""

from typing import TypedDict, List, Dict, Any, Optional
from typing_extensions import Literal


class MissionContext(TypedDict):
    """Context for a mission delegation."""

    relevant_files: List[str]


class MissionResult(TypedDict):
    """Result of a mission delegation."""

    success: bool
    output: str
    confidence: float


__all__ = [
    "MissionContext",
    "MissionResult",
]
