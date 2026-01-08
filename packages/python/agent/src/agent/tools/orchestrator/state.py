"""
agent/tools/orchestrator/state.py
Orchestrator state management.

Handles global orchestrator instance and state retention.
"""

from agent.core.orchestrator import Orchestrator

# Global instance for state retention
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get or create the global Orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        # Initialize with Sidecar/Headless support enabled by default in Server mode
        _orchestrator = Orchestrator()
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the global orchestrator instance (for testing)."""
    global _orchestrator
    _orchestrator = None


def is_orchestrator_initialized() -> bool:
    """Check if orchestrator has been initialized."""
    return _orchestrator is not None


__all__ = [
    "get_orchestrator",
    "reset_orchestrator",
    "is_orchestrator_initialized",
]
