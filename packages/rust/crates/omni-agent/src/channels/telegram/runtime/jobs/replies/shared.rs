use crate::agent::{SessionContextMode, SessionRecallFeedbackDirection};
use crate::channels::managed_runtime::replies as shared_replies;
use crate::jobs::{JobMetricsSnapshot, JobStatusSnapshot};

const PERMISSION_HINTS: shared_replies::PermissionHints<'static> =
    shared_replies::PermissionHints {
        control_command_hint: "Ask an identity allowed by `telegram.control_command_allow_from` (or matching `telegram.admin_command_rules` / `telegram.admin_users`) to run this command.",
        slash_command_hint: "Ask an admin to grant this command via telegram slash command allowlist settings.",
    };

pub(in super::super) fn format_job_status(snapshot: &JobStatusSnapshot) -> String {
    shared_replies::format_job_status(snapshot)
}

pub(in super::super) fn format_job_metrics(metrics: &JobMetricsSnapshot) -> String {
    shared_replies::format_job_metrics(metrics)
}

pub(in super::super) fn format_job_not_found(job_id: &str) -> String {
    shared_replies::format_job_not_found(job_id)
}

pub(in super::super) fn format_optional_usize(value: Option<usize>) -> String {
    shared_replies::format_optional_usize(value)
}

pub(in super::super) fn format_optional_u32(value: Option<u32>) -> String {
    shared_replies::format_optional_u32(value)
}

pub(in super::super) fn format_optional_f32(value: Option<f32>) -> String {
    shared_replies::format_optional_f32(value)
}

pub(in super::super) fn format_job_status_json(snapshot: &JobStatusSnapshot) -> String {
    shared_replies::format_job_status_json(snapshot)
}

pub(in super::super) fn format_job_metrics_json(metrics: &JobMetricsSnapshot) -> String {
    shared_replies::format_job_metrics_json(metrics)
}

pub(in super::super) fn format_job_not_found_json(job_id: &str) -> String {
    shared_replies::format_job_not_found_json(job_id)
}

pub(in super::super) fn format_context_mode(mode: SessionContextMode) -> &'static str {
    match mode {
        SessionContextMode::Bounded => "bounded",
        SessionContextMode::Unbounded => "unbounded",
    }
}

pub(in super::super) fn format_session_feedback(
    direction: SessionRecallFeedbackDirection,
    previous_bias: f32,
    updated_bias: f32,
) -> String {
    shared_replies::format_session_feedback(direction, previous_bias, updated_bias)
}

pub(in super::super) fn format_session_feedback_json(
    direction: SessionRecallFeedbackDirection,
    previous_bias: f32,
    updated_bias: f32,
) -> String {
    shared_replies::format_session_feedback_json(direction, previous_bias, updated_bias)
}

pub(in super::super) fn format_session_feedback_unavailable_json() -> String {
    shared_replies::format_session_feedback_unavailable_json()
}

pub(in super::super) fn format_control_command_admin_required(
    command: &str,
    sender: &str,
) -> String {
    shared_replies::format_control_command_admin_required(command, sender, PERMISSION_HINTS)
}

pub(in super::super) fn format_slash_command_permission_required(
    command: &str,
    sender: &str,
) -> String {
    shared_replies::format_slash_command_permission_required(command, sender, PERMISSION_HINTS)
}

pub(in super::super) fn format_slash_help() -> String {
    shared_replies::format_slash_help()
}

pub(in super::super) fn format_slash_help_json() -> String {
    shared_replies::format_slash_help_json()
}

pub(in super::super) fn format_command_error_json(command: &str, error: &str) -> String {
    shared_replies::format_command_error_json(command, error)
}

pub(in super::super) fn format_optional_bool(value: Option<bool>) -> String {
    value.map_or_else(|| "-".to_string(), format_yes_no)
}

pub(in super::super) fn format_optional_str(value: Option<&str>) -> String {
    value.map_or_else(|| "-".to_string(), ToString::to_string)
}

pub(in super::super) fn format_optional_string(value: Option<String>) -> String {
    value.unwrap_or_else(|| "-".to_string())
}

pub(in super::super) fn format_yes_no(value: bool) -> String {
    if value {
        "yes".to_string()
    } else {
        "no".to_string()
    }
}
