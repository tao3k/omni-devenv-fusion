use anyhow::{Context, Result};
use serde_json::json;

use super::channel::DiscordChannel;
use super::constants::DISCORD_MAX_MESSAGE_LENGTH;

impl DiscordChannel {
    pub(super) async fn send_text(&self, message: &str, recipient: &str) -> Result<()> {
        let channel_id = recipient.trim();
        if channel_id.is_empty() {
            anyhow::bail!("discord recipient channel id cannot be empty");
        }

        let chunks = split_message_for_discord(message, DISCORD_MAX_MESSAGE_LENGTH);
        if chunks.is_empty() {
            anyhow::bail!("discord message content cannot be empty");
        }

        for chunk in chunks {
            self.send_text_chunk(&chunk, channel_id).await?;
        }
        Ok(())
    }

    pub(super) async fn start_typing_indicator(&self, recipient: &str) -> Result<()> {
        let channel_id = recipient.trim();
        if channel_id.is_empty() {
            anyhow::bail!("discord recipient channel id cannot be empty");
        }

        let url = self.api_url(&format!("channels/{channel_id}/typing"));
        let response = self
            .client
            .post(url)
            .header("Authorization", format!("Bot {}", self.bot_token))
            .send()
            .await
            .context("discord typing request failed")?;
        if response.status().is_success() {
            return Ok(());
        }

        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        let preview = body.chars().take(256).collect::<String>();
        anyhow::bail!("discord typing failed: status={status} body={preview}");
    }

    async fn send_text_chunk(&self, content: &str, channel_id: &str) -> Result<()> {
        let url = self.api_url(&format!("channels/{channel_id}/messages"));
        let payload = json!({ "content": content });
        let response = self
            .client
            .post(url)
            .header("Authorization", format!("Bot {}", self.bot_token))
            .json(&payload)
            .send()
            .await
            .context("discord send request failed")?;
        if response.status().is_success() {
            return Ok(());
        }

        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        let preview = body.chars().take(256).collect::<String>();
        anyhow::bail!("discord send failed: status={status} body={preview}");
    }
}

/// Split text into Discord-safe chunks using character count (UTF-8 safe).
pub fn split_message_for_discord(message: &str, max_chars: usize) -> Vec<String> {
    if max_chars == 0 {
        return Vec::new();
    }
    if message.is_empty() {
        return Vec::new();
    }

    let mut chunks: Vec<String> = Vec::new();
    let mut current = String::new();
    let mut current_chars = 0usize;

    for ch in message.chars() {
        if current_chars == max_chars {
            chunks.push(current);
            current = String::new();
            current_chars = 0;
        }
        current.push(ch);
        current_chars += 1;
    }

    if !current.is_empty() {
        chunks.push(current);
    }
    chunks
}
