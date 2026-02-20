use std::sync::Arc;

use crate::channels::telegram::commands::parse_help_command;
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::{format_slash_help, format_slash_help_json};
use super::{
    EVENT_TELEGRAM_COMMAND_SLASH_HELP_JSON_REPLIED, EVENT_TELEGRAM_COMMAND_SLASH_HELP_REPLIED,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_help_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
) -> bool {
    let Some(format) = parse_help_command(&msg.content) else {
        return false;
    };
    let command_event = if format.is_json() {
        EVENT_TELEGRAM_COMMAND_SLASH_HELP_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SLASH_HELP_REPLIED
    };
    let response = if format.is_json() {
        format_slash_help_json()
    } else {
        format_slash_help()
    };
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send slash help response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
