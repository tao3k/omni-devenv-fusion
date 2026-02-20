use std::time::Duration;

use reqwest::StatusCode;
use tokio::sync::mpsc;

use crate::channels::traits::ChannelMessage;

use super::TelegramChannel;
use super::constants::{
    TELEGRAM_POLL_CONFLICT_RETRY_SECS, TELEGRAM_POLL_DEFAULT_RATE_LIMIT_RETRY_SECS,
    TELEGRAM_POLL_MAX_RATE_LIMIT_RETRY_SECS, TELEGRAM_POLL_RETRY_SECS,
};
use super::error::telegram_api_error_retry_after_secs;

impl TelegramChannel {
    pub(super) async fn listen_updates(
        &self,
        tx: mpsc::Sender<ChannelMessage>,
    ) -> anyhow::Result<()> {
        let mut offset: i64 = 0;
        tracing::info!("Telegram channel listening for messages...");
        loop {
            let url = self.api_url("getUpdates");
            let body = serde_json::json!({
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message"]
            });
            let resp = match self.client.post(&url).json(&body).send().await {
                Ok(r) => r,
                Err(e) => {
                    tracing::warn!("Telegram poll error: {e}");
                    tokio::time::sleep(Duration::from_secs(TELEGRAM_POLL_RETRY_SECS)).await;
                    continue;
                }
            };
            let http_status = resp.status();
            if !http_status.is_success() {
                let body_text = resp.text().await.unwrap_or_default();
                let maybe_data = serde_json::from_str::<serde_json::Value>(&body_text).ok();
                let description = maybe_data
                    .as_ref()
                    .and_then(|d| d.get("description"))
                    .and_then(serde_json::Value::as_str)
                    .filter(|s| !s.is_empty())
                    .unwrap_or(body_text.as_str());

                match http_status {
                    StatusCode::UNAUTHORIZED | StatusCode::FORBIDDEN => {
                        anyhow::bail!(
                            "Telegram getUpdates HTTP error (status={}): {}",
                            http_status,
                            description
                        );
                    }
                    StatusCode::CONFLICT => {
                        tracing::warn!(
                            "Telegram polling conflict (HTTP 409): {description}. \
Ensure only one process is using this bot token."
                        );
                        tokio::time::sleep(Duration::from_secs(TELEGRAM_POLL_CONFLICT_RETRY_SECS))
                            .await;
                    }
                    StatusCode::TOO_MANY_REQUESTS => {
                        let retry_after_secs = maybe_data
                            .as_ref()
                            .and_then(telegram_api_error_retry_after_secs)
                            .unwrap_or(TELEGRAM_POLL_DEFAULT_RATE_LIMIT_RETRY_SECS)
                            .clamp(1, TELEGRAM_POLL_MAX_RATE_LIMIT_RETRY_SECS);
                        tracing::warn!(
                            retry_after_secs,
                            "Telegram getUpdates HTTP 429 rate limited: {description}"
                        );
                        tokio::time::sleep(Duration::from_secs(retry_after_secs)).await;
                    }
                    _ => {
                        tracing::warn!(
                            status = %http_status,
                            "Telegram getUpdates HTTP error: {description}"
                        );
                        tokio::time::sleep(Duration::from_secs(TELEGRAM_POLL_RETRY_SECS)).await;
                    }
                }

                continue;
            }

            let data: serde_json::Value = match resp.json().await {
                Ok(d) => d,
                Err(e) => {
                    tracing::warn!("Telegram parse error: {e}");
                    tokio::time::sleep(Duration::from_secs(TELEGRAM_POLL_RETRY_SECS)).await;
                    continue;
                }
            };

            let ok = data
                .get("ok")
                .and_then(serde_json::Value::as_bool)
                .unwrap_or(true);
            if !ok {
                let error_code = data
                    .get("error_code")
                    .and_then(serde_json::Value::as_i64)
                    .unwrap_or_default();
                let description = data
                    .get("description")
                    .and_then(serde_json::Value::as_str)
                    .unwrap_or("unknown Telegram API error");

                match error_code {
                    401 | 403 => {
                        anyhow::bail!(
                            "Telegram getUpdates API error (code={}): {}",
                            error_code,
                            description
                        );
                    }
                    409 => {
                        tracing::warn!(
                            "Telegram polling conflict (409): {description}. \
Ensure only one process is using this bot token."
                        );
                        tokio::time::sleep(Duration::from_secs(TELEGRAM_POLL_CONFLICT_RETRY_SECS))
                            .await;
                    }
                    429 => {
                        let retry_after_secs = telegram_api_error_retry_after_secs(&data)
                            .unwrap_or(TELEGRAM_POLL_DEFAULT_RATE_LIMIT_RETRY_SECS)
                            .clamp(1, TELEGRAM_POLL_MAX_RATE_LIMIT_RETRY_SECS);
                        tracing::warn!(
                            retry_after_secs,
                            "Telegram getUpdates rate limited (429): {description}"
                        );
                        tokio::time::sleep(Duration::from_secs(retry_after_secs)).await;
                    }
                    _ => {
                        tracing::warn!(
                            "Telegram getUpdates API error (code={}): {description}",
                            error_code
                        );
                        tokio::time::sleep(Duration::from_secs(TELEGRAM_POLL_RETRY_SECS)).await;
                    }
                }

                continue;
            }

            if let Some(results) = data.get("result").and_then(serde_json::Value::as_array) {
                for update in results {
                    if let Some(uid) = update.get("update_id").and_then(serde_json::Value::as_i64) {
                        offset = uid + 1;
                    }
                    let Some(msg) = self.parse_update_message(update) else {
                        continue;
                    };
                    let _ = self.send_chat_action(&msg.recipient, "typing").await;
                    if tx.send(msg).await.is_err() {
                        return Ok(());
                    }
                }
            }
        }
    }

    pub(super) async fn health_probe(&self) -> bool {
        match tokio::time::timeout(
            Duration::from_secs(5),
            self.client.get(self.api_url("getMe")).send(),
        )
        .await
        {
            Ok(Ok(resp)) => resp.status().is_success(),
            _ => false,
        }
    }
}
