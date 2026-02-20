use std::sync::Arc;

use crate::channels::managed_commands::SLASH_SCOPE_JOB_STATUS as TELEGRAM_SLASH_SCOPE_JOB_STATUS;
use crate::channels::telegram::commands::parse_job_status_command;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::JobManager;

use super::super::super::observability::send_with_observability;
use super::super::super::replies::{
    format_job_not_found, format_job_not_found_json, format_job_status, format_job_status_json,
};
use super::super::slash_acl::ensure_slash_command_authorized;
use super::{
    EVENT_TELEGRAM_COMMAND_JOB_STATUS_JSON_REPLIED, EVENT_TELEGRAM_COMMAND_JOB_STATUS_REPLIED,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_job_status_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    job_manager: &Arc<JobManager>,
) -> bool {
    let Some(command) = parse_job_status_command(&msg.content) else {
        return false;
    };

    if !ensure_slash_command_authorized(channel, msg, TELEGRAM_SLASH_SCOPE_JOB_STATUS, "/job").await
    {
        return true;
    }

    let command_event = if command.format.is_json() {
        EVENT_TELEGRAM_COMMAND_JOB_STATUS_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_JOB_STATUS_REPLIED
    };
    let status_msg = match job_manager.get_status(&command.job_id).await {
        Some(snapshot) if command.format.is_json() => format_job_status_json(&snapshot),
        Some(snapshot) => format_job_status(&snapshot),
        None if command.format.is_json() => format_job_not_found_json(&command.job_id),
        None => format_job_not_found(&command.job_id),
    };
    send_with_observability(
        channel,
        &status_msg,
        &msg.recipient,
        "Failed to send job status",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
