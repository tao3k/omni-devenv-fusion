use serde_json::json;

use crate::agent::SessionRecallFeedbackDirection;
use crate::jobs::{JobHealthState, JobMetricsSnapshot, JobState, JobStatusSnapshot};

#[derive(Debug, Clone, Copy)]
pub(crate) struct PermissionHints<'a> {
    pub(crate) control_command_hint: &'a str,
    pub(crate) slash_command_hint: &'a str,
}

macro_rules! permission_lines {
    ($title:literal, $reason:literal, $command:expr, $sender:expr, $hint:expr) => {{
        [
            $title.to_string(),
            format!("- `reason`: `{}`", $reason),
            format!("- `command`: `{}`", $command),
            format!("- `sender`: `{}`", $sender),
            format!("- `hint`: {}", $hint),
        ]
        .join("\n")
    }};
}

pub(crate) fn format_control_command_admin_required(
    command: &str,
    sender: &str,
    hints: PermissionHints<'_>,
) -> String {
    permission_lines!(
        "## Control Command Permission Denied",
        "admin_required",
        command,
        sender,
        hints.control_command_hint
    )
}

pub(crate) fn format_slash_command_permission_required(
    command: &str,
    sender: &str,
    hints: PermissionHints<'_>,
) -> String {
    permission_lines!(
        "## Slash Command Permission Denied",
        "slash_permission_required",
        command,
        sender,
        hints.slash_command_hint
    )
}

pub(crate) fn format_slash_help() -> String {
    [
        "## Bot Slash Help".to_string(),
        "Use slash commands in chat to inspect session state, run background jobs, and recover context.".to_string(),
        "".to_string(),
        "### General".to_string(),
        "- `/help` or `/slash help`: show this command guide.".to_string(),
        "- `/help json`: machine-readable command catalog.".to_string(),
        "".to_string(),
        "### Session".to_string(),
        "- `/session [json]`: current session window/snapshot status.".to_string(),
        "- `/session budget [json]`: context-budget diagnostics.".to_string(),
        "- `/session memory [json]`: memory recall trigger/result/runtime status.".to_string(),
        "- `/session feedback up|down [json]`: adjust recall feedback bias.".to_string(),
        "- `/session admin [list|set|add|remove|clear] [json]`: delegated admins for current group/topic (admin).".to_string(),
        "- `/session partition [mode|on|off] [json]`: session key mode (admin).".to_string(),
        "- `/feedback up|down [json]`: short alias of `/session feedback ...`.".to_string(),
        "- `/reset` or `/clear`: clear active session context (admin).".to_string(),
        "- `/resume`, `/resume status`, `/resume drop`: restore/check/drop saved snapshot.".to_string(),
        "".to_string(),
        "### Background".to_string(),
        "- `/bg <prompt>`: submit prompt as background job.".to_string(),
        "- `/job <id> [json]`: inspect one background job.".to_string(),
        "- `/jobs [json]`: background queue health summary.".to_string(),
        "".to_string(),
        "### Notes".to_string(),
        "- Some commands can be blocked by slash ACL or admin policy.".to_string(),
        "- Add `json` when you need script-friendly output.".to_string(),
    ]
    .join("\n")
}

pub(crate) fn format_slash_help_json() -> String {
    json!({
        "kind": "slash_help",
        "commands": {
            "general": [
                {"usage": "/help", "description": "Show slash command guide"},
                {"usage": "/help json", "description": "Machine-readable guide payload"},
                {"usage": "/slash help", "description": "Alias of /help"},
            ],
            "session": [
                {"usage": "/session [json]", "description": "Session window/snapshot status"},
                {"usage": "/session budget [json]", "description": "Context-budget diagnostics"},
                {"usage": "/session memory [json]", "description": "Memory recall trigger/result/runtime status"},
                {"usage": "/session feedback up|down [json]", "description": "Adjust recall feedback bias"},
                {"usage": "/session admin [list|set|add|remove|clear] [json]", "description": "Delegated admins for current group/topic (admin)"},
                {"usage": "/session partition [mode|on|off] [json]", "description": "Session partition mode (admin)"},
                {"usage": "/feedback up|down [json]", "description": "Alias of /session feedback"},
                {"usage": "/reset | /clear", "description": "Reset current session context (admin)"},
                {"usage": "/resume | /resume status | /resume drop", "description": "Restore/check/drop saved context snapshot"},
            ],
            "background": [
                {"usage": "/bg <prompt>", "description": "Submit background job"},
                {"usage": "/job <id> [json]", "description": "Inspect one background job"},
                {"usage": "/jobs [json]", "description": "Background queue health summary"},
            ],
        },
        "notes": [
            "Some commands can be blocked by slash ACL or admin policy.",
            "Add json for script-friendly responses."
        ],
    })
    .to_string()
}

