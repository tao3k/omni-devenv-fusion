"""
agent/core/orchestrator/state.py
State Persistence for Orchestrator.

Phase 34: GraphState persistence with StateCheckpointer.
"""

from typing import Dict, Any, List

from agent.core.state import create_initial_state


def load_state(self) -> None:
    """Load GraphState from checkpointer on initialization."""
    import structlog

    logger = structlog.get_logger(__name__)

    saved_state = self._checkpointer.get(self._session_id)
    if saved_state:
        self._state = saved_state
        logger.bind(
            session_id=self._session_id,
            message_count=len(saved_state["messages"]),
            current_plan=saved_state.get("current_plan", "")[:50],
        ).info("state_resumed_from_checkpoint")
    else:
        self._state = create_initial_state()
        logger.bind(session_id=self._session_id).info("state_initialized")


def save_state(self, force: bool = False) -> None:
    """Save GraphState to checkpointer."""
    self._checkpointer.put(self._session_id, self._state)


def update_state(self, updates: dict[str, Any]) -> None:
    """Update GraphState with new values."""
    from agent.core.state import merge_state

    self._state = merge_state(self._state, updates)
    self._save_state()


def get_state(self) -> Dict[str, Any]:
    """Get current GraphState."""
    return self._state


def get_state_history(self, limit: int = 10) -> List[Dict[str, Any]]:
    """Get checkpoint history for current session."""
    return [
        {
            "checkpoint_id": cp.checkpoint_id,
            "timestamp": cp.timestamp,
            "state_keys": cp.state_keys,
            "size_bytes": cp.state_size_bytes,
        }
        for cp in self._checkpointer.get_history(self._session_id, limit)
    ]


def get_status(self) -> Dict[str, Any]:
    """Get Orchestrator status for debugging/monitoring."""
    return {
        "router_loaded": self.router is not None,
        "agents_available": list(self.agent_map.keys()),
        "inference_configured": self.inference is not None,
        "session_id": self._session_id,
        "state_messages": len(self._state.get("messages", [])),
        "state_plan": self._state.get("current_plan", "")[:100],
        "use_graph_mode": self.use_graph_mode,
    }


__all__ = [
    "load_state",
    "save_state",
    "update_state",
    "get_state",
    "get_state_history",
    "get_status",
]
