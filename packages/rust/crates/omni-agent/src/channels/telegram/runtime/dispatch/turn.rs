use crate::agent::Agent;
use crate::channels::managed_runtime::turn::{
    ForegroundTurnOutcome, build_session_id, run_foreground_turn,
};
use crate::channels::traits::{Channel, ChannelMessage};
use std::sync::Arc;

use super::preview::log_preview;

pub(super) async fn process_foreground_message(
    agent: Arc<Agent>,
    channel: Arc<dyn Channel>,
    msg: ChannelMessage,
    turn_timeout_secs: u64,
) {
    let session_id = build_session_id(&msg.channel, &msg.session_key);
    tracing::info!(
        r#"← User: "{preview}""#,
        preview = log_preview(&msg.content)
    );

    if let Err(error) = channel.start_typing(&msg.recipient).await {
        tracing::debug!("Failed to start typing: {error}");
    }

    let result = run_foreground_turn(
        agent.as_ref(),
        &session_id,
        &msg.content,
        turn_timeout_secs,
        format!(
            "Request timed out after {}s. Use `/bg <prompt>` for long-running tasks.",
            turn_timeout_secs
        ),
    )
    .await;

    if let Err(error) = channel.stop_typing(&msg.recipient).await {
        tracing::debug!("Failed to stop typing: {error}");
    }

    let reply = match result {
        ForegroundTurnOutcome::Succeeded(output) => output,
        ForegroundTurnOutcome::Failed {
            reply,
            error_chain,
            error_kind,
        } => {
            tracing::error!(
                event = "telegram.foreground.turn.failed",
                session_key = %msg.session_key,
                channel = %msg.channel,
                recipient = %msg.recipient,
                sender = %msg.sender,
                error_kind,
                error = %error_chain,
                "foreground turn failed"
            );
            reply
        }
        ForegroundTurnOutcome::TimedOut { reply } => {
            tracing::warn!(
                event = "telegram.foreground.turn.timeout",
                session_key = %msg.session_key,
                channel = %msg.channel,
                recipient = %msg.recipient,
                sender = %msg.sender,
                timeout_secs = turn_timeout_secs,
                "foreground turn timed out"
            );
            reply
        }
    };

    match channel.send(&reply, &msg.recipient).await {
        Ok(()) => tracing::info!(r#"→ Bot: "{preview}""#, preview = log_preview(&reply)),
        Err(error) => tracing::error!("Failed to send foreground reply: {error}"),
    }
}
