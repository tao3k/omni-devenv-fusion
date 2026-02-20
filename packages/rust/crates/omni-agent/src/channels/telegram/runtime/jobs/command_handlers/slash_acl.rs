use std::sync::Arc;

use crate::channels::traits::{Channel, ChannelMessage};

use super::super::observability::send_with_observability;
use super::super::replies::format_slash_command_permission_required;

const EVENT_TELEGRAM_COMMAND_SLASH_PERMISSION_REQUIRED_REPLIED: &str =
    "telegram.command.slash_permission_required.replied";

pub(in super::super) async fn ensure_slash_command_authorized(
    channel: &Arc<dyn Channel>,
    msg: &ChannelMessage,
    command_scope: &str,
    command_label: &str,
) -> bool {
    if channel.is_authorized_for_slash_command_for_recipient(
        &msg.sender,
        command_scope,
        &msg.recipient,
    ) {
        return true;
    }
    let response = format_slash_command_permission_required(command_label, &msg.sender);
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send slash permission-required response",
        Some(EVENT_TELEGRAM_COMMAND_SLASH_PERMISSION_REQUIRED_REPLIED),
        Some(&msg.session_key),
    )
    .await;
    false
}
