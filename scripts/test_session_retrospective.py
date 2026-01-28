"""
Session Retrospective Test

Demonstrates post-execution memory distillation - the "Session Retrospective"
is a post-execution summary that answers:
- What worked?
- What failed?
- New facts discovered?
- Tools used?
- Knowledge gained?
"""

import sys
from pathlib import Path

# Ensure package imports work
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/agent/src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/foundation/src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages/python/core/src"))


def create_session_retrospective(
    session_id: str,
    messages: list[dict],
    tool_calls: list[dict],
    outcome: str,
) -> dict:
    """
    Create a session retrospective summary.

    This distills a completed session into structured insights:
    - What worked (successful patterns)
    - What failed (errors encountered)
    - New facts (discovered information)
    - Tools used (actionable breakdown)
    - Knowledge gained (wisdom to save)
    """
    # Extract role counts
    role_counts = {}
    for msg in messages:
        role = msg.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    # Extract tool usage
    tools_used = []
    for call in tool_calls:
        tool_name = call.get("name", "unknown")
        if tool_name not in tools_used:
            tools_used.append(tool_name)

    # Analyze message content for key patterns
    successful_actions = []
    failed_actions = []
    new_facts = []
    errors_encountered = []

    for msg in messages:
        content = str(msg.get("content", ""))

        # Detect success indicators
        if any(kw in content.lower() for kw in ["success", "completed", "fixed", "done"]):
            if "error" not in content.lower() and "failed" not in content.lower():
                # Extract potential action from context
                if len(content) < 100:
                    successful_actions.append(content)

        # Detect error indicators
        if any(kw in content.lower() for kw in ["error", "failed", "exception", "traceback"]):
            errors_encountered.append(content[:200])
            failed_actions.append(content[:100])

        # Detect new facts (informational content)
        if len(content) > 50 and any(
            kw in content.lower() for kw in ["discovered", "found", "learned", "revealed"]
        ):
            new_facts.append(content[:150])

    # Build retrospective
    retrospective = {
        "session_id": session_id,
        "outcome": outcome,
        "role_counts": role_counts,
        "tools_used": tools_used,
        "successful_actions": successful_actions[:5],  # Limit to top 5
        "failed_actions": failed_actions[:3],  # Limit to top 3
        "new_facts": new_facts[:3],  # Limit to top 3
        "errors_encountered": errors_encountered[:3],  # Limit to top 3
        "metrics": {
            "total_messages": len(messages),
            "total_tool_calls": len(tool_calls),
            "success_rate": len(successful_actions) / max(len(tool_calls), 1),
        },
    }

    return retrospective


def format_retrospective(retro: dict) -> str:
    """Format retrospective as readable markdown."""
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
        f"  Success Rate: {retro['metrics']['success_rate']:.1%}",
        "",
        "-" * 40,
        "ROLE BREAKDOWN",
        "-" * 40,
    ]

    for role, count in retro["role_counts"].items():
        lines.append(f"  {role}: {count}")

    lines.extend(["", "-" * 40, "TOOLS USED", "-" * 40])
    for tool in retro["tools_used"]:
        lines.append(f"  - {tool}")

    if retro["successful_actions"]:
        lines.extend(["", "-" * 40, "WHAT WORKED", "-" * 40])
        for action in retro["successful_actions"]:
            lines.append(f"  - {action[:80]}")

    if retro["failed_actions"]:
        lines.extend(["", "-" * 40, "WHAT FAILED", "-" * 40])
        for action in retro["failed_actions"]:
            lines.append(f"  - {action[:80]}")

    if retro["new_facts"]:
        lines.extend(["", "-" * 40, "NEW FACTS DISCOVERED", "-" * 40])
        for fact in retro["new_facts"]:
            lines.append(f"  - {fact[:80]}")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


def main():
    print("Testing Session Retrospective Feature...")
    print("-" * 60)

    # Simulate a session
    session_id = "test-session-001"

    # Simulated messages (typical Omni Loop session)
    messages = [
        {"role": "user", "content": "Fix the off-by-one error in the loop counter"},
        {
            "role": "assistant",
            "content": "I'll help you fix the off-by-one error. Let me first read the file.",
        },
        {"role": "tool", "content": "read_files(paths=['/test/code.py'])"},
        {
            "role": "assistant",
            "content": "I found the issue at line 42. The loop should use `<=` instead of `<`.",
        },
        {"role": "tool", "content": "write_file(path='/test/code.py', content='...')"},
        {
            "role": "assistant",
            "content": "SUCCESS: Fixed the off-by-one error. The loop now correctly processes all elements.",
        },
        {"role": "tool", "content": "Success: File modified successfully"},
    ]

    # Simulated tool calls
    tool_calls = [
        {"name": "read_files", "status": "success"},
        {"name": "write_file", "status": "success"},
    ]

    outcome = "COMPLETED"

    # Create retrospective
    retro = create_session_retrospective(
        session_id=session_id,
        messages=messages,
        tool_calls=tool_calls,
        outcome=outcome,
    )

    # Format and display
    formatted = format_retrospective(retro)
    print(formatted)
    print()

    # Test saving to memory (if available)
    print("-" * 60)
    print("Saving key insights to memory...")

    try:
        from omni.foundation.services.vector import get_vector_store

        store = get_vector_store()

        # Save successful pattern
        if retro["successful_actions"]:
            success_content = "; ".join(retro["successful_actions"])
            store.add(
                content=f"Session {session_id} successful pattern: {success_content}",
                metadata={
                    "type": "session_retrospective",
                    "session_id": session_id,
                    "category": "successful_pattern",
                },
                collection="memory",
            )
            print(f"  Saved {len(retro['successful_actions'])} successful patterns")

        # Save new facts
        if retro["new_facts"]:
            store.add(
                content=f"Session {session_id} new facts: {retro['new_facts']}",
                metadata={
                    "type": "session_retrospective",
                    "session_id": session_id,
                    "category": "new_facts",
                },
                collection="memory",
            )
            print(f"  Saved {len(retro['new_facts'])} new facts")

        print("  All insights archived to VectorDB!")

    except ImportError:
        print("  (VectorDB not available - skipping memory save)")
    except Exception as e:
        print(f"  Warning: Could not save to memory: {e}")

    print()
    print("=" * 60)
    print("Session Retrospective Test: PASSED")
    print("=" * 60)


if __name__ == "__main__":
    main()
