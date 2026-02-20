use serde_json::json;

pub(in super::super) fn format_context_budget_snapshot(
    snapshot: crate::agent::SessionContextBudgetSnapshot,
) -> String {
    let classes = [
        ("non_system", snapshot.non_system),
        ("regular_system", snapshot.regular_system),
        ("summary_system", snapshot.summary_system),
    ];

    let mut largest_drop = ("none", 0usize);
    let mut largest_trunc = ("none", 0usize);
    for (name, class) in classes {
        if class.dropped_tokens > largest_drop.1 {
            largest_drop = (name, class.dropped_tokens);
        }
        if class.truncated_tokens > largest_trunc.1 {
            largest_trunc = (name, class.truncated_tokens);
        }
    }

    let mut lines = vec![
        "============================================================".to_string(),
        "session-budget dashboard".to_string(),
        "============================================================".to_string(),
        "Overview:".to_string(),
        format!("  captured_at_unix_ms={}", snapshot.created_at_unix_ms),
        format!("  strategy={}", snapshot.strategy.as_str()),
        format!(
            "  budget={} reserve={} effective={}",
            snapshot.budget_tokens, snapshot.reserve_tokens, snapshot.effective_budget_tokens
        ),
        format!(
            "  messages={} -> {} (dropped={})",
            snapshot.pre_messages, snapshot.post_messages, snapshot.dropped_messages
        ),
        format!(
            "  tokens={} -> {} (dropped={})",
            snapshot.pre_tokens, snapshot.post_tokens, snapshot.dropped_tokens
        ),
        "------------------------------------------------------------".to_string(),
        "Classes:".to_string(),
        "  class           in_msg  kept  drop  trunc  in_tok  kept   drop   trunc".to_string(),
    ];
    lines.extend(format_context_budget_class_row(
        "non_system",
        &snapshot.non_system,
    ));
    lines.extend(format_context_budget_class_row(
        "regular_system",
        &snapshot.regular_system,
    ));
    lines.extend(format_context_budget_class_row(
        "summary_system",
        &snapshot.summary_system,
    ));
    lines.extend([
        "------------------------------------------------------------".to_string(),
        "Bottlenecks:".to_string(),
        format!(
            "  largest_dropped_tokens={} ({})",
            largest_drop.0, largest_drop.1
        ),
        format!(
            "  largest_truncated_tokens={} ({})",
            largest_trunc.0, largest_trunc.1
        ),
        "============================================================".to_string(),
    ]);
    lines.join("\n")
}

pub(in super::super) fn format_context_budget_snapshot_json(
    snapshot: crate::agent::SessionContextBudgetSnapshot,
) -> String {
    let classes = [
        ("non_system", snapshot.non_system),
        ("regular_system", snapshot.regular_system),
        ("summary_system", snapshot.summary_system),
    ];
    let mut largest_drop = ("none", 0usize);
    let mut largest_trunc = ("none", 0usize);
    for (name, class) in classes {
        if class.dropped_tokens > largest_drop.1 {
            largest_drop = (name, class.dropped_tokens);
        }
        if class.truncated_tokens > largest_trunc.1 {
            largest_trunc = (name, class.truncated_tokens);
        }
    }

    json!({
        "kind": "session_budget",
        "available": true,
        "captured_at_unix_ms": snapshot.created_at_unix_ms,
        "strategy": snapshot.strategy.as_str(),
        "budget_tokens": snapshot.budget_tokens,
        "reserve_tokens": snapshot.reserve_tokens,
        "effective_budget_tokens": snapshot.effective_budget_tokens,
        "messages": {
            "pre": snapshot.pre_messages,
            "post": snapshot.post_messages,
            "dropped": snapshot.dropped_messages,
        },
        "tokens": {
            "pre": snapshot.pre_tokens,
            "post": snapshot.post_tokens,
            "dropped": snapshot.dropped_tokens,
        },
        "classes": {
            "non_system": format_context_budget_class_json(snapshot.non_system),
            "regular_system": format_context_budget_class_json(snapshot.regular_system),
            "summary_system": format_context_budget_class_json(snapshot.summary_system),
        },
        "bottlenecks": {
            "largest_dropped_tokens": {"class": largest_drop.0, "tokens": largest_drop.1},
            "largest_truncated_tokens": {"class": largest_trunc.0, "tokens": largest_trunc.1},
        },
    })
    .to_string()
}

pub(in super::super) fn format_context_budget_not_found_json() -> String {
    json!({
        "kind": "session_budget",
        "available": false,
        "status": "not_found",
        "hint": "Run at least one normal turn first (non-command message).",
    })
    .to_string()
}

pub(in super::super) fn format_context_budget_class_json(
    stats: crate::agent::SessionContextBudgetClassSnapshot,
) -> serde_json::Value {
    json!({
        "input_messages": stats.input_messages,
        "kept_messages": stats.kept_messages,
        "dropped_messages": stats.dropped_messages,
        "truncated_messages": stats.truncated_messages,
        "input_tokens": stats.input_tokens,
        "kept_tokens": stats.kept_tokens,
        "dropped_tokens": stats.dropped_tokens,
        "truncated_tokens": stats.truncated_tokens,
    })
}

pub(in super::super) fn format_context_budget_class_row(
    label: &str,
    stats: &crate::agent::SessionContextBudgetClassSnapshot,
) -> Vec<String> {
    vec![format!(
        "  {label:<14} {in_msg:>6} {kept:>5} {drop:>5} {trunc:>6} {in_tok:>7} {kept_tok:>6} {drop_tok:>6} {trunc_tok:>7}",
        in_msg = stats.input_messages,
        kept = stats.kept_messages,
        drop = stats.dropped_messages,
        trunc = stats.truncated_messages,
        in_tok = stats.input_tokens,
        kept_tok = stats.kept_tokens,
        drop_tok = stats.dropped_tokens,
        trunc_tok = stats.truncated_tokens,
    )]
}
