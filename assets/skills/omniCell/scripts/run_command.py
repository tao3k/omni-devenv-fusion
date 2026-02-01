"""omniCell.execute - Structured OS Interaction

Trinity Architecture - Core Layer

Unified command execution via Nushell with structured JSON output.
Replaces bash for agent workflows.
"""

from typing import Any

from omni.foundation.api.decorators import skill_command
from omni.core.skills.runtime.omni_cell import ActionType, CellResult, get_runner


@skill_command(
    name="execute",
    description="""
    Execute Nushell command with structured JSON output.

    Features:
    - Intent Classification: Auto-detects 'observe' vs 'mutate' operations
    - Safety Analysis: Blocks dangerous commands (rm -rf /, fork bombs, mkfs)
    - Structured Output: All results returned as JSON

    Args:
        - command: Nushell command string
        - intent: 'observe' (read-only) or 'mutate' (write operations)

    Returns:
        Dictionary with status, parsed data, and execution metadata.
    """,
    read_only=False,
    destructive=False,
    idempotent=False,
    open_world=False,
)
async def execute(
    command: str,
    intent: str = "observe",
) -> dict[str, Any]:
    """Execute a command via omniCell.

    Args:
        command: Nushell command to execute
        intent: 'observe' for read-only, 'mutate' for side-effects

    Returns:
        dict with status, data, and metadata
    """
    runner = get_runner()

    # Convert intent string to ActionType
    action = ActionType(intent) if intent in ["observe", "mutate"] else runner.classify(command)

    # Execute via omniCell
    result: CellResult = await runner.run(command, action=action, ensure_structured=True)

    # Convert to dict for JSON serialization
    return {
        "status": result.status,
        "data": result.data,
        "metadata": result.metadata,
        "security_check": result.security_check,
    }
