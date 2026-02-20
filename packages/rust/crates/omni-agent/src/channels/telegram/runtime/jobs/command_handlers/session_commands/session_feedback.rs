use std::sync::Arc;

use crate::agent::{Agent, SessionRecallFeedbackDirection};
use crate::channels::managed_commands::SLASH_SCOPE_SESSION_FEEDBACK as TELEGRAM_SLASH_SCOPE_SESSION_FEEDBACK;
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::{
    format_session_feedback, format_session_feedback_json, format_session_feedback_unavailable_json,
};
use super::super::slash_acl::ensure_slash_command_authorized;
use super::{
    EVENT_TELEGRAM_COMMAND_SESSION_FEEDBACK_JSON_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_FEEDBACK_REPLIED,
};

use crate::channels::telegram::commands::{
    SessionFeedbackDirection, parse_session_feedback_command,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_session_feedback_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    let Some(command) = parse_session_feedback_command(&msg.content) else {
        return false;
    };

    if !ensure_slash_command_authorized(
        channel,
        msg,
        TELEGRAM_SLASH_SCOPE_SESSION_FEEDBACK,
        "/session feedback",
    )
    .await
    {
        return true;
    }

    let command_event = if command.format.is_json() {
        EVENT_TELEGRAM_COMMAND_SESSION_FEEDBACK_JSON_REPLIED
    } else {
        EVENT_TELEGRAM_COMMAND_SESSION_FEEDBACK_REPLIED
    };
    let direction = match command.direction {
        SessionFeedbackDirection::Up => SessionRecallFeedbackDirection::Up,
        SessionFeedbackDirection::Down => SessionRecallFeedbackDirection::Down,
    };
    let response = match agent
        .apply_session_recall_feedback(session_id, direction)
        .await
    {
        Some(update) if command.format.is_json() => {
            format_session_feedback_json(direction, update.previous_bias, update.updated_bias)
        }
        Some(update) => {
            format_session_feedback(direction, update.previous_bias, update.updated_bias)
        }
        None if command.format.is_json() => format_session_feedback_unavailable_json(),
        None => "Session recall feedback is unavailable because memory is disabled.".to_string(),
    };
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send session feedback response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
