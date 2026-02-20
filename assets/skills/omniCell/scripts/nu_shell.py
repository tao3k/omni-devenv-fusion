"""omniCell.nuShell - Structured OS Interaction

Trinity Architecture - Core Layer

Unified command execution via Nushell with structured JSON output.
Replaces bash for agent workflows.
"""

import json
from typing import Any

from omni.core.skills.runtime.omni_cell import ActionType, get_runner
from omni.foundation.api.decorators import skill_command
from omni.foundation.api.response_payloads import build_status_message_response
from omni.foundation.context_delivery import ChunkedSessionStore, validate_chunked_action
from omni.foundation.runtime.skill_optimization import clamp_int

_NUSHELL_CHUNKED_WORKFLOW_TYPE = "omnicell_nushell_chunked"
_NUSHELL_CHUNKED_STORE = ChunkedSessionStore(_NUSHELL_CHUNKED_WORKFLOW_TYPE)


def _normalize_batch_size(value: Any) -> int:
    """Clamp chunk batch size for stable memory usage."""
    return clamp_int(value, default=28_000, min_value=2_000, max_value=200_000)


@skill_command(
    name="nuShell",
    description="""
    Execute Nushell command with structured JSON output.

    Universal shell tool - use for ANY terminal command:
    - ls, cat, grep, find (file operations)
    - git, cargo, npm, pytest (development tools)
    - Any command-line operation

    Features:
    - Intent Classification: Auto-detects 'observe' vs 'mutate'
    - Safety Analysis: Blocks dangerous commands
    - Structured Output: JSON returned
    - Optional chunked mode for large outputs via action=start/batch

    Args:
        - command: Any terminal command (nushell syntax)
        - intent: str = "" - Optional explicit intent: observe | mutate
        - chunked: bool = false - If true, return action=start with session_id + first batch
        - action: str = "" - Optional chunked action: start | batch
        - session_id: str = "" - Required for action=batch
        - batch_index: int = 0 - Batch index for action=batch
        - batch_size: int = 28000 - Character window for chunked payload splitting

    Returns:
        Dictionary with status, data, and metadata. In chunked mode returns
        session_id/batch_count/batch payload.

    Example:
        <tool_call>{"name": "omniCell.nuShell", "arguments": {"command": "cargo test"}}</tool_call>
    """,
    read_only=False,
    destructive=False,
    idempotent=False,
    open_world=False,
)
async def nuShell(
    command: str = "",
    intent: str = "",
    chunked: bool = False,
    action: str = "",
    session_id: str = "",
    batch_index: int = 0,
    batch_size: int = 28_000,
) -> dict[str, Any]:
    """Execute a command via omniCell nuShell.

    Universal shell - auto-detects observe vs mutate.

    Args:
        command: Any terminal command to execute
        intent: Optional explicit intent (observe|mutate), overrides auto-classification
        chunked: Whether to return chunked payload session metadata
        action: Optional action for chunked mode (start|batch)
        session_id: Session id from previous action=start response
        batch_index: Requested batch index for action=batch
        batch_size: Character size per chunk when creating a session

    Returns:
        dict with status, data, and metadata
    """
    action_name, action_error = validate_chunked_action(
        action,
        allowed_actions={"start", "batch"},
    )
    if action_error is not None:
        return action_error

    if action_name == "batch":
        return _NUSHELL_CHUNKED_STORE.get_batch_payload(
            session_id=session_id,
            batch_index=batch_index,
            action_name="batch",
        )

    if not command.strip():
        return build_status_message_response(
            status="error",
            message="command is required",
        )

    runner = get_runner()

    intent_name = (intent or "").strip().lower()
    if intent_name == ActionType.OBSERVE.value:
        run_action = ActionType.OBSERVE
    elif intent_name == ActionType.MUTATE.value:
        run_action = ActionType.MUTATE
    else:
        run_action = runner.classify(command)

    # Execute via omniCell
    result = await runner.run(command, action=run_action, ensure_structured=True)

    payload = {
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "data": result.data,
        "error": result.error_message,
    }

    if not chunked and action_name != "start":
        return payload

    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    size = _normalize_batch_size(batch_size)
    return _NUSHELL_CHUNKED_STORE.create_start_payload(
        content=encoded,
        batch_size=size,
        metadata={"tool": "omniCell.nuShell", "result_status": payload.get("status", "unknown")},
        action_name="start",
        batch_action_name="batch",
        status="success",
        message_template=(
            "Call omniCell.nuShell with action='batch', session_id, and "
            "batch_index=0..batch_count-1 to read all chunks."
        ),
        extra={"result_status": payload.get("status", "unknown")},
    )
