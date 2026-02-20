use super::super::TelegramChannel;
use super::super::identity::parse_recipient_target;

impl TelegramChannel {
    pub(in crate::channels::telegram::channel) async fn send_chat_action(
        &self,
        recipient: &str,
        action: &str,
    ) -> anyhow::Result<()> {
        let (chat_id, thread_id) = parse_recipient_target(recipient);
        let mut body = serde_json::json!({
            "chat_id": chat_id,
            "action": action,
        });
        if let Some(thread_id) = thread_id {
            body["message_thread_id"] = serde_json::json!(thread_id);
        }
        self.wait_for_send_rate_limit_gate("sendChatAction", action)
            .await;
        if let Ok(response) = self
            .client
            .post(self.api_url("sendChatAction"))
            .json(&body)
            .send()
            .await
            && let Err(error) = Self::validate_telegram_response(response).await
        {
            let delay = error.retry_delay(0);
            self.update_send_rate_limit_gate_from_error(&error, delay, "sendChatAction", action)
                .await;
            tracing::debug!(
                action,
                delay_ms = delay.as_millis(),
                error = %error,
                "Telegram sendChatAction failed"
            );
        }
        Ok(())
    }
}
