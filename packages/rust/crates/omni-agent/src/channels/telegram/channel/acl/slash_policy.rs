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

use super::super::{TelegramSlashCommandPolicy, TelegramSlashCommandRule};

pub(in crate::channels::telegram::channel) fn build_slash_command_policy(
    admin_users: Vec<String>,
    slash_policy: TelegramSlashCommandPolicy,
) -> ControlCommandPolicy<TelegramSlashCommandRule> {
    let admin_users_for_rules = admin_users.clone();
    let mut rules = Vec::new();
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_SESSION_STATUS,
        slash_policy.session_status_allow_from,
        &admin_users_for_rules,
    );
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_SESSION_BUDGET,
        slash_policy.session_budget_allow_from,
        &admin_users_for_rules,
    );
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_SESSION_MEMORY,
        slash_policy.session_memory_allow_from,
        &admin_users_for_rules,
    );
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_SESSION_FEEDBACK,
        slash_policy.session_feedback_allow_from,
        &admin_users_for_rules,
    );
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_JOB_STATUS,
        slash_policy.job_status_allow_from,
        &admin_users_for_rules,
    );
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_JOBS_SUMMARY,
        slash_policy.jobs_summary_allow_from,
        &admin_users_for_rules,
    );
    add_slash_rule(
        &mut rules,
        TELEGRAM_SLASH_SCOPE_BACKGROUND_SUBMIT,
        slash_policy.background_submit_allow_from,
        &admin_users_for_rules,
    );
    ControlCommandPolicy::new(admin_users, slash_policy.slash_command_allow_from, rules)
}

fn add_slash_rule(
    rules: &mut Vec<TelegramSlashCommandRule>,
    command_scope: &'static str,
    allow_from: Option<Vec<String>>,
    admin_users: &[String],
) {
    if let Some(mut allowed_identities) = allow_from {
        allowed_identities.extend(admin_users.iter().cloned());
        rules.push(TelegramSlashCommandRule::new(
            command_scope,
            allowed_identities,
        ));
    }
}
