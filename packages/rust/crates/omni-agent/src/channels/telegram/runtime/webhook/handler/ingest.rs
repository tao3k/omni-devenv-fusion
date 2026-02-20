use axum::http::StatusCode;

use super::super::state::TelegramWebhookState;

pub(super) async fn forward_update_to_agent(
    state: &TelegramWebhookState,
    update: &serde_json::Value,
) -> Result<(), (StatusCode, String)> {
    match state.channel.parse_update_message(update) {
        Some(msg) => {
            let message = update.get("message");
            let chat = message.and_then(|m| m.get("chat"));
            let chat_id = chat
                .and_then(|c| c.get("id"))
                .and_then(serde_json::Value::as_i64);
            let chat_title = chat
                .and_then(|c| c.get("title"))
                .and_then(serde_json::Value::as_str);
            let chat_type = chat
                .and_then(|c| c.get("type"))
                .and_then(serde_json::Value::as_str);
            let message_thread_id = message
                .and_then(|m| m.get("message_thread_id"))
                .and_then(serde_json::Value::as_i64);
            tracing::info!(
                session_key = %msg.session_key,
                chat_id = ?chat_id,
                chat_title = ?chat_title,
                chat_type = ?chat_type,
                message_thread_id = ?message_thread_id,
                content_preview = %msg.content.chars().take(50).collect::<String>(),
                "Parsed message, forwarding to agent"
            );
            if state.tx.send(msg).await.is_err() {
                tracing::error!("Channel inbound queue unavailable");
                return Err((
                    StatusCode::SERVICE_UNAVAILABLE,
                    "channel inbound queue unavailable".to_string(),
                ));
            }
        }
        None => {
            tracing::debug!(
                update_id = ?update.get("update_id"),
                "Update has no message (e.g. callback_query, channel_post); ignoring"
            );
        }
    }

    Ok(())
}
