#![allow(missing_docs)]

use omni_agent::{ChatMessage, prune_messages_for_token_budget};

fn msg(role: &str, content: &str) -> ChatMessage {
    msg_named(role, content, None)
}

fn msg_named(role: &str, content: &str, name: Option<&str>) -> ChatMessage {
    ChatMessage {
        role: role.to_string(),
        content: Some(content.to_string()),
        tool_calls: None,
        tool_call_id: None,
        name: name.map(str::to_string),
    }
}

#[test]
fn keeps_latest_non_system_message_under_budget() {
    let messages = vec![
        msg("system", "session policy"),
        msg("user", &"old context ".repeat(80)),
        msg("assistant", &"older assistant output ".repeat(80)),
        msg("user", "latest request"),
    ];

    let pruned = prune_messages_for_token_budget(messages, 64, 0);
    assert!(!pruned.is_empty());

    let last = pruned.last().expect("latest message should remain");
    assert_eq!(last.role, "user");
    assert_eq!(last.content.as_deref(), Some("latest request"));
}

#[test]
fn reserve_tokens_reduces_retained_context() {
    let messages = vec![
        msg("system", &"policy ".repeat(80)),
        msg("user", &"old user context ".repeat(80)),
        msg("assistant", &"old assistant context ".repeat(80)),
        msg("user", "latest request"),
    ];

    let without_reserve = prune_messages_for_token_budget(messages.clone(), 256, 0);
    let with_reserve = prune_messages_for_token_budget(messages, 256, 220);

    assert!(with_reserve.len() <= without_reserve.len());

    let with_reserve_chars: usize = with_reserve
        .iter()
        .filter_map(|m| m.content.as_ref())
        .map(String::len)
        .sum();
    let without_reserve_chars: usize = without_reserve
        .iter()
        .filter_map(|m| m.content.as_ref())
        .map(String::len)
        .sum();

    assert!(with_reserve_chars <= without_reserve_chars);
}

#[test]
fn truncates_oversized_system_message() {
    let original = "system context ".repeat(200);
    let messages = vec![msg("system", &original)];

    let pruned = prune_messages_for_token_budget(messages, 48, 0);
    assert_eq!(pruned.len(), 1);
    assert_eq!(pruned[0].role, "system");

    let content = pruned[0]
        .content
        .as_ref()
        .expect("truncated system content should exist");
    assert!(!content.trim().is_empty());
    assert!(content.len() < original.len());
}

#[test]
fn returns_empty_when_budget_is_zero() {
    let messages = vec![msg("user", "latest request")];
    let pruned = prune_messages_for_token_budget(messages, 0, 0);
    assert!(pruned.is_empty());
}

#[test]
fn keeps_recent_dialogue_before_summary_segments() {
    let messages = vec![
        msg_named(
            "system",
            &format!("OLD SUMMARY {}", "x ".repeat(400)),
            Some("session.summary.segment"),
        ),
        msg_named(
            "system",
            &format!("NEW SUMMARY {}", "y ".repeat(400)),
            Some("session.summary.segment"),
        ),
        msg("user", "recent-user"),
        msg("assistant", "recent-assistant"),
        msg("user", "latest request"),
    ];

    let pruned = prune_messages_for_token_budget(messages, 40, 0);
    let contents = pruned
        .iter()
        .filter_map(|m| m.content.as_deref())
        .collect::<Vec<_>>();
    assert!(contents.contains(&"latest request"));
    assert!(contents.contains(&"recent-assistant"));
    assert!(contents.contains(&"recent-user"));
}

#[test]
fn keeps_newer_summary_segment_when_budget_only_fits_one() {
    let messages = vec![
        msg_named(
            "system",
            &format!("OLD SUMMARY {}", "old ".repeat(120)),
            Some("session.summary.segment"),
        ),
        msg_named(
            "system",
            &format!("NEW SUMMARY {}", "new ".repeat(120)),
            Some("session.summary.segment"),
        ),
        msg("user", "latest request"),
    ];

    let pruned = prune_messages_for_token_budget(messages, 26, 0);
    let system_contents = pruned
        .iter()
        .filter(|m| m.role == "system")
        .filter_map(|m| m.content.as_deref())
        .collect::<Vec<_>>();

    assert_eq!(system_contents.len(), 1);
    assert!(system_contents[0].contains("NEW SUMMARY"));
}
