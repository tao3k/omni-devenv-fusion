use crate::channels::control_command_authorization::ControlCommandPolicy;
use crate::channels::managed_commands::{
    SLASH_SCOPE_BACKGROUND_SUBMIT as TELEGRAM_SLASH_SCOPE_BACKGROUND_SUBMIT,
    SLASH_SCOPE_JOB_STATUS as TELEGRAM_SLASH_SCOPE_JOB_STATUS,
    SLASH_SCOPE_JOBS_SUMMARY as TELEGRAM_SLASH_SCOPE_JOBS_SUMMARY,
    SLASH_SCOPE_SESSION_BUDGET as TELEGRAM_SLASH_SCOPE_SESSION_BUDGET,
    SLASH_SCOPE_SESSION_FEEDBACK as TELEGRAM_SLASH_SCOPE_SESSION_FEEDBACK,
    SLASH_SCOPE_SESSION_MEMORY as TELEGRAM_SLASH_SCOPE_SESSION_MEMORY,
    SLASH_SCOPE_SESSION_STATUS as TELEGRAM_SLASH_SCOPE_SESSION_STATUS,
};

use super::super::TelegramSlashCommandRule;
use super::super::admin_rules::TelegramCommandAdminRule;
use super::super::identity::{normalize_group_identity, normalize_user_identity};
use super::types::{
    TELEGRAM_ACL_FIELD_ADMIN_USERS, TELEGRAM_ACL_FIELD_CONTROL_COMMAND_ALLOW_FROM,
    TELEGRAM_ACL_FIELD_GROUP_ALLOW_FROM, TELEGRAM_ACL_FIELD_SLASH_BG_ALLOW_FROM,
    TELEGRAM_ACL_FIELD_SLASH_COMMAND_ALLOW_FROM, TELEGRAM_ACL_FIELD_SLASH_JOB_ALLOW_FROM,
    TELEGRAM_ACL_FIELD_SLASH_JOBS_ALLOW_FROM, TELEGRAM_ACL_FIELD_SLASH_SESSION_BUDGET_ALLOW_FROM,
    TELEGRAM_ACL_FIELD_SLASH_SESSION_FEEDBACK_ALLOW_FROM,
    TELEGRAM_ACL_FIELD_SLASH_SESSION_MEMORY_ALLOW_FROM,
    TELEGRAM_ACL_FIELD_SLASH_SESSION_STATUS_ALLOW_FROM,
};

pub(in crate::channels::telegram::channel) fn normalize_allowed_user_entries_with_context(
    entries: Vec<String>,
    field: &str,
) -> Vec<String> {
    entries
        .into_iter()
        .filter_map(|entry| {
            let normalized = normalize_user_identity(&entry);
            if normalized.is_empty() {
                tracing::warn!(
                    field = %field,
                    entry = %entry,
                    "telegram identity ignored: expected numeric user IDs (or `*` for tests)"
                );
                return None;
            }
            Some(normalized)
        })
        .collect()
}

pub(in crate::channels::telegram::channel) fn normalize_allowed_group_entries(
    entries: Vec<String>,
) -> Vec<String> {
    entries
        .into_iter()
        .map(|entry| normalize_group_identity(&entry))
        .filter(|entry| !entry.is_empty())
        .collect()
}

pub(in crate::channels::telegram::channel) fn normalize_optional_allowed_user_entries_with_context(
    entries: Option<Vec<String>>,
    field: &str,
) -> Option<Vec<String>> {
    entries.map(|entries| normalize_allowed_user_entries_with_context(entries, field))
}

pub(in crate::channels::telegram::channel) fn normalize_control_command_policy(
    policy: ControlCommandPolicy<TelegramCommandAdminRule>,
) -> ControlCommandPolicy<TelegramCommandAdminRule> {
    ControlCommandPolicy::new(
        normalize_allowed_user_entries_with_context(
            policy.admin_users,
            TELEGRAM_ACL_FIELD_ADMIN_USERS,
        ),
        normalize_optional_allowed_user_entries_with_context(
            policy.control_command_allow_from,
            TELEGRAM_ACL_FIELD_CONTROL_COMMAND_ALLOW_FROM,
        ),
        policy.rules,
    )
}

fn slash_rule_field_name(command_scope: &str) -> &'static str {
    match command_scope {
        TELEGRAM_SLASH_SCOPE_SESSION_STATUS => TELEGRAM_ACL_FIELD_SLASH_SESSION_STATUS_ALLOW_FROM,
        TELEGRAM_SLASH_SCOPE_SESSION_BUDGET => TELEGRAM_ACL_FIELD_SLASH_SESSION_BUDGET_ALLOW_FROM,
        TELEGRAM_SLASH_SCOPE_SESSION_MEMORY => TELEGRAM_ACL_FIELD_SLASH_SESSION_MEMORY_ALLOW_FROM,
        TELEGRAM_SLASH_SCOPE_SESSION_FEEDBACK => {
            TELEGRAM_ACL_FIELD_SLASH_SESSION_FEEDBACK_ALLOW_FROM
        }
        TELEGRAM_SLASH_SCOPE_JOB_STATUS => TELEGRAM_ACL_FIELD_SLASH_JOB_ALLOW_FROM,
        TELEGRAM_SLASH_SCOPE_JOBS_SUMMARY => TELEGRAM_ACL_FIELD_SLASH_JOBS_ALLOW_FROM,
        TELEGRAM_SLASH_SCOPE_BACKGROUND_SUBMIT => TELEGRAM_ACL_FIELD_SLASH_BG_ALLOW_FROM,
        _ => TELEGRAM_ACL_FIELD_SLASH_COMMAND_ALLOW_FROM,
    }
}

pub(in crate::channels::telegram::channel) fn normalize_slash_command_policy(
    policy: ControlCommandPolicy<TelegramSlashCommandRule>,
) -> ControlCommandPolicy<TelegramSlashCommandRule> {
    let rules = policy
        .rules
        .into_iter()
        .map(|rule| {
            TelegramSlashCommandRule::new(
                rule.command_scope,
                normalize_allowed_user_entries_with_context(
                    rule.allowed_identities,
                    slash_rule_field_name(rule.command_scope),
                ),
            )
        })
        .collect();
    ControlCommandPolicy::new(
        normalize_allowed_user_entries_with_context(
            policy.admin_users,
            TELEGRAM_ACL_FIELD_ADMIN_USERS,
        ),
        normalize_optional_allowed_user_entries_with_context(
            policy.control_command_allow_from,
            TELEGRAM_ACL_FIELD_SLASH_COMMAND_ALLOW_FROM,
        ),
        rules,
    )
}

pub(in crate::channels::telegram::channel) fn normalize_group_allow_from(
    entries: Option<Vec<String>>,
) -> Option<Vec<String>> {
    normalize_optional_allowed_user_entries_with_context(
        entries,
        TELEGRAM_ACL_FIELD_GROUP_ALLOW_FROM,
    )
}
