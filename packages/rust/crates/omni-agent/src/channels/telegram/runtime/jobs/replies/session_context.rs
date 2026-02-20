use serde_json::json;

use super::shared::format_context_mode;

pub(in super::super) fn format_session_context_snapshot(
    session_id: &str,
    partition_key: &str,
    partition_mode: &str,
    active: crate::agent::SessionContextWindowInfo,
    snapshot: Option<crate::agent::SessionContextSnapshotInfo>,
) -> String {
    let mut lines = vec![
        "============================================================".to_string(),
        "session-context dashboard".to_string(),
        "============================================================".to_string(),
        "Overview:".to_string(),
        format!("  logical_session_id={session_id}"),
        format!("  partition_key={partition_key}"),
        format!("  partition_mode={partition_mode}"),
        format!("  mode={}", format_context_mode(active.mode)),
        "------------------------------------------------------------".to_string(),
        "Active:".to_string(),
        format!("  messages={}", active.messages),
        format!("  summary_segments={}", active.summary_segments),
    ];
    if let Some(window_turns) = active.window_turns {
        lines.push(format!("  window_turns={window_turns}"));
    }
    if let Some(window_slots) = active.window_slots {
        lines.push(format!("  window_slots={window_slots}"));
    }
    if let Some(total_tool_calls) = active.total_tool_calls {
        lines.push(format!("  window_tool_calls={total_tool_calls}"));
    }
    lines.push("------------------------------------------------------------".to_string());
    lines.push("Saved Snapshot:".to_string());
    match snapshot {
        Some(info) => {
            lines.push("  status=available".to_string());
            lines.push(format!("  saved_messages={}", info.messages));
            lines.push(format!(
                "  saved_summary_segments={}",
                info.summary_segments
            ));
            if let Some(saved_at_unix_ms) = info.saved_at_unix_ms {
                lines.push(format!("  saved_at_unix_ms={saved_at_unix_ms}"));
            }
            if let Some(saved_age_secs) = info.saved_age_secs {
                lines.push(format!("  saved_age_secs={saved_age_secs}"));
            }
            lines.push("  restore_hint=/resume".to_string());
        }
        None => {
            lines.push("  status=none".to_string());
        }
    }
    lines.push("============================================================".to_string());
    lines.join("\n")
}

pub(in super::super) fn format_session_context_snapshot_json(
    session_id: &str,
    partition_key: &str,
    partition_mode: &str,
    active: crate::agent::SessionContextWindowInfo,
    snapshot: Option<crate::agent::SessionContextSnapshotInfo>,
) -> String {
    let snapshot_json = match snapshot {
        Some(info) => json!({
            "status": "available",
            "saved_messages": info.messages,
            "saved_summary_segments": info.summary_segments,
            "saved_at_unix_ms": info.saved_at_unix_ms,
            "saved_age_secs": info.saved_age_secs,
            "restore_hint": "/resume",
        }),
        None => json!({
            "status": "none",
        }),
    };

    json!({
        "kind": "session_context",
        "logical_session_id": session_id,
        "partition_key": partition_key,
        "partition_mode": partition_mode,
        "mode": format_context_mode(active.mode),
        "active": {
            "messages": active.messages,
            "summary_segments": active.summary_segments,
            "window_turns": active.window_turns,
            "window_slots": active.window_slots,
            "window_tool_calls": active.total_tool_calls,
        },
        "saved_snapshot": snapshot_json,
    })
    .to_string()
}
