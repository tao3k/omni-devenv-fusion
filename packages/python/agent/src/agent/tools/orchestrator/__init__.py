"""
agent/tools/orchestrator/
Orchestrator Tools - Atomic Module Structure

Sub-modules:
- core: Core delegation functionality
- state: State management and global instance
- types: Type definitions

Usage:
    from agent.tools.orchestrator import delegate_mission, get_orchestrator
"""

from .core import delegate_mission
from .state import get_orchestrator, reset_orchestrator, is_orchestrator_initialized
from .types import MissionContext, MissionResult

__all__ = [
    # Core
    "delegate_mission",
    # State
    "get_orchestrator",
    "reset_orchestrator",
    "is_orchestrator_initialized",
    # Types
    "MissionContext",
    "MissionResult",
]
