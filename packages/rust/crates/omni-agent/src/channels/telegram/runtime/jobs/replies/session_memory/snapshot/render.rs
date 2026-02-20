use serde_json::json;

use super::super::super::shared::{
    format_optional_f32, format_optional_str, format_optional_string, format_optional_usize,
    format_yes_no,
};
use super::super::metrics::{
    format_memory_recall_metrics_json, format_memory_recall_metrics_lines,
};
use super::super::runtime::{
    format_memory_gate_policy_compact_line, format_memory_runtime_status_json,
    format_memory_runtime_status_lines, memory_backend_ready,
};

pub(in crate::channels::telegram::runtime::jobs) fn format_memory_recall_snapshot(
    snapshot: crate::agent::SessionMemoryRecallSnapshot,
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
    runtime_status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    let mut lines = vec![
        "## Session Memory".to_string(),
        format!("Captured at unix ms: `{}`", snapshot.created_at_unix_ms),
        "".to_string(),
        "### Trigger".to_string(),
        format!("- Decision: `{}`", snapshot.decision.as_str()),
        format!("- Query tokens: `{}`", snapshot.query_tokens),
        format!(
            "- Recall feedback bias: `{:.3}`",
            snapshot.recall_feedback_bias
        ),
        format!("- Embedding source: `{}`", snapshot.embedding_source),
        format!(
            "- Pipeline duration: `{} ms`",
            snapshot.pipeline_duration_ms
        ),
        "".to_string(),
        "### Persistence".to_string(),
    ];
    lines.extend(format_memory_runtime_status_lines(runtime_status));
    lines.extend([
        "".to_string(),
        "### Recall Plan".to_string(),
        format!("- `k1={}` / `k2={}`", snapshot.k1, snapshot.k2),
        format!("- `lambda={:.3}`", snapshot.lambda),
        format!("- `min_score={:.3}`", snapshot.min_score),
        format!("- `max_context_chars={}`", snapshot.max_context_chars),
        "".to_string(),
        "### Context Pressure".to_string(),
        format!("- `budget_pressure={:.3}`", snapshot.budget_pressure),
        format!("- `window_pressure={:.3}`", snapshot.window_pressure),
        format!(
            "- `effective_budget_tokens={}`",
            format_optional_usize(snapshot.effective_budget_tokens)
        ),
        format!(
            "- `active_turns_estimate={}`",
            snapshot.active_turns_estimate
        ),
        format!(
            "- `summary_segment_count={}`",
            snapshot.summary_segment_count
        ),
        "".to_string(),
        "### Recall Result".to_string(),
        format!("- `recalled_total={}`", snapshot.recalled_total),
        format!("- `recalled_selected={}`", snapshot.recalled_selected),
        format!("- `recalled_injected={}`", snapshot.recalled_injected),
        format!(
            "- `context_chars_injected={}`",
            snapshot.context_chars_injected
        ),
        format!(
            "- `best_score={}`",
            format_optional_f32(snapshot.best_score)
        ),
        format!(
            "- `weakest_score={}`",
            format_optional_f32(snapshot.weakest_score)
        ),
        "".to_string(),
        "### Process Metrics".to_string(),
    ]);
    lines.extend(format_memory_recall_metrics_lines(metrics));
    lines.join("\n")
}

pub(in crate::channels::telegram::runtime::jobs) fn format_memory_recall_snapshot_telegram(
    snapshot: crate::agent::SessionMemoryRecallSnapshot,
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
    runtime_status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    let backend_ready = memory_backend_ready(&runtime_status);
    [
        "## Session Memory".to_string(),
        format!("Captured at unix ms: `{}`", snapshot.created_at_unix_ms),
        "".to_string(),
        "### Trigger - Decision".to_string(),
        format!(
            "- `decision={}` `query_tokens={}` `pipeline_ms={}`",
            snapshot.decision.as_str(),
            snapshot.query_tokens,
            snapshot.pipeline_duration_ms
        ),
        format!(
            "- `feedback_bias={:.3}` `embedding_source={}`",
            snapshot.recall_feedback_bias, snapshot.embedding_source
        ),
        "".to_string(),
        "### Recall Result".to_string(),
        format!(
            "- `injected={}` / `selected={}` / `total={}`",
            snapshot.recalled_injected, snapshot.recalled_selected, snapshot.recalled_total
        ),
        format!(
            "- `context_chars={}` `best_score={}` `weakest_score={}`",
            snapshot.context_chars_injected,
            format_optional_f32(snapshot.best_score),
            format_optional_f32(snapshot.weakest_score)
        ),
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
        "### Adaptive Metrics".to_string(),
        format!(
            "- `planned_total={}` `completed_total={}` `injected_total={}` `skipped_total={}`",
            metrics.planned_total,
            metrics.completed_total,
            metrics.injected_total,
            metrics.skipped_total
        ),
        format!(
            "- `avg_pipeline_ms={:.2}` `injected_rate={:.3}`",
            metrics.avg_pipeline_duration_ms, metrics.injected_rate
        ),
        "".to_string(),
        "Tip: run `/session memory json` for full payload.".to_string(),
    ]
    .join("\n")
}

pub(in crate::channels::telegram::runtime::jobs) fn format_memory_recall_snapshot_json(
    snapshot: crate::agent::SessionMemoryRecallSnapshot,
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
    runtime_status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> String {
    json!({
        "kind": "session_memory",
        "available": true,
        "captured_at_unix_ms": snapshot.created_at_unix_ms,
        "decision": snapshot.decision.as_str(),
        "query_tokens": snapshot.query_tokens,
        "recall_feedback_bias": snapshot.recall_feedback_bias,
        "embedding_source": snapshot.embedding_source,
        "pipeline_duration_ms": snapshot.pipeline_duration_ms,
        "plan": {
            "k1": snapshot.k1,
            "k2": snapshot.k2,
            "lambda": snapshot.lambda,
            "min_score": snapshot.min_score,
            "max_context_chars": snapshot.max_context_chars,
        },
        "context_pressure": {
            "budget_pressure": snapshot.budget_pressure,
            "window_pressure": snapshot.window_pressure,
            "effective_budget_tokens": snapshot.effective_budget_tokens,
            "active_turns_estimate": snapshot.active_turns_estimate,
            "summary_segment_count": snapshot.summary_segment_count,
        },
        "result": {
            "recalled_total": snapshot.recalled_total,
            "recalled_selected": snapshot.recalled_selected,
            "recalled_injected": snapshot.recalled_injected,
            "context_chars_injected": snapshot.context_chars_injected,
            "best_score": snapshot.best_score,
            "weakest_score": snapshot.weakest_score,
        },
        "runtime": format_memory_runtime_status_json(runtime_status),
        "metrics": format_memory_recall_metrics_json(metrics),
    })
    .to_string()
}
