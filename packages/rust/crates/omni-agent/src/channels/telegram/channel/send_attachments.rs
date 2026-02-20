use std::time::Duration;

use super::TelegramChannel;
use super::constants::{TELEGRAM_MAX_CAPTION_LENGTH, TELEGRAM_MEDIA_GROUP_MAX_ITEMS};
use super::media::{TelegramAttachment, TelegramAttachmentKind};
use super::send_types::{MediaGroupFilePart, PreparedCaption};

impl TelegramChannel {
    pub(super) async fn send_attachments(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        attachments: &[TelegramAttachment],
        first_caption: Option<&PreparedCaption>,
    ) -> anyhow::Result<()> {
        let mut first_caption = first_caption;
        let mut start = 0;
        while start < attachments.len() {
            let end = Self::next_media_batch_end(attachments, start);
            let batch = &attachments[start..end];

            if batch.len() > 1
                && self
                    .try_send_media_group(chat_id, thread_id, batch, first_caption)
                    .await?
            {
                // sendMediaGroup already delivered this batch in one request.
                first_caption = None;
            } else {
                for (index, attachment) in batch.iter().enumerate() {
                    let caption = if index == 0 { first_caption } else { None };
                    self.send_attachment(chat_id, thread_id, attachment, caption)
                        .await?;
                    if caption.is_some() {
                        first_caption = None;
                    }
                    if index < batch.len() - 1 {
                        tokio::time::sleep(Duration::from_millis(100)).await;
                    }
                }
            }

            start = end;
            if start < attachments.len() {
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        }
        Ok(())
    }

    async fn try_send_media_group(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        attachments: &[TelegramAttachment],
        first_caption: Option<&PreparedCaption>,
    ) -> anyhow::Result<bool> {
        let mut media = Vec::with_capacity(attachments.len());
        let mut file_parts = Vec::new();

        for (index, attachment) in attachments.iter().enumerate() {
            let Some(item_type) = Self::media_group_item_type(&attachment.kind) else {
                return Ok(false);
            };

            if let Some(url) = attachment.target.as_url() {
                let mut item = serde_json::json!({
                    "type": item_type,
                    "media": url,
                });
                if index == 0
                    && let Some(caption) = first_caption
                {
                    if let Some(markdown_caption) = caption.markdown_text() {
                        item["caption"] = serde_json::json!(markdown_caption);
                        item["parse_mode"] = serde_json::json!("MarkdownV2");
                    } else {
                        item["caption"] = serde_json::json!(caption.plain_text());
                    }
                }
                media.push(item);
                continue;
            }

            if let Some(path) = attachment.target.as_path() {
                let field_name = format!("file{index}");
                let file_name = path
                    .file_name()
                    .and_then(|name| name.to_str())
                    .unwrap_or(field_name.as_str())
                    .to_string();
                let file_bytes = tokio::fs::read(path).await.map_err(|error| {
                    anyhow::anyhow!(
                        "failed to read local attachment {}: {error}",
                        path.display()
                    )
                })?;

                let mut item = serde_json::json!({
                    "type": item_type,
                    "media": format!("attach://{field_name}"),
                });
                if index == 0
                    && let Some(caption) = first_caption
                {
                    if let Some(markdown_caption) = caption.markdown_text() {
                        item["caption"] = serde_json::json!(markdown_caption);
                        item["parse_mode"] = serde_json::json!("MarkdownV2");
                    } else {
                        item["caption"] = serde_json::json!(caption.plain_text());
                    }
                }
                media.push(item);
                file_parts.push(MediaGroupFilePart {
                    field_name,
                    file_name,
                    file_bytes,
                });
                continue;
            };

            return Ok(false);
        }

        let send_result = self
            .send_media_group_payload(chat_id, thread_id, &media, &file_parts)
            .await;
        let send_result = match send_result {
            Err(error)
                if first_caption
                    .and_then(PreparedCaption::markdown_text)
                    .is_some()
                    && error.should_retry_without_parse_mode() =>
            {
                tracing::warn!(
                    error = %error,
                    "Telegram sendMediaGroup caption MarkdownV2 failed; retrying with plain caption"
                );
                let media_plain_caption =
                    Self::media_group_plain_caption_payload(&media, first_caption);
                self.send_media_group_payload(chat_id, thread_id, &media_plain_caption, &file_parts)
                    .await
            }
            other => other,
        };

        match send_result {
            Ok(()) => Ok(true),
            Err(error) => {
                tracing::warn!(
                    error = %error,
                    "Telegram sendMediaGroup failed; falling back to sequential attachment sends"
                );
                Ok(false)
            }
        }
    }

    async fn send_attachment(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        attachment: &TelegramAttachment,
        caption: Option<&PreparedCaption>,
    ) -> anyhow::Result<()> {
        let (method, media_field) = Self::media_method_and_field(&attachment.kind);

        if let Some(url) = attachment.target.as_url() {
            return self
                .send_media_by_url(method, media_field, chat_id, thread_id, url, caption)
                .await
                .map_err(|error| anyhow::anyhow!("Telegram {method} failed: {error}"));
        }

        if let Some(path) = attachment.target.as_path() {
            return self
                .send_media_file_with_retry(method, media_field, chat_id, thread_id, path, caption)
                .await
                .map_err(|error| anyhow::anyhow!("Telegram {method} failed: {error}"));
        }

        anyhow::bail!("Telegram attachment target is invalid");
    }

    fn media_method_and_field(kind: &TelegramAttachmentKind) -> (&'static str, &'static str) {
        match kind {
            TelegramAttachmentKind::Image => ("sendPhoto", "photo"),
            TelegramAttachmentKind::Document => ("sendDocument", "document"),
            TelegramAttachmentKind::Video => ("sendVideo", "video"),
            TelegramAttachmentKind::Audio => ("sendAudio", "audio"),
            TelegramAttachmentKind::Voice => ("sendVoice", "voice"),
        }
    }

    fn media_group_item_type(kind: &TelegramAttachmentKind) -> Option<&'static str> {
        match kind {
            TelegramAttachmentKind::Image => Some("photo"),
            TelegramAttachmentKind::Document => Some("document"),
            TelegramAttachmentKind::Video => Some("video"),
            TelegramAttachmentKind::Audio => Some("audio"),
            TelegramAttachmentKind::Voice => None,
        }
    }

