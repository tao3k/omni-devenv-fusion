use std::path::Path;

use reqwest::multipart::{Form, Part};

use super::super::TelegramChannel;
use super::super::constants::TELEGRAM_SEND_MAX_RETRIES;
use super::super::error::TelegramApiError;
use super::super::send_types::{MediaGroupFilePart, PreparedCaption};

impl TelegramChannel {
    pub(in crate::channels::telegram::channel) async fn send_media_by_url(
        &self,
        method: &str,
        media_field: &str,
        chat_id: &str,
        thread_id: Option<&str>,
        url: &str,
        caption: Option<&PreparedCaption>,
    ) -> Result<(), TelegramApiError> {
        let mut body = serde_json::json!({
            "chat_id": chat_id,
        });
        body[media_field] = serde_json::json!(url);
        if let Some(caption) = caption {
            if let Some(markdown_caption) = caption.markdown_text() {
                body["caption"] = serde_json::json!(markdown_caption);
                body["parse_mode"] = serde_json::json!("MarkdownV2");
            } else {
                body["caption"] = serde_json::json!(caption.plain_text());
            }
        }

        if let Some(thread_id) = thread_id {
            body["message_thread_id"] = serde_json::json!(thread_id);
        }

        let send_result = self
            .send_api_request_with_retry(method, &body, media_field)
            .await;
        match send_result {
            Err(error)
                if caption.and_then(PreparedCaption::markdown_text).is_some()
                    && error.should_retry_without_parse_mode() =>
            {
                tracing::warn!(
                    error = %error,
                    method,
                    "Telegram media caption MarkdownV2 failed; retrying with plain caption"
                );
                let mut plain_body = body;
                if let Some(caption) = caption {
                    plain_body["caption"] = serde_json::json!(caption.plain_text());
                }
                if let Some(object) = plain_body.as_object_mut() {
                    object.remove("parse_mode");
                }
                self.send_api_request_with_retry(method, &plain_body, media_field)
                    .await
            }
            other => other,
        }
    }

    pub(in crate::channels::telegram::channel) async fn send_media_file_with_retry(
        &self,
        method: &str,
        media_field: &str,
        chat_id: &str,
        thread_id: Option<&str>,
        path: &Path,
        caption: Option<&PreparedCaption>,
    ) -> Result<(), TelegramApiError> {
        let file_name = path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or(media_field)
            .to_string();
        let file_bytes = tokio::fs::read(path)
            .await
            .map_err(|error| TelegramApiError {
                status: Some(reqwest::StatusCode::BAD_REQUEST),
                error_code: None,
                retry_after_secs: None,
                body: format!(
                    "failed to read local attachment {}: {error}",
                    path.display()
                ),
            })?;

        let markdown_caption = caption.and_then(PreparedCaption::markdown_text);
        let first_caption_text =
            markdown_caption.or_else(|| caption.map(PreparedCaption::plain_text));
        let first_parse_mode = markdown_caption.map(|_| "MarkdownV2");

        let send_result = self
            .send_media_file_with_retry_mode(
                method,
                media_field,
                chat_id,
                thread_id,
                file_name.as_str(),
                file_bytes.as_slice(),
                first_caption_text,
                first_parse_mode,
            )
            .await;
        match send_result {
            Err(error) if markdown_caption.is_some() && error.should_retry_without_parse_mode() => {
                tracing::warn!(
                    error = %error,
                    method,
                    media_field,
                    "Telegram media upload caption MarkdownV2 failed; retrying with plain caption"
                );
                self.send_media_file_with_retry_mode(
                    method,
                    media_field,
                    chat_id,
                    thread_id,
                    file_name.as_str(),
                    file_bytes.as_slice(),
                    caption.map(PreparedCaption::plain_text),
                    None,
                )
                .await
            }
            other => other,
        }
    }

