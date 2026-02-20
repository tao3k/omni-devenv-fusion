use serde_json::json;

use crate::agent::{SessionContextMode, SessionRecallFeedbackDirection};
use crate::channels::managed_runtime::replies as shared_replies;
use crate::channels::managed_runtime::session_partition::{
    SessionPartitionProfile, quick_toggle_usage, set_mode_usage, supported_modes,
    supported_modes_csv,
};
use crate::jobs::{JobMetricsSnapshot, JobStatusSnapshot};

const PERMISSION_HINTS: shared_replies::PermissionHints<'static> =
    shared_replies::PermissionHints {
        control_command_hint: "Ask an identity allowed by `discord.control_command_allow_from` (or matching `discord.admin_command_rules` / `discord.admin_users`) to run this command.",
        slash_command_hint: "Ask an admin to grant this command via `discord.slash_*_allow_from` settings.",
    };

pub(super) fn format_job_status(snapshot: &JobStatusSnapshot) -> String {
    shared_replies::format_job_status(snapshot)
}

pub(super) fn format_job_metrics(metrics: &JobMetricsSnapshot) -> String {
    shared_replies::format_job_metrics(metrics)
}

pub(super) fn format_job_not_found(job_id: &str) -> String {
    shared_replies::format_job_not_found(job_id)
}

pub(super) fn format_job_status_json(snapshot: &JobStatusSnapshot) -> String {
    shared_replies::format_job_status_json(snapshot)
}

pub(super) fn format_job_metrics_json(metrics: &JobMetricsSnapshot) -> String {
    shared_replies::format_job_metrics_json(metrics)
}

pub(super) fn format_job_not_found_json(job_id: &str) -> String {
    shared_replies::format_job_not_found_json(job_id)
}

pub(super) fn format_context_mode(mode: SessionContextMode) -> &'static str {
    match mode {
        SessionContextMode::Bounded => "bounded",
        SessionContextMode::Unbounded => "unbounded",
    }
}

