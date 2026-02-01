from typing import Dict, Any
from ..state import RobustTaskState


async def review_node(state: RobustTaskState) -> Dict[str, Any]:
    """
    Review Node - A placeholder for human interaction.
    In a CLI flow, the actual interaction happens in the runner (run.py).
    This node serves as a checkpoint/router based on the user's input.
    """
    # Logic is mainly handled by the edge routing,
    # but we can do some preprocessing here if needed.

    # If we are here, it means we are waiting for approval or just received it.
    status = state.get("approval_status", "pending")

    if status == "pending":
        # This state signals the runner to interrupt
        return {"approval_status": "waiting_for_user"}

    return {}
