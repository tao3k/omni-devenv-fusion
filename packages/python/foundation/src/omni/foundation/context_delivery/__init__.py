"""
context_delivery - Common library for skill tool content delivery strategies.

Two distinct scenarios (see docs/reference/skill-tool-context-practices.md):

1. **Summary-only** (e.g. git diff): Extract basic info → reflect situation → write summary.
   Truncation acceptable. Use prepare_for_summary().

2. **Full-content** (e.g. researcher): Deep analysis requires full content.
   No truncation. Use ChunkedSession for chunked delivery.

Usage:
    from omni.foundation.context_delivery import (
        prepare_for_summary,
        ChunkedSession,
        ChunkedSessionStore,
        WorkflowStateStore,
        ActionWorkflowEngine,
        create_chunked_session,
    )

    # Git diff scenario
    diff_preview = prepare_for_summary(full_diff, max_chars=8000)

    # Researcher scenario
    session = create_chunked_session(repomix_xml, batch_size=28000)
    batch_0 = session.get_batch(0)

    # Chunked action=start/batch scenario
    store = ChunkedSessionStore("omnicell_nushell_chunked")
    persisted = store.create(very_large_payload, batch_size=28000)
    batch_payload = store.get_batch_payload(session_id=persisted.session_id, batch_index=0)

    # Generic action-based workflow state
    workflow_store = WorkflowStateStore("smart_commit")
    workflow_store.save("wf_123", {"status": "prepared"})

    # Generic action dispatch with shared validation
    engine = ActionWorkflowEngine(
        workflow_type="smart_commit",
        allowed_actions={"start", "approve", "status"},
    )
"""

from omni.foundation.context_delivery.sessions import (
    ActionWorkflowEngine,
    ChunkedSessionStore,
    WorkflowStateStore,
    normalize_chunked_action_name,
    validate_chunked_action,
)
from omni.foundation.context_delivery.strategies import (
    ChunkedSession,
    create_chunked_session,
    prepare_for_summary,
)

__all__ = [
    "ActionWorkflowEngine",
    "ChunkedSession",
    "ChunkedSessionStore",
    "WorkflowStateStore",
    "create_chunked_session",
    "normalize_chunked_action_name",
    "prepare_for_summary",
    "validate_chunked_action",
]