pub(crate) fn format_job_status(snapshot: &JobStatusSnapshot) -> String {
    let mut lines = vec![
        "============================================================".to_string(),
        "job-status dashboard".to_string(),
        "============================================================".to_string(),
        "Overview:".to_string(),
        format!("  job_id={}", snapshot.job_id),
        format!("  state={}", format_job_state(snapshot.state)),
        "------------------------------------------------------------".to_string(),
        "Identity:".to_string(),
        format!("  session_id={}", snapshot.session_id),
        format!("  prompt_preview={}", snapshot.prompt_preview),
        "------------------------------------------------------------".to_string(),
        "Timing:".to_string(),
        format!("  submitted_age_secs={}", snapshot.submitted_age_secs),
        format!(
            "  running_age_secs={}",
            format_optional_u64(snapshot.running_age_secs)
        ),
        format!(
            "  finished_age_secs={}",
            format_optional_u64(snapshot.finished_age_secs)
        ),
        "------------------------------------------------------------".to_string(),
        "Result:".to_string(),
    ];
    if let Some(ref output_preview) = snapshot.output_preview {
        lines.push(format!("  output_preview={output_preview}"));
    } else {
        lines.push("  output_preview=-".to_string());
    }
    if let Some(ref error) = snapshot.error {
        lines.push(format!("  error={error}"));
    } else {
        lines.push("  error=-".to_string());
    }
    lines.extend([
        "------------------------------------------------------------".to_string(),
        "Hints:".to_string(),
        "  jobs_dashboard=/jobs".to_string(),
        "============================================================".to_string(),
    ]);
    lines.join("\n")
}

pub(crate) fn format_job_metrics(metrics: &JobMetricsSnapshot) -> String {
    let mut lines = vec![
        "============================================================".to_string(),
        "jobs-health dashboard".to_string(),
        "============================================================".to_string(),
        "Overview:".to_string(),
        format!("  total={}", metrics.total_jobs),
        format!("  queued={}", metrics.queued),
        format!("  running={}", metrics.running),
        format!("  succeeded={}", metrics.succeeded),
        format!("  failed={}", metrics.failed),
        format!("  timed_out={}", metrics.timed_out),
        "------------------------------------------------------------".to_string(),
        "Timing:".to_string(),
        format!(
            "  oldest_queued_age_secs={}",
            format_optional_u64(metrics.oldest_queued_age_secs)
        ),
        format!(
            "  longest_running_age_secs={}",
            format_optional_u64(metrics.longest_running_age_secs)
        ),
        "------------------------------------------------------------".to_string(),
        "Health:".to_string(),
        format!("  state={}", format_job_health(metrics.health_state)),
    ];
    lines.push(format!("  hint={}", format_job_health_hint(metrics)));
    lines.push("============================================================".to_string());
    lines.join("\n")
}

pub(crate) fn format_job_not_found(job_id: &str) -> String {
    [
        "============================================================".to_string(),
        "job-status dashboard".to_string(),
        "============================================================".to_string(),
        "Overview:".to_string(),
        format!("  job_id={job_id}"),
        "  status=not_found".to_string(),
        "------------------------------------------------------------".to_string(),
        "Hints:".to_string(),
        "  jobs_dashboard=/jobs".to_string(),
        "  submit_background=/bg <prompt>".to_string(),
        "============================================================".to_string(),
    ]
    .join("\n")
}

pub(crate) fn format_optional_u64(value: Option<u64>) -> String {
    value.map_or_else(|| "-".to_string(), |age| age.to_string())
}

pub(crate) fn format_optional_usize(value: Option<usize>) -> String {
    value.map_or_else(|| "-".to_string(), |v| v.to_string())
}

