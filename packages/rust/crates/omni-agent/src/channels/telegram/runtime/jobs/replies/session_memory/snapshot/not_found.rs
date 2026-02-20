use serde_json::json;

use super::super::super::shared::{format_optional_str, format_optional_string, format_yes_no};
use super::super::metrics::format_memory_recall_metrics_json;
use super::super::runtime::{
    format_memory_gate_policy_compact_line, format_memory_runtime_status_json,
    format_memory_runtime_status_lines, memory_backend_ready,
};

pub(in crate::channels::telegram::runtime::jobs) fn format_memory_recall_not_found(
    runtime_status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    let mut lines = vec![
        "## Session Memory".to_string(),
        "No memory recall snapshot found for this session yet.".to_string(),
        "".to_string(),
        "### Persistence".to_string(),
    ];
    lines.extend(format_memory_runtime_status_lines(runtime_status));
    lines.extend([
        "".to_string(),
        "### Next Step".to_string(),
        "- Send at least one normal turn first (non-command message).".to_string(),
        "- Then run `/session memory` again.".to_string(),
    ]);
    lines.join("\n")
}

pub(in crate::channels::telegram::runtime::jobs) fn format_memory_recall_not_found_telegram(
    runtime_status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    let backend_ready = memory_backend_ready(&runtime_status);
    [
        "## Session Memory".to_string(),
        "No memory recall snapshot found for this session yet.".to_string(),
        "".to_string(),
        "### Persistence".to_string(),
        format!(
            "- `memory_enabled={}` `backend_ready={}` `startup_load_status={}`",
            format_yes_no(runtime_status.enabled),
            format_yes_no(backend_ready),
            runtime_status.startup_load_status
        ),
        format!(
            "- `active_backend={}` `configured_backend={}`",
            format_optional_str(runtime_status.active_backend),
            format_optional_string(runtime_status.configured_backend.clone())
        ),
        format_memory_gate_policy_compact_line(&runtime_status),
        "".to_string(),
        "### Next Step".to_string(),
        "- Send at least one normal turn first (non-command message).".to_string(),
        "- Then run `/session memory` again.".to_string(),
        "- Use `/session memory json` for full payload.".to_string(),
    ]
    .join("\n")
}

pub(in crate::channels::telegram::runtime::jobs) fn format_memory_recall_not_found_json(
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
    runtime_status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    json!({
        "kind": "session_memory",
        "available": false,
        "status": "not_found",
        "hint": "Run at least one normal turn first (non-command message).",
        "runtime": format_memory_runtime_status_json(runtime_status),
        "metrics": format_memory_recall_metrics_json(metrics),
    })
    .to_string()
}