pub(super) fn format_session_context_snapshot(
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

pub(super) fn format_session_context_snapshot_json(
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

pub(super) fn format_memory_recall_snapshot(
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

pub(super) fn format_memory_recall_snapshot_json(
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

pub(super) fn format_memory_recall_not_found(
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

pub(super) fn format_memory_recall_not_found_json(
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

pub(super) fn format_session_feedback(
    direction: SessionRecallFeedbackDirection,
    previous_bias: f32,
    updated_bias: f32,
) -> String {
    shared_replies::format_session_feedback(direction, previous_bias, updated_bias)
}

pub(super) fn format_session_feedback_json(
    direction: SessionRecallFeedbackDirection,
    previous_bias: f32,
    updated_bias: f32,
) -> String {
    shared_replies::format_session_feedback_json(direction, previous_bias, updated_bias)
}

pub(super) fn format_session_feedback_unavailable_json() -> String {
    shared_replies::format_session_feedback_unavailable_json()
}

pub(super) fn format_session_partition_status(current_mode: &str) -> String {
    let profile = SessionPartitionProfile::Discord;
    [
        "Session partition status.".to_string(),
        format!("current_mode={current_mode}"),
        format!("supported_modes={}", supported_modes_csv(profile)),
        format!("quick_toggle={}", quick_toggle_usage()),
        format!("set_mode={}", set_mode_usage(profile)),
        "scope=runtime (takes effect for new incoming messages)".to_string(),
    ]
    .join("\n")
}

pub(super) fn format_session_partition_status_json(current_mode: &str) -> String {
    let profile = SessionPartitionProfile::Discord;
    json!({
        "kind": "session_partition",
        "updated": false,
        "current_mode": current_mode,
        "supported_modes": supported_modes(profile),
        "quick_toggle": quick_toggle_usage(),
        "scope": "runtime",
    })
    .to_string()
}

pub(super) fn format_session_partition_updated(requested_mode: &str, current_mode: &str) -> String {
    [
        "Session partition updated.".to_string(),
        format!("requested_mode={requested_mode}"),
        format!("current_mode={current_mode}"),
        "scope=runtime (takes effect for new incoming messages)".to_string(),
    ]
    .join("\n")
}

pub(super) fn format_session_partition_updated_json(
    requested_mode: &str,
    current_mode: &str,
) -> String {
    json!({
        "kind": "session_partition",
        "updated": true,
        "requested_mode": requested_mode,
        "current_mode": current_mode,
        "scope": "runtime",
    })
    .to_string()
}

pub(super) fn format_session_partition_error_json(requested_mode: &str, error: &str) -> String {
    json!({
        "kind": "session_partition",
        "updated": false,
        "requested_mode": requested_mode,
        "error": error,
    })
    .to_string()
}

pub(super) fn format_session_partition_admin_required(sender: &str, current_mode: &str) -> String {
    [
        "## Session Partition Permission Denied".to_string(),
        "- `reason`: `admin_required`".to_string(),
        format!("- `sender`: `{sender}`"),
        format!("- `current_mode`: `{current_mode}`"),
        "- `hint`: Ask an identity allowed by `discord.control_command_allow_from` (or matching `discord.admin_command_rules` / `discord.admin_users`) to run `/session partition ...`."
            .to_string(),
    ]
    .join("\n")
}

pub(super) fn format_session_partition_admin_required_json(
    sender: &str,
    current_mode: &str,
) -> String {
    json!({
        "kind": "session_partition",
        "updated": false,
        "reason": "admin_required",
        "sender": sender,
        "current_mode": current_mode,
        "hint": "Ask an identity allowed by discord.control_command_allow_from (or discord.admin_command_rules / discord.admin_users) to run /session partition ...",
    })
    .to_string()
}

pub(super) fn format_control_command_admin_required(command: &str, sender: &str) -> String {
    shared_replies::format_control_command_admin_required(command, sender, PERMISSION_HINTS)
}

pub(super) fn format_slash_command_permission_required(command: &str, sender: &str) -> String {
    shared_replies::format_slash_command_permission_required(command, sender, PERMISSION_HINTS)
}

pub(super) fn format_slash_help() -> String {
    shared_replies::format_slash_help()
}

pub(super) fn format_slash_help_json() -> String {
    shared_replies::format_slash_help_json()
}

pub(super) fn format_memory_recall_metrics_lines(
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
) -> Vec<String> {
    vec![
        format!("- `planned_total={}`", metrics.planned_total),
        format!(
            "- `completed_total={}` / `injected={}` / `skipped={}`",
            metrics.completed_total, metrics.injected_total, metrics.skipped_total
        ),
        format!(
            "- `selected_total={}` / `injected_items_total={}`",
            metrics.selected_total, metrics.injected_items_total
        ),
        format!(
            "- `context_chars_injected_total={}`",
            metrics.context_chars_injected_total
        ),
        format!(
            "- `avg_pipeline_duration_ms={:.2}` / `total_pipeline_duration_ms={}`",
            metrics.avg_pipeline_duration_ms, metrics.pipeline_duration_ms_total
        ),
        format!(
            "- `injected_rate={:.3}` / `avg_selected_per_completed={:.3}` / `avg_injected_per_injected={:.3}`",
            metrics.injected_rate,
            metrics.avg_selected_per_completed,
            metrics.avg_injected_per_injected
        ),
        format!(
            "- `latency_buckets_ms`: `<=10:{}` `<=25:{}` `<=50:{}` `<=100:{}` `<=250:{}` `<=500:{}` `>500:{}`",
            metrics.latency_buckets.le_10ms,
            metrics.latency_buckets.le_25ms,
            metrics.latency_buckets.le_50ms,
            metrics.latency_buckets.le_100ms,
            metrics.latency_buckets.le_250ms,
            metrics.latency_buckets.le_500ms,
            metrics.latency_buckets.gt_500ms
        ),
    ]
}

pub(super) fn format_memory_recall_metrics_json(
    metrics: crate::agent::MemoryRecallMetricsSnapshot,
) -> serde_json::Value {
    json!({
        "captured_at_unix_ms": metrics.captured_at_unix_ms,
        "planned_total": metrics.planned_total,
        "injected_total": metrics.injected_total,
        "skipped_total": metrics.skipped_total,
        "completed_total": metrics.completed_total,
        "selected_total": metrics.selected_total,
        "injected_items_total": metrics.injected_items_total,
        "context_chars_injected_total": metrics.context_chars_injected_total,
        "pipeline_duration_ms_total": metrics.pipeline_duration_ms_total,
        "avg_pipeline_duration_ms": metrics.avg_pipeline_duration_ms,
        "avg_selected_per_completed": metrics.avg_selected_per_completed,
        "avg_injected_per_injected": metrics.avg_injected_per_injected,
        "injected_rate": metrics.injected_rate,
        "latency_buckets_ms": {
            "le_10ms": metrics.latency_buckets.le_10ms,
            "le_25ms": metrics.latency_buckets.le_25ms,
            "le_50ms": metrics.latency_buckets.le_50ms,
            "le_100ms": metrics.latency_buckets.le_100ms,
            "le_250ms": metrics.latency_buckets.le_250ms,
            "le_500ms": metrics.latency_buckets.le_500ms,
            "gt_500ms": metrics.latency_buckets.gt_500ms,
        },
    })
}

fn format_memory_runtime_status_lines(
    status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> Vec<String> {
    let backend_ready =
        status.enabled && status.active_backend.is_some() && status.startup_load_status == "loaded";
    vec![
        format!("- `memory_enabled={}`", format_yes_no(status.enabled)),
        format!(
            "- `configured_backend={}`",
            format_optional_string(status.configured_backend)
        ),
        format!(
            "- `active_backend={}`",
            format_optional_str(status.active_backend)
        ),
        format!(
            "- `strict_startup={}`",
            format_optional_bool(status.strict_startup)
        ),
        format!("- `startup_load_status={}`", status.startup_load_status),
        format!("- `backend_ready={}`", format_yes_no(backend_ready)),
        format!(
            "- `store_path={}`",
            format_optional_string(status.store_path)
        ),
        format!(
            "- `table_name={}`",
            format_optional_string(status.table_name)
        ),
        format!(
            "- `gate_promote_threshold={}`",
            format_optional_f32(status.gate_promote_threshold)
        ),
        format!(
            "- `gate_obsolete_threshold={}`",
            format_optional_f32(status.gate_obsolete_threshold)
        ),
        format!(
            "- `gate_promote_min_usage={}`",
            format_optional_u32(status.gate_promote_min_usage)
        ),
        format!(
            "- `gate_obsolete_min_usage={}`",
            format_optional_u32(status.gate_obsolete_min_usage)
        ),
        format!(
            "- `gate_promote_failure_rate_ceiling={}`",
            format_optional_f32(status.gate_promote_failure_rate_ceiling)
        ),
        format!(
            "- `gate_obsolete_failure_rate_floor={}`",
            format_optional_f32(status.gate_obsolete_failure_rate_floor)
        ),
        format!(
            "- `gate_promote_min_ttl_score={}`",
            format_optional_f32(status.gate_promote_min_ttl_score)
        ),
        format!(
            "- `gate_obsolete_max_ttl_score={}`",
            format_optional_f32(status.gate_obsolete_max_ttl_score)
        ),
        format!(
            "- `episodes_total={}`",
            format_optional_usize(status.episodes_total)
        ),
        format!(
            "- `q_values_total={}`",
            format_optional_usize(status.q_values_total)
        ),
    ]
}

fn format_memory_runtime_status_json(
    status: crate::agent::MemoryRuntimeStatusSnapshot,
) -> serde_json::Value {
    let backend_ready =
        status.enabled && status.active_backend.is_some() && status.startup_load_status == "loaded";
    json!({
        "memory_enabled": status.enabled,
        "configured_backend": status.configured_backend,
        "active_backend": status.active_backend,
        "strict_startup": status.strict_startup,
        "startup_load_status": status.startup_load_status,
        "backend_ready": backend_ready,
        "store_path": status.store_path,
        "table_name": status.table_name,
        "gate_promote_threshold": status.gate_promote_threshold,
        "gate_obsolete_threshold": status.gate_obsolete_threshold,
        "gate_promote_min_usage": status.gate_promote_min_usage,
        "gate_obsolete_min_usage": status.gate_obsolete_min_usage,
        "gate_promote_failure_rate_ceiling": status.gate_promote_failure_rate_ceiling,
        "gate_obsolete_failure_rate_floor": status.gate_obsolete_failure_rate_floor,
        "gate_promote_min_ttl_score": status.gate_promote_min_ttl_score,
        "gate_obsolete_max_ttl_score": status.gate_obsolete_max_ttl_score,
        "episodes_total": status.episodes_total,
        "q_values_total": status.q_values_total,
    })
}

fn format_optional_bool(value: Option<bool>) -> String {
    value.map_or_else(|| "-".to_string(), format_yes_no)
}

fn format_optional_str(value: Option<&str>) -> String {
    value.map_or_else(|| "-".to_string(), ToString::to_string)
}

fn format_optional_string(value: Option<String>) -> String {
    value.unwrap_or_else(|| "-".to_string())
}

fn format_yes_no(value: bool) -> String {
    if value {
        "yes".to_string()
    } else {
        "no".to_string()
    }
}

pub(super) fn format_context_budget_snapshot(
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

pub(super) fn format_context_budget_snapshot_json(
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

pub(super) fn format_context_budget_not_found_json() -> String {
    json!({
        "kind": "session_budget",
        "available": false,
        "status": "not_found",
        "hint": "Run at least one normal turn first (non-command message).",
    })
    .to_string()
}

pub(super) fn format_context_budget_class_json(
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

pub(super) fn format_command_error_json(command: &str, error: &str) -> String {
    shared_replies::format_command_error_json(command, error)
}

pub(super) fn format_context_budget_class_row(
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

pub(super) fn format_optional_usize(value: Option<usize>) -> String {
    shared_replies::format_optional_usize(value)
}

pub(super) fn format_optional_u32(value: Option<u32>) -> String {
    shared_replies::format_optional_u32(value)
}

pub(super) fn format_optional_f32(value: Option<f32>) -> String {
    shared_replies::format_optional_f32(value)
}