    fn supports_caption(kind: &TelegramAttachmentKind) -> bool {
        match kind {
            TelegramAttachmentKind::Image
            | TelegramAttachmentKind::Document
            | TelegramAttachmentKind::Video
            | TelegramAttachmentKind::Audio => true,
            TelegramAttachmentKind::Voice => false,
        }
    }

    pub(super) fn select_first_attachment_caption(
        text_without_markers: &str,
        attachments: &[TelegramAttachment],
    ) -> Option<String> {
        let first_attachment = attachments.first()?;
        if text_without_markers.is_empty() {
            return None;
        }
        if !Self::supports_caption(&first_attachment.kind) {
            return None;
        }
        if text_without_markers.chars().count() > TELEGRAM_MAX_CAPTION_LENGTH {
            return None;
        }

        Some(text_without_markers.to_string())
    }

    fn next_media_batch_end(attachments: &[TelegramAttachment], start: usize) -> usize {
        if start >= attachments.len() {
            return start;
        }

        if Self::media_group_item_type(&attachments[start].kind).is_none() {
            return start + 1;
        }

        let mut end = start + 1;
        while end < attachments.len()
            && (end - start) < TELEGRAM_MEDIA_GROUP_MAX_ITEMS
            && Self::media_group_item_type(&attachments[end].kind).is_some()
        {
            end += 1;
        }
        end
    }

    fn media_group_plain_caption_payload(
        media: &[serde_json::Value],
        first_caption: Option<&PreparedCaption>,
    ) -> Vec<serde_json::Value> {
        let mut payload = media.to_vec();
        let Some(caption) = first_caption else {
            return payload;
        };

        let Some(first_item) = payload.first_mut() else {
            return payload;
        };

        first_item["caption"] = serde_json::json!(caption.plain_text());
        if let Some(object) = first_item.as_object_mut() {
            object.remove("parse_mode");
        }
        payload
    }

    async fn send_media_group_payload(
        &self,
        chat_id: &str,
        thread_id: Option<&str>,
        media: &[serde_json::Value],
        file_parts: &[MediaGroupFilePart],
    ) -> Result<(), super::error::TelegramApiError> {
        if file_parts.is_empty() {
            let mut body = serde_json::json!({
                "chat_id": chat_id,
                "media": media,
            });
            if let Some(thread_id) = thread_id {
                body["message_thread_id"] = serde_json::json!(thread_id);
            }

            self.send_api_request_with_retry("sendMediaGroup", &body, "media_group")
                .await
        } else {
            self.send_media_group_files_with_retry(chat_id, thread_id, media, file_parts)
                .await
        }
    }
}
