use std::sync::Arc;

use crate::channels::traits::{Channel, ChannelMessage};

pub(super) async fn send_response(
    channel: &Arc<dyn Channel>,
    recipient: &str,
    response: String,
    msg: &ChannelMessage,
    event: &'static str,
) {
    match channel.send(&response, recipient).await {
        Ok(()) => tracing::info!(
            event,
            session_key = %msg.session_key,
            recipient = %msg.recipient,
            "discord command reply sent"
        ),
        Err(error) => tracing::warn!(
            event,
            error = %error,
            session_key = %msg.session_key,
            recipient = %msg.recipient,
            "discord failed to send command reply"
        ),
    }
}

pub(super) async fn send_completion(
    channel: &Arc<dyn Channel>,
    recipient: &str,
    response: String,
    event: &'static str,
) {
    match channel.send(&response, recipient).await {
        Ok(()) => tracing::info!(
            event,
            recipient = %recipient,
            "discord command completion reply sent"
        ),
        Err(error) => tracing::warn!(
            event,
            error = %error,
            recipient = %recipient,
            "discord failed to send command completion reply"
        ),
    }
}