pub(crate) fn format_optional_u32(value: Option<u32>) -> String {
    value.map_or_else(|| "-".to_string(), |v| v.to_string())
}

pub(crate) fn format_optional_f32(value: Option<f32>) -> String {
    value.map_or_else(|| "-".to_string(), |v| format!("{v:.3}"))
}

pub(crate) fn format_job_status_json(snapshot: &JobStatusSnapshot) -> String {
    json!({
        "kind": "job_status",
        "found": true,
        "job_id": snapshot.job_id.clone(),
        "state": format_job_state(snapshot.state),
        "session_id": snapshot.session_id.clone(),
        "prompt_preview": snapshot.prompt_preview.clone(),
        "submitted_age_secs": snapshot.submitted_age_secs,
        "running_age_secs": snapshot.running_age_secs,
        "finished_age_secs": snapshot.finished_age_secs,
        "output_preview": snapshot.output_preview.clone(),
        "error": snapshot.error.clone(),
    })
    .to_string()
}

pub(crate) fn format_job_metrics_json(metrics: &JobMetricsSnapshot) -> String {
    json!({
        "kind": "jobs_health",
        "total": metrics.total_jobs,
        "queued": metrics.queued,
        "running": metrics.running,
        "succeeded": metrics.succeeded,
        "failed": metrics.failed,
        "timed_out": metrics.timed_out,
        "oldest_queued_age_secs": metrics.oldest_queued_age_secs,
        "longest_running_age_secs": metrics.longest_running_age_secs,
        "health": format_job_health(metrics.health_state),
        "hint": format_job_health_hint(metrics),
    })
    .to_string()
}

pub(crate) fn format_job_not_found_json(job_id: &str) -> String {
    json!({
        "kind": "job_status",
        "found": false,
        "job_id": job_id,
        "status": "not_found",
    })
    .to_string()
}

pub(crate) fn format_job_health_hint(metrics: &JobMetricsSnapshot) -> &'static str {
    if metrics.queued > 0 {
        "queued backlog present; use /job <id> for drill-down"
    } else if metrics.running > 0 {
        "jobs are in progress; use /job <id> for drill-down"
    } else {
        "no active jobs"
    }
}

pub(crate) fn format_job_state(state: JobState) -> &'static str {
    match state {
        JobState::Queued => "queued",
        JobState::Running => "running",
        JobState::Succeeded => "succeeded",
        JobState::Failed => "failed",
        JobState::TimedOut => "timed_out",
    }
}

pub(crate) fn format_job_health(state: JobHealthState) -> &'static str {
    match state {
        JobHealthState::Healthy => "healthy",
        JobHealthState::QueueStalled => "queue_stalled",
        JobHealthState::RunningStalled => "running_stalled",
    }
}

pub(crate) fn format_session_feedback(
    direction: SessionRecallFeedbackDirection,
    previous_bias: f32,
    updated_bias: f32,
) -> String {
    let direction_label = match direction {
        SessionRecallFeedbackDirection::Up => "up",
        SessionRecallFeedbackDirection::Down => "down",
    };
    format!(
        "Session recall feedback updated.\ndirection={direction_label}\nprevious_bias={previous_bias:.3}\nupdated_bias={updated_bias:.3}"
    )
}

pub(crate) fn format_session_feedback_json(
    direction: SessionRecallFeedbackDirection,
    previous_bias: f32,
    updated_bias: f32,
) -> String {
    let direction_label = match direction {
        SessionRecallFeedbackDirection::Up => "up",
        SessionRecallFeedbackDirection::Down => "down",
    };
    json!({
        "kind": "session_feedback",
        "applied": true,
        "direction": direction_label,
        "previous_bias": previous_bias,
        "updated_bias": updated_bias,
    })
    .to_string()
}

pub(crate) fn format_session_feedback_unavailable_json() -> String {
    json!({
        "kind": "session_feedback",
        "applied": false,
        "reason": "memory_disabled",
        "message": "Session recall feedback is unavailable because memory is disabled.",
    })
    .to_string()
}

pub(crate) fn format_command_error_json(command: &str, error: &str) -> String {
    json!({
        "kind": "command_error",
        "command": command,
        "status": "error",
        "error": error,
    })
    .to_string()
}
