use std::sync::PoisonError;

use crate::channels::traits::ChannelMessage;

use super::identity::{normalize_group_identity, normalize_user_identity};
use super::{TelegramChannel, TelegramGroupPolicyMode};

impl TelegramChannel {
    fn is_user_allowed(&self, identity: &str) -> bool {
        let normalized = normalize_user_identity(identity);
        self.allowed_users
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .iter()
            .any(|u| u == "*" || u == &normalized)
    }

    fn is_identity_in_allowlist(&self, identity: &str, allowlist: &[String]) -> bool {
        let normalized = normalize_user_identity(identity);
        if normalized.is_empty() {
            return false;
        }
        allowlist
            .iter()
            .any(|entry| entry == "*" || entry == &normalized)
    }

    fn is_group_allowed(&self, chat_id: &str) -> bool {
        let normalized = normalize_group_identity(chat_id);
        self.allowed_groups
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .iter()
            .any(|g| g == "*" || g == &normalized)
    }

    fn build_session_key(
        &self,
        chat_id: &str,
        user_identity: &str,
        message_thread_id: Option<i64>,
    ) -> String {
        self.session_partition()
            .build_session_key(chat_id, user_identity, message_thread_id)
    }

    /// Parse a Telegram update into a channel message (returns None for unsupported updates).
    pub fn parse_update_message(&self, update: &serde_json::Value) -> Option<ChannelMessage> {
        self.ensure_acl_fresh();

        let message = update.get("message")?;
        let text = message.get("text").and_then(serde_json::Value::as_str)?;

        let chat = message.get("chat")?;
        let chat_id = chat
            .get("id")
            .and_then(serde_json::Value::as_i64)
            .map(|id| id.to_string())?;
        let chat_title = chat
            .get("title")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("(not set)");
        let chat_type = chat
            .get("type")
            .and_then(serde_json::Value::as_str)
            .unwrap_or("(not set)");

        let username = message
            .get("from")
            .and_then(|f| f.get("username"))
            .and_then(|u| u.as_str());
        let user_id = message
            .get("from")
            .and_then(|f| f.get("id"))
            .and_then(serde_json::Value::as_i64)
            .map(|id| id.to_string());
        let message_thread_id = message
            .get("message_thread_id")
            .and_then(serde_json::Value::as_i64);

        let allowed_by_group = chat_id.starts_with('-') && self.is_group_allowed(&chat_id);
        let allowed_by_user = user_id
            .as_deref()
            .is_some_and(|identity| self.is_user_allowed(identity));

        if !allowed_by_group && !allowed_by_user {
            tracing::warn!(
                "Telegram: ignoring message from unauthorized user. \
                 Add to allowed_users (user_id={}, username={}) or allowed_groups (chat_id={}, chat_title={}, chat_type={})",
                user_id.as_deref().unwrap_or("-"),
                username.unwrap_or("(not set)"),
                chat_id,
                chat_title,
                chat_type
            );
            return None;
        }

        let user_identity = user_id
            .clone()
            .unwrap_or_else(|| username.unwrap_or("unknown").to_string());
        let is_group_chat = chat_id.starts_with('-');
        if is_group_chat {
            let effective_policy = self
                .group_policy_config
                .read()
                .unwrap_or_else(PoisonError::into_inner)
                .resolve(&chat_id, message_thread_id);

            if !effective_policy.enabled
                || matches!(
                    effective_policy.group_policy,
                    TelegramGroupPolicyMode::Disabled
                )
            {
                tracing::debug!(
                    chat_id = %chat_id,
                    user_id = %user_identity,
                    message_thread_id = ?message_thread_id,
                    "telegram group message ignored: group policy disabled"
                );
                return None;
            }

            if matches!(
                effective_policy.group_policy,
                TelegramGroupPolicyMode::Allowlist
            ) {
                let sender_allowed = match &effective_policy.allow_from {
                    Some(entries) => self.is_identity_in_allowlist(user_identity.as_str(), entries),
                    None => allowed_by_user,
                };
                if !sender_allowed {
                    tracing::debug!(
                        chat_id = %chat_id,
                        user_id = %user_identity,
                        message_thread_id = ?message_thread_id,
                        "telegram group message ignored: sender not in allowlist policy"
                    );
                    return None;
                }
            }

            if effective_policy.require_mention && !is_message_triggered_for_group(message, text) {
                tracing::debug!(
                    chat_id = %chat_id,
                    user_id = %user_identity,
                    message_thread_id = ?message_thread_id,
                    "telegram group message ignored: require_mention enabled and no mention trigger detected"
                );
                return None;
            }
        }

        let message_id = message
            .get("message_id")
            .and_then(serde_json::Value::as_i64)
            .unwrap_or_default();
        let update_id = update
            .get("update_id")
            .and_then(serde_json::Value::as_i64)
            .unwrap_or_default();
        let session_key = self.build_session_key(&chat_id, &user_identity, message_thread_id);
        let recipient = if let Some(thread_id) = message_thread_id {
            format!("{chat_id}:{thread_id}")
        } else {
            chat_id.clone()
        };

        Some(ChannelMessage {
            id: format!("telegram_{chat_id}_{message_id}_{update_id}"),
            sender: user_identity,
            recipient,
            session_key,
            content: text.to_string(),
            channel: "telegram".to_string(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
        })
    }
}

fn is_message_triggered_for_group(message: &serde_json::Value, text: &str) -> bool {
    let trimmed = text.trim_start();
    if trimmed.starts_with('/') {
        return true;
    }
    if trimmed.contains('@') {
        return true;
    }
    if message
        .get("reply_to_message")
        .and_then(|reply| reply.get("from"))
        .and_then(|from| from.get("is_bot"))
        .and_then(serde_json::Value::as_bool)
        .unwrap_or(false)
    {
        return true;
    }
    message
        .get("entities")
        .and_then(serde_json::Value::as_array)
        .is_some_and(|entities| {
            entities.iter().any(|entity| {
                entity
                    .get("type")
                    .and_then(serde_json::Value::as_str)
                    .is_some_and(|entity_type| {
                        matches!(entity_type, "mention" | "text_mention" | "bot_command")
                    })
            })
        })
}
