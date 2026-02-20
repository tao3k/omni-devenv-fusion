use std::collections::HashMap;

use crate::config::{TelegramGroupSettings, TelegramTopicSettings};

use super::super::group_policy::{
    TelegramGroupOverrideConfig, TelegramTopicPolicyConfig, parse_group_policy_mode,
};
use super::super::identity::normalize_group_identity;
use super::normalization::normalize_optional_allowed_user_entries_with_context;
use super::parsing::parse_optional_comma_entries;

pub(super) fn parse_group_overrides(
    groups: HashMap<String, TelegramGroupSettings>,
) -> HashMap<String, TelegramGroupOverrideConfig> {
    let mut overrides = HashMap::new();
    for (raw_group_id, group_settings) in groups {
        let group_id = raw_group_id.trim();
        let normalized_group_id = if group_id == "*" {
            "*".to_string()
        } else {
            normalize_group_identity(group_id)
        };
        if normalized_group_id.is_empty() {
            tracing::warn!(
                group_id = %raw_group_id,
                "telegram group override ignored: empty group id"
            );
            continue;
        }
        let context_prefix = format!("telegram.groups.{normalized_group_id}");
        let group_policy = group_settings.group_policy.as_deref().and_then(|raw| {
            parse_group_policy_mode(raw, format!("{context_prefix}.group_policy").as_str())
        });
        let allow_from_field = format!("{context_prefix}.allow_from");
        let allow_from = normalize_optional_allowed_user_entries_with_context(
            parse_optional_comma_entries(group_settings.allow_from),
            allow_from_field.as_str(),
        );
        let admin_users_field = format!("{context_prefix}.admin_users");
        let admin_users = normalize_optional_allowed_user_entries_with_context(
            parse_optional_comma_entries(group_settings.admin_users),
            admin_users_field.as_str(),
        );
        let topics = parse_topic_overrides(normalized_group_id.as_str(), group_settings.topics);
        overrides.insert(
            normalized_group_id,
            TelegramGroupOverrideConfig {
                enabled: group_settings.enabled,
                group_policy,
                allow_from,
                admin_users,
                require_mention: group_settings.require_mention,
                topics,
            },
        );
    }
    overrides
}

fn parse_topic_overrides(
    group_id: &str,
    topics: Option<HashMap<String, TelegramTopicSettings>>,
) -> HashMap<i64, TelegramTopicPolicyConfig> {
    let mut overrides = HashMap::new();
    let Some(topics) = topics else {
        return overrides;
    };
    for (raw_topic_id, topic_settings) in topics {
        let topic_id = match raw_topic_id.trim().parse::<i64>() {
            Ok(value) if value > 0 => value,
            _ => {
                tracing::warn!(
                    group_id = %group_id,
                    topic_id = %raw_topic_id,
                    "telegram topic override ignored: topic id must be a positive integer"
                );
                continue;
            }
        };
        let context_prefix = format!("telegram.groups.{group_id}.topics.{topic_id}");
        let group_policy = topic_settings.group_policy.as_deref().and_then(|raw| {
            parse_group_policy_mode(raw, format!("{context_prefix}.group_policy").as_str())
        });
        let allow_from_field = format!("{context_prefix}.allow_from");
        let allow_from = normalize_optional_allowed_user_entries_with_context(
            parse_optional_comma_entries(topic_settings.allow_from),
            allow_from_field.as_str(),
        );
        let admin_users_field = format!("{context_prefix}.admin_users");
        let admin_users = normalize_optional_allowed_user_entries_with_context(
            parse_optional_comma_entries(topic_settings.admin_users),
            admin_users_field.as_str(),
        );
        overrides.insert(
            topic_id,
            TelegramTopicPolicyConfig {
                enabled: topic_settings.enabled,
                group_policy,
                allow_from,
                admin_users,
                require_mention: topic_settings.require_mention,
            },
        );
    }
    overrides
}
