#![allow(missing_docs)]

use std::collections::HashSet;

#[path = "../src/observability/session_events.rs"]
mod session_events;

use session_events::SessionEvent;

#[test]
fn session_event_ids_are_non_empty_and_unique() {
    let mut seen = HashSet::new();
    for event in SessionEvent::ALL {
        let id = event.as_str();
        assert!(!id.is_empty());
        assert!(
            seen.insert(id),
            "duplicate observability event id detected: {id}"
        );
    }
}

#[test]
fn session_event_ids_follow_namespace_convention() {
    for event in SessionEvent::ALL {
        let id = event.as_str();
        assert!(
            id.starts_with("session.")
                || id.starts_with("agent.memory.")
                || id.starts_with("telegram.dedup."),
            "unexpected event namespace: {id}"
        );
    }
}

#[test]
fn memory_persistence_events_are_registered() {
    let ids: HashSet<&str> = SessionEvent::ALL
        .iter()
        .copied()
        .map(SessionEvent::as_str)
        .collect();

    for expected in [
        "agent.memory.backend.initialized",
        "agent.memory.state_load_succeeded",
        "agent.memory.state_load_failed",
        "agent.memory.state_save_succeeded",
        "agent.memory.state_save_failed",
        "agent.memory.recall.planned",
        "agent.memory.recall.injected",
        "agent.memory.recall.skipped",
        "agent.memory.recall.credit_applied",
        "agent.memory.recall.feedback_updated",
        "agent.memory.gate.evaluated",
        "agent.memory.decay.applied",
        "agent.memory.stream_consumer.started",
        "agent.memory.stream_consumer.disabled",
        "agent.memory.stream_consumer.group_ready",
        "agent.memory.stream_consumer.event_processed",
        "agent.memory.stream_consumer.read_failed",
    ] {
        assert!(
            ids.contains(expected),
            "missing expected memory observability event: {expected}"
        );
    }
}
