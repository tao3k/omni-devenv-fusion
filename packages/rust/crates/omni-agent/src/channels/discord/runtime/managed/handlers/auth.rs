use std::sync::Arc;

use crate::channels::traits::{Channel, ChannelMessage};

use super::super::replies::{
    format_control_command_admin_required, format_slash_command_permission_required,
};
use super::events::{
    EVENT_DISCORD_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED,
    EVENT_DISCORD_COMMAND_SLASH_PERMISSION_REQUIRED_REPLIED,
};
use super::send::send_response;

pub(super) async fn ensure_control_command_authorized(
    channel: &Arc<dyn Channel>,
    msg: &ChannelMessage,
    command: &str,
) -> bool {
    if channel.is_authorized_for_control_command(&msg.sender, &msg.content) {
        return true;
    }
    let response = format_control_command_admin_required(command, &msg.sender);
    send_response(
        channel,
        &msg.recipient,
        response,
        msg,
        EVENT_DISCORD_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED,
    )
    .await;
    false
}

pub(super) async fn ensure_slash_command_authorized(
    channel: &Arc<dyn Channel>,
    msg: &ChannelMessage,
    scope: &str,
    command_label: &str,
) -> bool {
    if channel.is_authorized_for_slash_command(&msg.sender, scope) {
        return true;
    }
    let response = format_slash_command_permission_required(command_label, &msg.sender);
    send_response(
        channel,
        &msg.recipient,
        response,
        msg,
        EVENT_DISCORD_COMMAND_SLASH_PERMISSION_REQUIRED_REPLIED,
    )
    .await;
    false
}
