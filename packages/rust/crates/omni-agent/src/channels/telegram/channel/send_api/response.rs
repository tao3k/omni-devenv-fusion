use super::super::TelegramChannel;
use super::super::error::{
    TelegramApiError, telegram_api_error_code, telegram_api_error_description,
    telegram_api_error_retry_after_secs,
};

impl TelegramChannel {
    pub(in crate::channels::telegram::channel) async fn validate_telegram_response(
        response: reqwest::Response,
    ) -> Result<(), TelegramApiError> {
        let status = response.status();
        let body_text = response.text().await.unwrap_or_default();
        let parsed = serde_json::from_str::<serde_json::Value>(&body_text).ok();

        if !status.is_success() {
            return Err(TelegramApiError {
                status: Some(status),
                error_code: parsed.as_ref().and_then(telegram_api_error_code),
                retry_after_secs: parsed
                    .as_ref()
                    .and_then(telegram_api_error_retry_after_secs),
                body: parsed
                    .as_ref()
                    .map(|data| {
                        telegram_api_error_description(data, body_text.as_str()).to_string()
                    })
                    .unwrap_or(body_text),
            });
        }

        let Some(data) = parsed else {
            return Err(TelegramApiError {
                status: None,
                error_code: None,
                retry_after_secs: None,
                body: format!("failed to parse Telegram success response: {body_text}"),
            });
        };

        let ok = data
            .get("ok")
            .and_then(serde_json::Value::as_bool)
            .unwrap_or(true);
        if !ok {
            return Err(TelegramApiError {
                status: Some(status),
                error_code: telegram_api_error_code(&data),
                retry_after_secs: telegram_api_error_retry_after_secs(&data),
                body: telegram_api_error_description(&data, body_text.as_str()).to_string(),
            });
        }

        Ok(())
    }
}
