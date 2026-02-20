use crate::channels::traits::ChannelMessage;

use super::channel::DiscordChannel;

impl DiscordChannel {
    fn is_user_allowed(&self, identity: &str) -> bool {
        let normalized = self.normalize_identity(identity);
        self.allowed_users
            .iter()
            .any(|entry| entry == "*" || entry == &normalized)
    }

    fn is_any_user_allowed<'a, I>(&self, identities: I) -> bool
    where
        I: IntoIterator<Item = &'a str>,
    {
        identities
            .into_iter()
            .any(|identity| self.is_user_allowed(identity))
    }

    fn is_guild_allowed(&self, guild_id: &str) -> bool {
        let normalized = guild_id.trim();
        self.allowed_guilds
            .iter()
            .any(|entry| entry == "*" || entry == normalized)
    }

    fn build_session_key(&self, scope: &str, channel_id: &str, user_identity: &str) -> String {
        self.session_partition()
            .build_session_key(scope, channel_id, user_identity)
    }

    /// Parse a Discord gateway-style message payload into a channel message.
    ///
    /// Expected shape (subset):
    /// - `id` (message id)
    /// - `content` (text)
    /// - `channel_id`
    /// - optional `guild_id` (missing for DMs)
    /// - `author.id`, optional `author.username`
    pub fn parse_gateway_message(&self, event: &serde_json::Value) -> Option<ChannelMessage> {
        let message_id = event.get("id").and_then(serde_json::Value::as_str)?;
        let text = event.get("content").and_then(serde_json::Value::as_str)?;
        if text.trim().is_empty() {
            return None;
        }

        let channel_id = event
            .get("channel_id")
            .and_then(serde_json::Value::as_str)?;
        let guild_id = event.get("guild_id").and_then(serde_json::Value::as_str);
        let author = event.get("author")?;
        let author_id = author.get("id").and_then(serde_json::Value::as_str)?;
        let username = author.get("username").and_then(serde_json::Value::as_str);

        let allowed_by_guild = guild_id.is_some_and(|id| self.is_guild_allowed(id));
        let mut identities = vec![author_id];
        if let Some(name) = username {
            identities.push(name);
        }
        let allowed_by_user = self.is_any_user_allowed(identities);

        if !allowed_by_guild && !allowed_by_user {
            tracing::warn!(
                "Discord: ignoring message from unauthorized sender (user_id={}, username={}, guild_id={}, channel_id={})",
                author_id,
                username.unwrap_or("(not set)"),
                guild_id.unwrap_or("(dm)"),
                channel_id
            );
            return None;
        }

        let scope = guild_id.unwrap_or("dm");
        let sender = self.normalize_identity(author_id);
        let session_key = self.build_session_key(scope, channel_id, &sender);

        Some(ChannelMessage {
            id: format!("discord_{channel_id}_{message_id}"),
            sender,
            recipient: channel_id.to_string(),
            session_key,
            content: text.to_string(),
            channel: "discord".to_string(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        })
    }
}
