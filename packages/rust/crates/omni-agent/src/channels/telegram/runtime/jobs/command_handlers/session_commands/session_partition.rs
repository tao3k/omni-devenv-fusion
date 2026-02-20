use std::sync::Arc;

use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::{
    format_session_partition_admin_required, format_session_partition_admin_required_json,
    format_session_partition_error_json, format_session_partition_status,
    format_session_partition_status_json, format_session_partition_updated,
    format_session_partition_updated_json,
};
use super::{
    EVENT_TELEGRAM_COMMAND_SESSION_PARTITION_JSON_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_PARTITION_REPLIED,
};

use crate::channels::telegram::commands::{SessionPartitionMode, parse_session_partition_command};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_session_partition_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
) -> bool {
    let Some(command) = parse_session_partition_command(&msg.content) else {
        return false;
    };

    let command_event = if command.format.is_json() {
        EVENT_TELEGRAM_COMMAND_SESSION_PARTITION_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SESSION_PARTITION_REPLIED
    };
    let current_mode = channel
        .session_partition_mode()
        .unwrap_or_else(|| "unknown".to_string());
    let sender_is_admin = channel.is_authorized_for_control_command_for_recipient(
        &msg.sender,
        &msg.content,
        &msg.recipient,
    );

    if !sender_is_admin {
        let response = if command.format.is_json() {
            format_session_partition_admin_required_json(&msg.sender, &current_mode)
        } else {
            format_session_partition_admin_required(&msg.sender, &current_mode)
        };
        send_with_observability(
            channel,
            &response,
            &msg.recipient,
            "Failed to send session partition admin-required response",
            Some(command_event),
            Some(&msg.session_key),
        )
        .await;
        return true;
    }

    let response = match command.mode {
        None if command.format.is_json() => format_session_partition_status_json(&current_mode),
        None => format_session_partition_status(&current_mode),
        Some(mode) => {
            let requested = mode.as_str();
            match channel.set_session_partition_mode(requested) {
                Ok(()) => {
                    let updated_mode = channel
                        .session_partition_mode()
                        .unwrap_or_else(|| requested.to_string());
                    if command.format.is_json() {
                        format_session_partition_updated_json(requested, &updated_mode)
                    } else {
                        format_session_partition_updated(requested, &updated_mode)
                    }
                }
                Err(error) if command.format.is_json() => {
                    format_session_partition_error_json(requested, &error.to_string())
                }
                Err(error) => format!(
                    "Failed to update session partition mode.\nrequested_mode={requested}\nerror={error}"
                ),
            }
        }
    };

    tracing::info!(
        session_key = %msg.session_key,
        recipient = %msg.recipient,
        previous_partition_mode = %current_mode,
        requested_partition_mode = command.mode.map(SessionPartitionMode::as_str).unwrap_or(""),
        "telegram session partition command processed"
    );
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send session partition response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
