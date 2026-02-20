use std::time::Duration;

use super::TelegramChannel;
use super::chunking::{decorate_chunk_for_telegram, split_message_for_telegram};
use super::constants::TELEGRAM_MAX_MESSAGE_LENGTH;
use super::identity::parse_recipient_target;
use super::markdown::{markdown_to_telegram_html, markdown_to_telegram_markdown_v2};
use super::media::{parse_attachment_markers, parse_path_only_attachment};
use super::send_types::PreparedCaption;

impl TelegramChannel {
    pub(super) async fn send_text(&self, message: &str, recipient: &str) -> anyhow::Result<()> {
        let (chat_id, thread_id) = parse_recipient_target(recipient);

        let (text_without_markers, attachments, has_invalid_attachment_marker) =
            parse_attachment_markers(message);
        if !attachments.is_empty() {
            let first_attachment_caption =
                Self::select_first_attachment_caption(&text_without_markers, &attachments)
                    .map(|caption| PreparedCaption::from_plain(caption.as_str()));

            if first_attachment_caption.is_none() && !text_without_markers.is_empty() {
                self.send_text_chunks(&text_without_markers, chat_id, thread_id, false)
                    .await?;
            }
            self.send_attachments(
                chat_id,
                thread_id,
                &attachments,
                first_attachment_caption.as_ref(),
            )
            .await?;
            return Ok(());
        }

        if has_invalid_attachment_marker {
            return self
                .send_text_chunks(&text_without_markers, chat_id, thread_id, true)
                .await;
        }

        if let Some(attachment) = parse_path_only_attachment(message) {
            self.send_attachments(chat_id, thread_id, &[attachment], None)
                .await?;
            return Ok(());
        }

        self.send_text_chunks(message, chat_id, thread_id, false)
            .await
    }

    async fn send_text_chunks(
        &self,
        message: &str,
        chat_id: &str,
        thread_id: Option<&str>,
        force_plain: bool,
    ) -> anyhow::Result<()> {
        let chunks = split_message_for_telegram(message);
        let prepared_chunks: Vec<(String, String, usize, String, usize)> = chunks
            .iter()
            .enumerate()
            .map(|(index, chunk)| {
                let plain_text = decorate_chunk_for_telegram(chunk, index, chunks.len());
                let markdown_v2_text = markdown_to_telegram_markdown_v2(&plain_text);
                let html_text = markdown_to_telegram_html(&plain_text);
                let markdown_chars = markdown_v2_text.chars().count();
                let html_chars = html_text.chars().count();
                (
                    plain_text,
                    markdown_v2_text,
                    markdown_chars,
                    html_text,
                    html_chars,
                )
            })
            .collect();

        let markdown_overflow = prepared_chunks
            .iter()
            .any(|(_, _, markdown_chars, _, _)| *markdown_chars > TELEGRAM_MAX_MESSAGE_LENGTH);
        if markdown_overflow {
            tracing::warn!(
                chunks = prepared_chunks.len(),
                "Telegram MarkdownV2 payload exceeds limit for at least one chunk; sending all chunks as plain text"
            );
        }

        for (index, (plain_text, markdown_v2_text, markdown_chars, html_text, html_chars)) in
            prepared_chunks.into_iter().enumerate()
        {
            if force_plain || markdown_overflow || markdown_chars > TELEGRAM_MAX_MESSAGE_LENGTH {
                self.send_message_with_mode(chat_id, thread_id, &plain_text, None)
                    .await
                    .map_err(|plain_error| {
                        anyhow::anyhow!(
                            "Telegram sendMessage failed (markdown skipped due size; plain fallback: {})",
                            plain_error
                        )
                    })?;
            } else {
                let send_result = self
                    .send_message_with_mode(
                        chat_id,
                        thread_id,
                        &markdown_v2_text,
                        Some("MarkdownV2"),
                    )
                    .await;

                match send_result {
                    Ok(()) => {}
                    Err(markdown_error) if markdown_error.should_retry_without_parse_mode() => {
                        tracing::warn!(
                            error = %markdown_error,
                            "Telegram MarkdownV2 send failed with parse-mode error; retrying with HTML parse mode"
                        );
                        if html_chars <= TELEGRAM_MAX_MESSAGE_LENGTH {
                            let html_result = self
                                .send_message_with_mode(
                                    chat_id,
                                    thread_id,
                                    &html_text,
                                    Some("HTML"),
                                )
                                .await;
                            match html_result {
                                Ok(()) => {}
                                Err(html_error) if html_error.should_retry_without_parse_mode() => {
                                    tracing::warn!(
                                        error = %html_error,
                                        "Telegram HTML send failed with parse-mode error; retrying without parse_mode"
                                    );
                                    self.send_message_with_mode(chat_id, thread_id, &plain_text, None)
                                        .await
                                        .map_err(|plain_error| {
                                            anyhow::anyhow!(
                                                "Telegram sendMessage failed (markdown request failed: {}; html fallback failed: {}; plain fallback: {})",
                                                markdown_error,
                                                html_error,
                                                plain_error
                                            )
                                        })?;
                                }
                                Err(error) => {
                                    anyhow::bail!(
                                        "Telegram sendMessage failed (markdown request failed: {}; html fallback failed: {})",
                                        markdown_error,
                                        error
                                    );
                                }
                            }
                        } else {
                            tracing::warn!(
                                html_chars,
                                "Telegram HTML fallback chunk exceeds message limit; sending plain text"
                            );
                            self.send_message_with_mode(chat_id, thread_id, &plain_text, None)
                                .await
                                .map_err(|plain_error| {
                                    anyhow::anyhow!(
                                        "Telegram sendMessage failed (markdown request failed: {}; plain fallback: {})",
                                        markdown_error,
                                        plain_error
                                    )
                                })?;
                        }
                    }
                    Err(error) => {
                        anyhow::bail!("Telegram sendMessage failed: {error}");
                    }
                }
            }

            debug_assert!(
                plain_text.chars().count() <= TELEGRAM_MAX_MESSAGE_LENGTH,
                "chunk {} exceeds limit: {} > {}",
                index,
                plain_text.chars().count(),
                TELEGRAM_MAX_MESSAGE_LENGTH
            );

            if index < chunks.len() - 1 {
                tokio::time::sleep(Duration::from_millis(100)).await;
            }
        }
        Ok(())
    }
}
