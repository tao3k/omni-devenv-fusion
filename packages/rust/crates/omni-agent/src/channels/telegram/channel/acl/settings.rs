use crate::channels::control_command_authorization::ControlCommandPolicy;
use crate::config::TelegramSettings;

use super::super::TelegramSlashCommandPolicy;
use super::super::admin_rules::parse_admin_command_rule_specs;
use super::super::group_policy::{
    TelegramGroupPolicyConfig, TelegramGroupPolicyMode, parse_group_policy_mode,
};
use super::group_overrides::parse_group_overrides;
use super::normalization::{
    normalize_allowed_group_entries, normalize_allowed_user_entries_with_context,
    normalize_control_command_policy, normalize_group_allow_from, normalize_slash_command_policy,
};
use super::parsing::{
    parse_comma_entries, parse_optional_comma_entries, parse_semicolon_entries,
    resolve_bool_env_or_setting, resolve_optional_env_or_setting, resolve_string_env_or_setting,
};
use super::slash_policy::build_slash_command_policy;
use super::types::{
    TELEGRAM_ACL_FIELD_ADMIN_COMMAND_RULES, TELEGRAM_ACL_FIELD_ALLOWED_USERS, TelegramAclConfig,
};

pub(in crate::channels::telegram::channel) fn resolve_acl_config_from_settings(
    settings: TelegramSettings,
) -> anyhow::Result<TelegramAclConfig> {
    let allowed_users_raw = resolve_string_env_or_setting(
        "OMNI_AGENT_TELEGRAM_ALLOWED_USERS",
        settings.allowed_users,
        "",
    );
    let allowed_groups_raw = resolve_string_env_or_setting(
        "OMNI_AGENT_TELEGRAM_ALLOWED_GROUPS",
        settings.allowed_groups,
        "",
    );
    let session_admin_persist = resolve_bool_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SESSION_ADMIN_PERSIST",
        settings.session_admin_persist,
        false,
    );
    let group_policy_raw = resolve_string_env_or_setting(
        "OMNI_AGENT_TELEGRAM_GROUP_POLICY",
        settings.group_policy,
        "open",
    );
    let group_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_GROUP_ALLOW_FROM",
        settings.group_allow_from,
    );
    let require_mention = resolve_bool_env_or_setting(
        "OMNI_AGENT_TELEGRAM_REQUIRE_MENTION",
        settings.require_mention,
        false,
    );
    let group_entries = settings.groups.unwrap_or_default();
    let admin_users_raw =
        resolve_string_env_or_setting("OMNI_AGENT_TELEGRAM_ADMIN_USERS", settings.admin_users, "");
    let control_command_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_CONTROL_COMMAND_ALLOW_FROM",
        settings.control_command_allow_from,
    );
    let admin_command_rules_raw = resolve_string_env_or_setting(
        "OMNI_AGENT_TELEGRAM_ADMIN_COMMAND_RULES",
        settings.admin_command_rules,
        "",
    );
    let slash_command_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_COMMAND_ALLOW_FROM",
        settings.slash_command_allow_from,
    );
    let slash_session_status_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_STATUS_ALLOW_FROM",
        settings.slash_session_status_allow_from,
    );
    let slash_session_budget_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_BUDGET_ALLOW_FROM",
        settings.slash_session_budget_allow_from,
    );
    let slash_session_memory_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_MEMORY_ALLOW_FROM",
        settings.slash_session_memory_allow_from,
    );
    let slash_session_feedback_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_FEEDBACK_ALLOW_FROM",
        settings.slash_session_feedback_allow_from,
    );
    let slash_job_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_JOB_ALLOW_FROM",
        settings.slash_job_allow_from,
    );
    let slash_jobs_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_JOBS_ALLOW_FROM",
        settings.slash_jobs_allow_from,
    );
    let slash_bg_allow_from_raw = resolve_optional_env_or_setting(
        "OMNI_AGENT_TELEGRAM_SLASH_BG_ALLOW_FROM",
        settings.slash_bg_allow_from,
    );

    let admin_command_rule_specs = parse_semicolon_entries(admin_command_rules_raw.as_str());
    let admin_command_rules = parse_admin_command_rule_specs(admin_command_rule_specs)
        .map_err(|error| anyhow::anyhow!("{TELEGRAM_ACL_FIELD_ADMIN_COMMAND_RULES}: {error}"))?;

    let allowed_users = normalize_allowed_user_entries_with_context(
        parse_comma_entries(allowed_users_raw.as_str()),
        TELEGRAM_ACL_FIELD_ALLOWED_USERS,
    );
    let allowed_groups =
        normalize_allowed_group_entries(parse_comma_entries(allowed_groups_raw.as_str()));
    let group_policy = parse_group_policy_mode(group_policy_raw.as_str(), "telegram.group_policy")
        .unwrap_or(TelegramGroupPolicyMode::Open);
    let group_allow_from =
        normalize_group_allow_from(parse_optional_comma_entries(group_allow_from_raw));
    let admin_users = parse_comma_entries(admin_users_raw.as_str());
    let control_command_allow_from = parse_optional_comma_entries(control_command_allow_from_raw);

    let slash_command_policy = TelegramSlashCommandPolicy {
        slash_command_allow_from: parse_optional_comma_entries(slash_command_allow_from_raw),
        session_status_allow_from: parse_optional_comma_entries(
            slash_session_status_allow_from_raw,
        ),
        session_budget_allow_from: parse_optional_comma_entries(
            slash_session_budget_allow_from_raw,
        ),
        session_memory_allow_from: parse_optional_comma_entries(
            slash_session_memory_allow_from_raw,
        ),
        session_feedback_allow_from: parse_optional_comma_entries(
            slash_session_feedback_allow_from_raw,
        ),
        job_status_allow_from: parse_optional_comma_entries(slash_job_allow_from_raw),
        jobs_summary_allow_from: parse_optional_comma_entries(slash_jobs_allow_from_raw),
        background_submit_allow_from: parse_optional_comma_entries(slash_bg_allow_from_raw),
    };

    let control_command_policy = normalize_control_command_policy(ControlCommandPolicy::new(
        admin_users.clone(),
        control_command_allow_from,
        admin_command_rules,
    ));
    let slash_command_policy = normalize_slash_command_policy(build_slash_command_policy(
        admin_users,
        slash_command_policy,
    ));
    let group_policy_config = TelegramGroupPolicyConfig {
        group_policy,
        group_allow_from,
        require_mention,
        groups: parse_group_overrides(group_entries),
    };

    Ok(TelegramAclConfig {
        allowed_users,
        allowed_groups,
        control_command_policy,
        slash_command_policy,
        group_policy_config,
        session_admin_persist,
    })
}
