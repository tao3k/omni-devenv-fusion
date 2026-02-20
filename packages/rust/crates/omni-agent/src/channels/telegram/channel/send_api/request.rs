use super::super::TelegramChannel;
use super::super::constants::TELEGRAM_SEND_MAX_RETRIES;
use super::super::error::TelegramApiError;

impl TelegramChannel {
    pub(in crate::channels::telegram::channel) async fn send_message_with_mode(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        text: &str,
        parse_mode: Option<&str>,
    ) -> Result<(), TelegramApiError> {
        let mut body = serde_json::json!({
            "chat_id": chat_id,
            "text": text,
        });
        if let Some(mode) = parse_mode {
            body["parse_mode"] = serde_json::json!(mode);
        }
        if let Some(thread_id) = thread_id {
            body["message_thread_id"] = serde_json::json!(thread_id);
        }

        self.send_api_request_with_retry("sendMessage", &body, parse_mode.unwrap_or("plain"))
            .await
    }

    pub(in crate::channels::telegram::channel) async fn send_api_request_with_retry(
        &self,
        method: &str,
        body: &serde_json::Value,
        request_kind: &str,
    ) -> Result<(), TelegramApiError> {
        for attempt in 0..=TELEGRAM_SEND_MAX_RETRIES {
            self.wait_for_send_rate_limit_gate(method, request_kind)
                .await;
            match self.send_api_request_once(method, body).await {
                Ok(()) => return Ok(()),
                Err(error) if attempt < TELEGRAM_SEND_MAX_RETRIES && error.should_retry_send() => {
                    let delay = error.retry_delay(attempt);
                    self.update_send_rate_limit_gate_from_error(
                        &error,
                        delay,
                        method,
                        request_kind,
                    )
                    .await;
                    tracing::warn!(
                        attempt,
                        max_retries = TELEGRAM_SEND_MAX_RETRIES,
                        delay_ms = delay.as_millis(),
                        method,
                        request_kind,
                        error = %error,
                        "Telegram API transient failure; retrying"
                    );
                    tokio::time::sleep(delay).await;
                }
                Err(error) => return Err(error),
            }
        }

        unreachable!("send_api_request_with_retry should return before exhausting attempts")
    }

    async fn send_api_request_once(
        &self,
        method: &str,
        body: &serde_json::Value,
    ) -> Result<(), TelegramApiError> {
        let response = self
            .client
            .post(self.api_url(method))
            .json(body)
            .send()
            .await
            .map_err(TelegramApiError::from_reqwest)?;
        Self::validate_telegram_response(response).await
    }
}
