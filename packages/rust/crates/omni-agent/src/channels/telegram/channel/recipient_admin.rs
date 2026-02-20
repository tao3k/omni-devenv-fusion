use std::sync::PoisonError;

use crate::channels::traits::RecipientCommandAdminUsersMutation;

use super::TelegramChannel;
use super::acl::normalize_allowed_user_entries_with_context;
use super::group_policy::{
    TelegramGroupOverrideConfig, TelegramGroupPolicyConfig, TelegramTopicPolicyConfig,
};
use super::identity::parse_recipient_target;
use super::session_admin_persistence::persist_session_admin_override_to_user_settings;

#[derive(Debug, Clone, PartialEq, Eq)]
enum TelegramRecipientAdminScope {
    Group(String),
    Topic { chat_id: String, thread_id: i64 },
}

impl TelegramChannel {
    fn recipient_admin_scope(recipient: &str) -> anyhow::Result<TelegramRecipientAdminScope> {
        let (chat_id, thread_id) = parse_recipient_target(recipient);
        if !chat_id.starts_with('-') {
            return Err(anyhow::anyhow!(
                "recipient-scoped admin override is only supported for group chats"
            ));
        }
        match thread_id {
            Some(raw_thread_id) => {
                let parsed = raw_thread_id
                    .parse::<i64>()
                    .map_err(|_| anyhow::anyhow!("invalid topic id in recipient: {recipient}"))?;
                if parsed <= 0 {
                    return Err(anyhow::anyhow!(
                        "invalid topic id in recipient: {recipient}"
                    ));
                }
                Ok(TelegramRecipientAdminScope::Topic {
                    chat_id: chat_id.to_string(),
                    thread_id: parsed,
                })
            }
            None => Ok(TelegramRecipientAdminScope::Group(chat_id.to_string())),
        }
    }

    pub(super) fn recipient_override_admin_users(
        &self,
        recipient: &str,
    ) -> anyhow::Result<Option<Vec<String>>> {
        let scope = Self::recipient_admin_scope(recipient)?;
        let policy = self
            .group_policy_config
            .read()
            .unwrap_or_else(PoisonError::into_inner);
        let admin_users = match scope {
            TelegramRecipientAdminScope::Group(ref chat_id) => policy
                .groups
                .get(chat_id)
                .and_then(|group| group.admin_users.clone()),
            TelegramRecipientAdminScope::Topic {
                ref chat_id,
                thread_id,
            } => policy
                .groups
                .get(chat_id)
                .and_then(|group| group.topics.get(&thread_id))
                .and_then(|topic| topic.admin_users.clone()),
        };
        Ok(admin_users)
    }

    pub(super) fn mutate_recipient_override_admin_users(
        &self,
        recipient: &str,
        mutation: RecipientCommandAdminUsersMutation,
    ) -> anyhow::Result<Option<Vec<String>>> {
        let scope = Self::recipient_admin_scope(recipient)?;
        let current = {
            let policy = self
                .group_policy_config
                .read()
                .unwrap_or_else(PoisonError::into_inner);
            match scope {
                TelegramRecipientAdminScope::Group(ref chat_id) => policy
                    .groups
                    .get(chat_id)
                    .and_then(|group| group.admin_users.clone()),
                TelegramRecipientAdminScope::Topic {
                    ref chat_id,
                    thread_id,
                } => policy
                    .groups
                    .get(chat_id)
                    .and_then(|group| group.topics.get(&thread_id))
                    .and_then(|topic| topic.admin_users.clone()),
            }
        };
        let next = match mutation {
            RecipientCommandAdminUsersMutation::Clear => None,
            RecipientCommandAdminUsersMutation::Set(entries) => {
                Some(normalize_admin_user_mutation_entries(entries)?)
            }
            RecipientCommandAdminUsersMutation::Add(entries) => {
                let mut merged = current.clone().unwrap_or_default();
                let mut additions = normalize_admin_user_mutation_entries(entries)?;
                merged.append(&mut additions);
                Some(dedup_preserve_order(merged))
            }
            RecipientCommandAdminUsersMutation::Remove(entries) => {
                let removals = normalize_admin_user_mutation_entries(entries)?;
                let Some(existing) = current.clone() else {
                    return Ok(None);
                };
                let filtered: Vec<String> = existing
                    .into_iter()
                    .filter(|entry| !removals.iter().any(|removal| removal == entry))
                    .collect();
                if filtered.is_empty() {
                    None
                } else {
                    Some(dedup_preserve_order(filtered))
                }
            }
        };
        if next == current {
            return Ok(next);
        }
        if *self
            .session_admin_persist
            .read()
            .unwrap_or_else(PoisonError::into_inner)
        {
            let user_settings_path = self
                .acl_reload_state
                .read()
                .unwrap_or_else(PoisonError::into_inner)
                .user_settings_path
                .clone();
            persist_session_admin_override_to_user_settings(
                user_settings_path.as_path(),
                recipient,
                next.as_deref(),
            )?;
        }
        let mut policy = self
            .group_policy_config
            .write()
            .unwrap_or_else(PoisonError::into_inner);
        apply_recipient_override_admin_users(&mut policy, &scope, next.clone());
        Ok(next)
    }

