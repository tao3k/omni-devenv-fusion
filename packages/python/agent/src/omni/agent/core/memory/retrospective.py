"""
retrospective.py - Session Retrospective

Post-execution memory distillation. Creates structured summaries from completed
sessions, answering:
- What worked?
- What failed?
- New facts discovered?
- Tools used?
- Knowledge gained?

These retrospectives are then archived to VectorDB for future recall.
"""

from __future__ import annotations

from typing import Any


def create_session_retrospective(
    session_id: str,
    messages: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
    outcome: str,
) -> dict[str, Any]:
    """
    Create a session retrospective summary.

    Distills a completed session into structured insights:
    - What worked (successful patterns)
    - What failed (errors encountered)
    - New facts (discovered information)
    - Tools used (actionable breakdown)
    - Knowledge gained (wisdom to save)

    Args:
        session_id: Unique identifier for this session
        messages: All messages from the session
        tool_calls: All tool invocations
        outcome: Session outcome (COMPLETED, FAILED, PARTIAL, EMPTY)

    Returns:
        Dictionary containing structured retrospective data
    """
    # Extract role counts
    role_counts: dict[str, int] = {}
    for msg in messages:
        role = msg.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    # Extract tool usage (deduplicated)
    tools_used: list[str] = []
    for call in tool_calls:
        tool_name = call.get("name", "unknown")
        if tool_name not in tools_used:
            tools_used.append(tool_name)

    # Count successful vs failed tool calls
    successful_calls = sum(1 for c in tool_calls if c.get("status") == "success")
    failed_calls = sum(1 for c in tool_calls if c.get("status") == "failed")

    # Analyze message content for key patterns
    successful_actions: list[str] = []
    failed_actions: list[str] = []
    new_facts: list[str] = []

    for msg in messages:
        content = str(msg.get("content", ""))

        # Detect success indicators
        if any(
            kw in content.lower() for kw in ["success", "completed", "fixed", "done", "created"]
        ):
            # Exclude error-containing messages
            if "error" not in content.lower() and "failed" not in content.lower():
                # Extract concise action description
                if len(content) < 150:
                    successful_actions.append(content)

        # Detect new facts (informational discoveries)
        if len(content) > 30 and any(
            kw in content.lower()
            for kw in ["found", "discovered", "revealed", "identified", "the issue is"]
        ):
            new_facts.append(content[:150])

    # Build retrospective
    retro: dict[str, Any] = {
        "session_id": session_id,
        "outcome": outcome,
        "role_counts": role_counts,
        "tools_used": tools_used,
        "successful_patterns": successful_actions[:5],  # Top 5
        "failed_patterns": failed_actions[:3],  # Top 3
        "new_facts": new_facts[:3],  # Top 3
        "metrics": {
            "total_messages": len(messages),
            "total_tool_calls": len(tool_calls),
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": successful_calls / max(len(tool_calls), 1),
        },
    }

    return retro


def format_retrospective(retro: dict[str, Any]) -> str:
    """
    Format retrospective as readable markdown.

    Args:
        retro: The retrospective dictionary from create_session_retrospective

    Returns:
        Formatted markdown string suitable for display
    """
    lines = [
        "=" * 60,
        "SESSION RETROSPECTIVE",
        "=" * 60,
        f"Session ID: {retro['session_id']}",
        f"Outcome: {retro['outcome']}",
        "",
        "-" * 40,
        "METRICS",
        "-" * 40,
        f"  Total Messages: {retro['metrics']['total_messages']}",
        f"  Total Tool Calls: {retro['metrics']['total_tool_calls']}",
        f"  Successful: {retro['metrics']['successful_calls']}",
        f"  Failed: {retro['metrics']['failed_calls']}",
        f"  Success Rate: {retro['metrics']['success_rate']:.1%}",
        "",
        "-" * 40,
        "ROLE BREAKDOWN",
        "-" * 40,
    ]

    for role, count in retro["role_counts"].items():
        lines.append(f"  {role}: {count}")

    if retro["tools_used"]:
        lines.extend(["", "-" * 40, "TOOLS USED", "-" * 40])
        for tool in retro["tools_used"]:
            lines.append(f"  - {tool}")

    if retro.get("successful_patterns"):
        lines.extend(["", "-" * 40, "WHAT WORKED", "-" * 40])
        for pattern in retro["successful_patterns"]:
            lines.append(f"  - {pattern[:100]}")

    if retro.get("failed_patterns"):
        lines.extend(["", "-" * 40, "WHAT FAILED", "-" * 40])
        for pattern in retro["failed_patterns"]:
            lines.append(f"  - {pattern[:100]}")

    if retro.get("new_facts"):
        lines.extend(["", "-" * 40, "NEW FACTS DISCOVERED", "-" * 40])
        for fact in retro["new_facts"]:
            lines.append(f"  - {fact[:100]}")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def extract_knowledge_to_save(retro: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract knowledge entries from retrospective for VectorDB storage.

    Args:
        retro: The retrospective dictionary

    Returns:
        List of knowledge entries ready for VectorDB storage
    """
    entries: list[dict[str, Any]] = []

    # Save successful patterns
    for pattern in retro.get("successful_patterns", []):
        entries.append(
            {
                "content": f"Successful approach: {pattern}",
                "metadata": {
                    "type": "session_retrospective",
                    "category": "successful_pattern",
                    "session_id": retro["session_id"],
                },
            }
        )

    # Save new facts
    for fact in retro.get("new_facts", []):
        entries.append(
            {
                "content": f"Discovered: {fact}",
                "metadata": {
                    "type": "session_retrospective",
                    "category": "new_fact",
                    "session_id": retro["session_id"],
                },
            }
        )

    return entries


__all__ = [
    "create_session_retrospective",
    "format_retrospective",
    "extract_knowledge_to_save",
]