    async fn send_media_file_with_retry_mode(
        &self,
        method: &str,
        media_field: &str,
        chat_id: &str,
        thread_id: Option<&str>,
        file_name: &str,
        file_bytes: &[u8],
        caption_text: Option<&str>,
        caption_parse_mode: Option<&str>,
    ) -> Result<(), TelegramApiError> {
        for attempt in 0..=TELEGRAM_SEND_MAX_RETRIES {
            self.wait_for_send_rate_limit_gate(method, media_field)
                .await;
            match self
                .send_media_file_once(
                    method,
                    media_field,
                    chat_id,
                    thread_id,
                    file_name,
                    file_bytes,
                    caption_text,
                    caption_parse_mode,
                )
                .await
            {
                Ok(()) => return Ok(()),
                Err(error) if attempt < TELEGRAM_SEND_MAX_RETRIES && error.should_retry_send() => {
                    let delay = error.retry_delay(attempt);
                    self.update_send_rate_limit_gate_from_error(&error, delay, method, media_field)
                        .await;
                    tracing::warn!(
                        attempt,
                        max_retries = TELEGRAM_SEND_MAX_RETRIES,
                        delay_ms = delay.as_millis(),
                        method,
                        media_field,
                        error = %error,
                        "Telegram media upload transient failure; retrying"
                    );
                    tokio::time::sleep(delay).await;
                }
                Err(error) => return Err(error),
            }
        }

        unreachable!("send_media_file_with_retry_mode should return before exhausting attempts")
    }

    async fn send_media_file_once(
        &self,
        method: &str,
        media_field: &str,
        chat_id: &str,
        thread_id: Option<&str>,
        file_name: &str,
        file_bytes: &[u8],
        caption_text: Option<&str>,
        caption_parse_mode: Option<&str>,
    ) -> Result<(), TelegramApiError> {
        let part = Part::bytes(file_bytes.to_vec()).file_name(file_name.to_string());
        let mut form = Form::new()
            .text("chat_id", chat_id.to_string())
            .part(media_field.to_string(), part);
        if let Some(caption_text) = caption_text {
            form = form.text("caption", caption_text.to_string());
        }
        if let Some(caption_parse_mode) = caption_parse_mode {
            form = form.text("parse_mode", caption_parse_mode.to_string());
        }
        if let Some(thread_id) = thread_id {
            form = form.text("message_thread_id", thread_id.to_string());
        }

        let response = self
            .client
            .post(self.api_url(method))
            .multipart(form)
            .send()
            .await
            .map_err(TelegramApiError::from_reqwest)?;
        Self::validate_telegram_response(response).await
    }

    pub(in crate::channels::telegram::channel) async fn send_media_group_files_with_retry(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        media: &[serde_json::Value],
        file_parts: &[MediaGroupFilePart],
    ) -> Result<(), TelegramApiError> {
        for attempt in 0..=TELEGRAM_SEND_MAX_RETRIES {
            self.wait_for_send_rate_limit_gate("sendMediaGroup", "multipart")
                .await;
            match self
                .send_media_group_files_once(chat_id, thread_id, media, file_parts)
                .await
            {
                Ok(()) => return Ok(()),
                Err(error) if attempt < TELEGRAM_SEND_MAX_RETRIES && error.should_retry_send() => {
                    let delay = error.retry_delay(attempt);
                    self.update_send_rate_limit_gate_from_error(
                        &error,
                        delay,
                        "sendMediaGroup",
                        "multipart",
                    )
                    .await;
                    tracing::warn!(
                        attempt,
                        max_retries = TELEGRAM_SEND_MAX_RETRIES,
                        delay_ms = delay.as_millis(),
                        error = %error,
                        "Telegram sendMediaGroup multipart transient failure; retrying"
                    );
                    tokio::time::sleep(delay).await;
                }
                Err(error) => return Err(error),
            }
        }

        unreachable!("send_media_group_files_with_retry should return before exhausting attempts")
    }

    async fn send_media_group_files_once(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        media: &[serde_json::Value],
        file_parts: &[MediaGroupFilePart],
    ) -> Result<(), TelegramApiError> {
        let mut form = Form::new().text("chat_id", chat_id.to_string()).text(
            "media",
            serde_json::to_string(media).map_err(|error| TelegramApiError {
                status: Some(reqwest::StatusCode::BAD_REQUEST),
                error_code: None,
                retry_after_secs: None,
                body: format!("failed to encode sendMediaGroup payload: {error}"),
            })?,
        );
        if let Some(thread_id) = thread_id {
            form = form.text("message_thread_id", thread_id.to_string());
        }

        for part in file_parts {
            let file_part =
                Part::bytes(part.file_bytes.clone()).file_name(part.file_name.to_string());
            form = form.part(part.field_name.to_string(), file_part);
        }

        let response = self
            .client
            .post(self.api_url("sendMediaGroup"))
            .multipart(form)
            .send()
            .await
            .map_err(TelegramApiError::from_reqwest)?;
        Self::validate_telegram_response(response).await
    }
}
