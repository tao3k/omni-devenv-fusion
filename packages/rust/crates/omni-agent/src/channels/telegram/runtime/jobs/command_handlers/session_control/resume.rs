use std::sync::Arc;

use crate::agent::Agent;
use crate::channels::telegram::commands::{ResumeContextCommand, parse_resume_context_command};
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::observability::send_with_observability;
use super::super::super::replies::format_control_command_admin_required;
use super::{
    EVENT_TELEGRAM_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_RESUME_DROP_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_RESUME_REPLIED,
    EVENT_TELEGRAM_COMMAND_SESSION_RESUME_STATUS_REPLIED,
};

pub(in crate::channels::telegram::runtime::jobs) async fn try_handle_resume_context_command(
    msg: &ChannelMessage,
    channel: &Arc<dyn Channel>,
    agent: &Arc<Agent>,
    session_id: &str,
) -> bool {
    let Some(resume_command) = parse_resume_context_command(&msg.content) else {
        return false;
    };

    let resume_requires_admin = matches!(
        resume_command,
        ResumeContextCommand::Restore | ResumeContextCommand::Drop
    );
    if resume_requires_admin
        && !channel.is_authorized_for_control_command_for_recipient(
            &msg.sender,
            &msg.content,
            &msg.recipient,
        )
    {
        let command = match resume_command {
            ResumeContextCommand::Restore => "/resume",
            ResumeContextCommand::Drop => "/resume drop",
            ResumeContextCommand::Status => "/resume status",
        };
        let response = format_control_command_admin_required(command, &msg.sender);
        send_with_observability(
            channel,
            &response,
            &msg.recipient,
            "Failed to send resume admin-required response",
            Some(EVENT_TELEGRAM_COMMAND_CONTROL_ADMIN_REQUIRED_REPLIED),
            Some(&msg.session_key),
        )
        .await;
        return true;
    }

    let command_event = match resume_command {
        ResumeContextCommand::Restore => EVENT_TELEGRAM_COMMAND_SESSION_RESUME_REPLIED,
        ResumeContextCommand::Status => EVENT_TELEGRAM_COMMAND_SESSION_RESUME_STATUS_REPLIED,
        ResumeContextCommand::Drop => EVENT_TELEGRAM_COMMAND_SESSION_RESUME_DROP_REPLIED,
    };
    let response = match resume_command {
        ResumeContextCommand::Restore => match agent.resume_context_window(session_id).await {
            Ok(Some(stats)) => format!(
                "Session context restored.\nmessages_restored={} summary_segments_restored={}",
                stats.messages, stats.summary_segments
            ),
            Ok(None) => "No saved session context snapshot found. Use `/reset` or `/clear` first."
                .to_string(),
            Err(error) => format!("Failed to restore session context: {error}"),
        },
        ResumeContextCommand::Drop => match agent.drop_context_window_backup(session_id).await {
            Ok(true) => "Saved session context snapshot dropped.".to_string(),
            Ok(false) => "No saved session context snapshot found to drop.".to_string(),
            Err(error) => format!("Failed to drop saved session context snapshot: {error}"),
        },
        ResumeContextCommand::Status => match agent.peek_context_window_backup(session_id).await {
            Ok(Some(info)) => {
                let mut lines = vec![
                    "Saved session context snapshot:".to_string(),
                    format!("messages={}", info.messages),
                    format!("summary_segments={}", info.summary_segments),
                ];
                if let Some(saved_at_unix_ms) = info.saved_at_unix_ms {
                    lines.push(format!("saved_at_unix_ms={saved_at_unix_ms}"));
                }
                if let Some(saved_age_secs) = info.saved_age_secs {
                    lines.push(format!("saved_age_secs={saved_age_secs}"));
                }
                lines.push("Use `/resume` to restore.".to_string());
                lines.join("\n")
            }
            Ok(None) => "No saved session context snapshot found.".to_string(),
            Err(error) => format!("Failed to inspect session context snapshot: {error}"),
        },
    };
    send_with_observability(
        channel,
        &response,
        &msg.recipient,
        "Failed to send resume context response",
        Some(command_event),
        Some(&msg.session_key),
    )
    .await;
    true
}