    pub(super) fn resolve_group_command_admin_users(&self, recipient: &str) -> Option<Vec<String>> {
        let (chat_id, thread_id) = parse_recipient_target(recipient);
        if !chat_id.starts_with('-') {
            return None;
        }
        let message_thread_id = thread_id.and_then(|value| value.parse::<i64>().ok());
        self.group_policy_config
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .resolve(chat_id, message_thread_id)
            .admin_users
    }
}

fn dedup_preserve_order(entries: Vec<String>) -> Vec<String> {
    let mut deduped: Vec<String> = Vec::new();
    for entry in entries {
        if !deduped.iter().any(|existing| existing == &entry) {
            deduped.push(entry);
        }
    }
    deduped
}

fn normalize_admin_user_mutation_entries(entries: Vec<String>) -> anyhow::Result<Vec<String>> {
    let normalized = dedup_preserve_order(normalize_allowed_user_entries_with_context(
        entries,
        "telegram.runtime.session_admin_users",
    ));
    if normalized.is_empty() {
        return Err(anyhow::anyhow!(
            "no valid Telegram user IDs provided; expected numeric user IDs (or `*` for tests)"
        ));
    }
    Ok(normalized)
}

fn is_topic_policy_config_empty(config: &TelegramTopicPolicyConfig) -> bool {
    config.enabled.is_none()
        && config.group_policy.is_none()
        && config.allow_from.is_none()
        && config.admin_users.is_none()
        && config.require_mention.is_none()
}

fn is_group_override_config_empty(config: &TelegramGroupOverrideConfig) -> bool {
    config.enabled.is_none()
        && config.group_policy.is_none()
        && config.allow_from.is_none()
        && config.admin_users.is_none()
        && config.require_mention.is_none()
        && config.topics.is_empty()
}

fn apply_recipient_override_admin_users(
    policy: &mut TelegramGroupPolicyConfig,
    scope: &TelegramRecipientAdminScope,
    admin_users: Option<Vec<String>>,
) {
    match scope {
        TelegramRecipientAdminScope::Group(chat_id) => {
            let mut remove_group = false;
            if let Some(group) = policy.groups.get_mut(chat_id) {
                group.admin_users = admin_users.clone();
                remove_group = is_group_override_config_empty(group);
            } else if let Some(admin_users) = admin_users {
                policy.groups.insert(
                    chat_id.clone(),
                    TelegramGroupOverrideConfig {
                        admin_users: Some(admin_users),
                        ..TelegramGroupOverrideConfig::default()
                    },
                );
            }
            if remove_group {
                policy.groups.remove(chat_id);
            }
        }
        TelegramRecipientAdminScope::Topic { chat_id, thread_id } => {
            let mut remove_group = false;
            if let Some(group) = policy.groups.get_mut(chat_id) {
                if let Some(topic) = group.topics.get_mut(thread_id) {
                    topic.admin_users = admin_users.clone();
                    if is_topic_policy_config_empty(topic) {
                        group.topics.remove(thread_id);
                    }
                } else if let Some(admin_users) = admin_users.clone() {
                    group.topics.insert(
                        *thread_id,
                        TelegramTopicPolicyConfig {
                            admin_users: Some(admin_users),
                            ..TelegramTopicPolicyConfig::default()
                        },
                    );
                }
                remove_group = is_group_override_config_empty(group);
            } else if let Some(admin_users) = admin_users {
                let mut group = TelegramGroupOverrideConfig::default();
                group.topics.insert(
                    *thread_id,
                    TelegramTopicPolicyConfig {
                        admin_users: Some(admin_users),
                        ..TelegramTopicPolicyConfig::default()
                    },
                );
                policy.groups.insert(chat_id.clone(), group);
            }
            if remove_group {
                policy.groups.remove(chat_id);
            }
        }
    }
}
