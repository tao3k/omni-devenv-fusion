use serde_json::json;

use crate::channels::managed_runtime::session_partition::{
    SessionPartitionProfile, quick_toggle_usage, set_mode_usage, supported_modes,
    supported_modes_csv,
};

pub(in super::super) fn format_session_partition_status(current_mode: &str) -> String {
    let profile = SessionPartitionProfile::Telegram;
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

pub(in super::super) fn format_session_partition_status_json(current_mode: &str) -> String {
    let profile = SessionPartitionProfile::Telegram;
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

pub(in super::super) fn format_session_partition_updated(
    requested_mode: &str,
    current_mode: &str,
) -> String {
    [
        "Session partition updated.".to_string(),
        format!("requested_mode={requested_mode}"),
        format!("current_mode={current_mode}"),
        "scope=runtime (takes effect for new incoming messages)".to_string(),
    ]
    .join("\n")
}

pub(in super::super) fn format_session_partition_updated_json(
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

pub(in super::super) fn format_session_partition_error_json(
    requested_mode: &str,
    error: &str,
) -> String {
    json!({
        "kind": "session_partition",
        "updated": false,
        "requested_mode": requested_mode,
        "error": error,
    })
    .to_string()
}

pub(in super::super) fn format_session_partition_admin_required(
    sender: &str,
    current_mode: &str,
) -> String {
    [
        "## Session Partition Permission Denied".to_string(),
        "- `reason`: `admin_required`".to_string(),
        format!("- `sender`: `{sender}`"),
        format!("- `current_mode`: `{current_mode}`"),
        "- `hint`: Ask an identity allowed by `telegram.control_command_allow_from` (or `telegram.admin_command_rules` / `telegram.admin_users`) to run `/session partition ...`."
            .to_string(),
    ]
    .join("\n")
}

pub(in super::super) fn format_session_partition_admin_required_json(
    sender: &str,
    current_mode: &str,
) -> String {
    json!({
        "kind": "session_partition",
        "updated": false,
        "reason": "admin_required",
        "sender": sender,
        "current_mode": current_mode,
        "hint": "Ask an identity allowed by telegram.control_command_allow_from (or telegram.admin_command_rules / telegram.admin_users) to run /session partition ...",
    })
    .to_string()
}
