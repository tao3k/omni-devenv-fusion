use crate::agent::Agent;
use crate::channels::managed_commands::{
    detect_managed_control_command, detect_managed_slash_command,
};
use crate::channels::managed_runtime::turn::{
    ForegroundTurnOutcome, build_session_id, run_foreground_turn,
};
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::JobManager;
use std::sync::Arc;

use super::managed::handle_inbound_managed_command;

const LOG_PREVIEW_LEN: usize = 80;

pub(super) async fn process_discord_message(
    agent: Arc<Agent>,
    channel: Arc<dyn Channel>,
    msg: ChannelMessage,
    job_manager: &Arc<JobManager>,
    turn_timeout_secs: u64,
) {
    if let Some(control_command) = detect_managed_control_command(&msg.content) {
        tracing::debug!(
            command = control_command.canonical_command(),
            "discord managed control command detected"
        );
    }
    if let Some(slash_command) = detect_managed_slash_command(&msg.content) {
        tracing::debug!(
            command = slash_command.canonical_command(),
            scope = slash_command.scope(),
            "discord managed slash command detected"
        );
    }

    if handle_inbound_managed_command(&agent, &channel, &msg, job_manager).await {
        return;
    }

    let session_id = build_session_id(&msg.channel, &msg.session_key);
    tracing::info!(
        r#"discord ← User: "{preview}""#,
        preview = log_preview(&msg.content)
    );

    if let Err(error) = channel.start_typing(&msg.recipient).await {
        tracing::debug!("discord: failed to start typing: {error}");
    }

    let result = run_foreground_turn(
        agent.as_ref(),
        &session_id,
        &msg.content,
        turn_timeout_secs,
        format!("Request timed out after {turn_timeout_secs}s."),
    )
    .await;

    if let Err(error) = channel.stop_typing(&msg.recipient).await {
        tracing::debug!("discord: failed to stop typing: {error}");
    }

    let reply = match result {
        ForegroundTurnOutcome::Succeeded(output) => output,
        ForegroundTurnOutcome::Failed {
            reply,
            error_chain,
            error_kind,
        } => {
            tracing::error!(
                event = "discord.foreground.turn.failed",
                session_key = %msg.session_key,
                channel = %msg.channel,
                recipient = %msg.recipient,
                sender = %msg.sender,
                error_kind,
                error = %error_chain,
                "discord foreground turn failed"
            );
            reply
        }
        ForegroundTurnOutcome::TimedOut { reply } => {
            tracing::warn!(
                event = "discord.foreground.turn.timeout",
                session_key = %msg.session_key,
                channel = %msg.channel,
                recipient = %msg.recipient,
                sender = %msg.sender,
                timeout_secs = turn_timeout_secs,
                "discord foreground turn timed out"
            );
            reply
        }
    };

    match channel.send(&reply, &msg.recipient).await {
        Ok(()) => tracing::info!(
            r#"discord → Bot: "{preview}""#,
            preview = log_preview(&reply)
        ),
        Err(error) => tracing::warn!("discord: failed to send reply: {error}"),
    }
}

fn log_preview(s: &str) -> String {
    let one_line: String = s.chars().map(|c| if c == '\n' { ' ' } else { c }).collect();
    if one_line.chars().count() > LOG_PREVIEW_LEN {
        format!(
            "{}...",
            one_line
                .chars()
                .take(LOG_PREVIEW_LEN)
                .collect::<String>()
                .trim_end()
        )
    } else {
        one_line
    }
}
