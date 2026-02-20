use std::collections::HashMap;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) enum TelegramGroupPolicyMode {
    Open,
    Allowlist,
    Disabled,
}

impl Default for TelegramGroupPolicyMode {
    fn default() -> Self {
        Self::Open
    }
}

pub(super) fn parse_group_policy_mode(raw: &str, context: &str) -> Option<TelegramGroupPolicyMode> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "open" => Some(TelegramGroupPolicyMode::Open),
        "allowlist" => Some(TelegramGroupPolicyMode::Allowlist),
        "disabled" => Some(TelegramGroupPolicyMode::Disabled),
        _ => {
            tracing::warn!(
                context = %context,
                value = %raw,
                "invalid telegram group policy mode; expected open|allowlist|disabled"
            );
            None
        }
    }
}

#[derive(Debug, Clone, Default)]
pub(super) struct TelegramTopicPolicyConfig {
    pub(super) enabled: Option<bool>,
    pub(super) group_policy: Option<TelegramGroupPolicyMode>,
    pub(super) allow_from: Option<Vec<String>>,
    pub(super) admin_users: Option<Vec<String>>,
    pub(super) require_mention: Option<bool>,
}

#[derive(Debug, Clone, Default)]
pub(super) struct TelegramGroupOverrideConfig {
    pub(super) enabled: Option<bool>,
    pub(super) group_policy: Option<TelegramGroupPolicyMode>,
    pub(super) allow_from: Option<Vec<String>>,
    pub(super) admin_users: Option<Vec<String>>,
    pub(super) require_mention: Option<bool>,
    pub(super) topics: HashMap<i64, TelegramTopicPolicyConfig>,
}

#[derive(Debug, Clone)]
pub(super) struct TelegramGroupPolicyConfig {
    pub(super) group_policy: TelegramGroupPolicyMode,
    pub(super) group_allow_from: Option<Vec<String>>,
    pub(super) require_mention: bool,
    pub(super) groups: HashMap<String, TelegramGroupOverrideConfig>,
}

impl Default for TelegramGroupPolicyConfig {
    fn default() -> Self {
        Self {
            group_policy: TelegramGroupPolicyMode::Open,
            group_allow_from: None,
            require_mention: false,
            groups: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone)]
pub(super) struct TelegramEffectiveGroupPolicy {
    pub(super) enabled: bool,
    pub(super) group_policy: TelegramGroupPolicyMode,
    pub(super) allow_from: Option<Vec<String>>,
    pub(super) admin_users: Option<Vec<String>>,
    pub(super) require_mention: bool,
}

impl TelegramGroupPolicyConfig {
    pub(super) fn resolve(
        &self,
        chat_id: &str,
        message_thread_id: Option<i64>,
    ) -> TelegramEffectiveGroupPolicy {
        let mut effective = TelegramEffectiveGroupPolicy {
            enabled: true,
            group_policy: self.group_policy,
            allow_from: self.group_allow_from.clone(),
            admin_users: None,
            require_mention: self.require_mention,
        };

        if let Some(global_group) = self.groups.get("*") {
            apply_group_override(&mut effective, global_group);
            if let Some(thread_id) = message_thread_id
                && let Some(topic) = global_group.topics.get(&thread_id)
            {
                apply_topic_override(&mut effective, topic);
            }
        }

        if let Some(group) = self.groups.get(chat_id) {
            apply_group_override(&mut effective, group);
            if let Some(thread_id) = message_thread_id
                && let Some(topic) = group.topics.get(&thread_id)
            {
                apply_topic_override(&mut effective, topic);
            }
        }

        effective
    }
}

fn apply_group_override(
    effective: &mut TelegramEffectiveGroupPolicy,
    override_config: &TelegramGroupOverrideConfig,
) {
    if let Some(enabled) = override_config.enabled {
        effective.enabled = enabled;
    }
    if let Some(mode) = override_config.group_policy {
        effective.group_policy = mode;
    }
    if let Some(allow_from) = &override_config.allow_from {
        effective.allow_from = Some(allow_from.clone());
    }
    if let Some(admin_users) = &override_config.admin_users {
        effective.admin_users = Some(admin_users.clone());
    }
    if let Some(require_mention) = override_config.require_mention {
        effective.require_mention = require_mention;
    }
}

fn apply_topic_override(
    effective: &mut TelegramEffectiveGroupPolicy,
    override_config: &TelegramTopicPolicyConfig,
) {
    if let Some(enabled) = override_config.enabled {
        effective.enabled = enabled;
    }
    if let Some(mode) = override_config.group_policy {
        effective.group_policy = mode;
    }
    if let Some(allow_from) = &override_config.allow_from {
        effective.allow_from = Some(allow_from.clone());
    }
    if let Some(admin_users) = &override_config.admin_users {
        effective.admin_users = Some(admin_users.clone());
    }
    if let Some(require_mention) = override_config.require_mention {
        effective.require_mention = require_mention;
    }
}
