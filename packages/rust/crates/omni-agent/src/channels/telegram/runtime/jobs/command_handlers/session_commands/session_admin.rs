use std::sync::Arc;

use crate::channels::traits::{Channel, ChannelMessage, RecipientCommandAdminUsersMutation};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::{
    format_command_error_json, format_control_command_admin_required, format_session_admin_status,
    format_session_admin_status_json,
};
use super::{
    EVENT_TELEGRAM_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_ADMIN_JSON_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_ADMIN_REPLIED, update_session_admin_users,
};

use crate::channels::telegram::commands::{SessionAdminAction, parse_session_admin_command};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_session_admin_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
) -> bool {
    let Some(command) = parse_session_admin_command(&msg.content) else {
        return false;
    };

    if !channel.is_authorized_for_control_command_for_recipient(
        &msg.sender,
        &msg.content,
        &msg.recipient,
    ) {
        let response = format_control_command_admin_required("/session admin", &msg.sender);
        send_with_observability(
            channel,
            &response,
            &msg.recipient,
            "Failed to send session admin admin-required response",
            Some(EVENT_TELEGRAM_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED),
            Some(&msg.session_key),
        )
        .await;
        return true;
    }

    let command_event = if command.format.is_json() {
        EVENT_TELEGRAM_COMMAND_SESSION_ADMIN_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SESSION_ADMIN_REPLIED
    };

    let response = match command.action {
        SessionAdminAction::List => match channel.recipient_command_admin_users(&msg.recipient) {
            Ok(admin_users) if command.format.is_json() => {
                format_session_admin_status_json(&msg.recipient, admin_users.as_deref())
            }
            Ok(admin_users) => format_session_admin_status(&msg.recipient, admin_users.as_deref()),
            Err(error) if command.format.is_json() => {
                format_command_error_json("session_admin_status", &error.to_string())
            }
            Err(error) => format!("Failed to inspect session delegated admins: {error}"),
        },
        SessionAdminAction::Set(entries) => update_session_admin_users(
            channel,
            &msg.recipient,
            RecipientCommandAdminUsersMutation::Set(entries),
            "set",
            command.format.is_json(),
        ),
        SessionAdminAction::Add(entries) => update_session_admin_users(
            channel,
            &msg.recipient,
            RecipientCommandAdminUsersMutation::Add(entries),
            "add",
            command.format.is_json(),
        ),
        SessionAdminAction::Remove(entries) => update_session_admin_users(
            channel,
            &msg.recipient,
            RecipientCommandAdminUsersMutation::Remove(entries),
            "remove",
            command.format.is_json(),
        ),
        SessionAdminAction::Clear => update_session_admin_users(
            channel,
            &msg.recipient,
            RecipientCommandAdminUsersMutation::Clear,
            "clear",
            command.format.is_json(),
        ),
    };

    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send session admin response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
