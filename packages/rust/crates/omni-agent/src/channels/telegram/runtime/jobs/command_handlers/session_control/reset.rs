use std::sync::Arc;

use crate::agent::Agent;
use crate::channels::telegram::commands::is_reset_context_command;
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::format_control_command_admin_required;
use super::{
    EVENT_TELEGRAM_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_RESET_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_RESET_SNAPSHOT_STATE,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_reset_context_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    if !is_reset_context_command(&msg.content) {
        return false;
    }

    if !channel.is_authorized_for_control_command_for_recipient(
        &msg.sender,
        &msg.content,
        &msg.recipient,
    ) {
        let response = format_control_command_admin_required(msg.content.trim(), &msg.sender);
        send_with_observability(
            channel,
            &response,
            &msg.recipient,
            "Failed to send reset admin-required response",
            Some(EVENT_TELEGRAM_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED),
            Some(&msg.session_key),
        )
        .await;
        return true;
    }

    let (response, snapshot_state) = match agent.reset_context_window(session_id).await {
        Ok(stats) => {
            if stats.messages > 0 || stats.summary_segments > 0 {
                (
                    format!(
                        "Session context reset.\nmessages_cleared={} summary_segments_cleared={}\nUse `/resume` to restore this session context.\nLong-term memory and knowledge stores are unchanged.",
                        stats.messages, stats.summary_segments
                    ),
                    Some("created"),
                )
            } else {
                let (snapshot_note, snapshot_state) = match agent
                    .peek_context_window_backup(session_id)
                    .await
                {
                    Ok(Some(_)) => (
                        "Existing saved snapshot remains available. Use `/resume status` to inspect it.",
                        "retained",
                    ),
                    Ok(None) => (
                        "No saved session context snapshot is currently available.",
                        "none",
                    ),
                    Err(_) => (
                        "Snapshot availability could not be confirmed. Use `/resume status` to verify.",
                        "unknown",
                    ),
                };
                (
                    format!(
                        "Session context reset.\nmessages_cleared=0 summary_segments_cleared=0\nNo active context snapshot was created because this session is already empty.\n{snapshot_note}\nLong-term memory and knowledge stores are unchanged."
                    ),
                    Some(snapshot_state),
                )
            }
        }
        Err(error) => (
            format!("Failed to reset session context: {error}"),
            Some("error"),
        ),
    };
    if let Some(snapshot_state) = snapshot_state {
        tracing::info!(
            event = EVENT_TELEGRAM_COMMAND_SESSION_RESET_SNAPSHOT_STATE,
            session_key = %msg.session_key,
            recipient = %msg.recipient,
            snapshot_state,
            "telegram command reset snapshot state"
        );
    }
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send reset context response",
        Some(EVENT_TELEGRAM_COMMAND_SESSION_RESET_REPLIED),
        Some(&msg.session_key),
    )
    .await;
    true
}
