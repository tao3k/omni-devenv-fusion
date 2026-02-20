use std::sync::Arc;

use omni_agent::{
    DEFAULT_REDIS_KEY_PREFIX, RuntimeSettings, TelegramControlCommandPolicy,
    TelegramSlashCommandPolicy, WebhookDedupBackend, WebhookDedupConfig,
    run_telegram_webhook_with_control_command_policy, run_telegram_with_control_command_policy,
};

use crate::agent_builder::build_agent;
use crate::cli::{TelegramChannelMode, WebhookDedupBackendMode};
use crate::resolve::{
    resolve_channel_mode, resolve_dedup_backend, resolve_optional_string, resolve_positive_u64,
    resolve_string,
};

use super::ChannelCommandRequest;
use super::common::{
    log_control_command_allow_override, log_slash_command_allow_override,
    parse_comma_separated_entries, parse_optional_comma_separated_entries,
    parse_semicolon_separated_entries,
};

pub(super) async fn run_telegram_channel_command(
    req: ChannelCommandRequest,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let ChannelCommandRequest {
        bot_token,
        allowed_users,
        allowed_groups,
        admin_users,
        control_command_allow_from,
        admin_command_rules,
        slash_command_allow_from,
        slash_session_status_allow_from,
        slash_session_budget_allow_from,
        slash_session_memory_allow_from,
        slash_session_feedback_allow_from,
        slash_job_allow_from,
        slash_jobs_allow_from,
        slash_bg_allow_from,
        mcp_config,
        mode,
        webhook_bind,
        webhook_path,
        webhook_secret_token,
        webhook_dedup_backend,
        valkey_url,
        webhook_dedup_ttl_secs,
        webhook_dedup_key_prefix,
        ..
    } = req;

    let channel_mode = resolve_channel_mode(mode, runtime_settings.telegram.mode.as_deref());
    let allowed_users = resolve_string(
        allowed_users,
        "OMNI_AGENT_TELEGRAM_ALLOWED_USERS",
        runtime_settings.telegram.allowed_users.as_deref(),
        "",
    );
    let allowed_groups = resolve_string(
        allowed_groups,
        "OMNI_AGENT_TELEGRAM_ALLOWED_GROUPS",
        runtime_settings.telegram.allowed_groups.as_deref(),
        "",
    );
    let admin_users = resolve_string(
        admin_users,
        "OMNI_AGENT_TELEGRAM_ADMIN_USERS",
        runtime_settings.telegram.admin_users.as_deref(),
        "",
    );
    let control_command_allow_from = resolve_optional_string(
        control_command_allow_from,
        "OMNI_AGENT_TELEGRAM_CONTROL_COMMAND_ALLOW_FROM",
        runtime_settings
            .telegram
            .control_command_allow_from
            .as_deref(),
    );
    let admin_command_rules = resolve_string(
        admin_command_rules,
        "OMNI_AGENT_TELEGRAM_ADMIN_COMMAND_RULES",
        runtime_settings.telegram.admin_command_rules.as_deref(),
        "",
    );
    let slash_command_allow_from = resolve_optional_string(
        slash_command_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_COMMAND_ALLOW_FROM",
        runtime_settings
            .telegram
            .slash_command_allow_from
            .as_deref(),
    );
    let slash_session_status_allow_from = resolve_optional_string(
        slash_session_status_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_STATUS_ALLOW_FROM",
        runtime_settings
            .telegram
            .slash_session_status_allow_from
            .as_deref(),
    );
    let slash_session_budget_allow_from = resolve_optional_string(
        slash_session_budget_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_BUDGET_ALLOW_FROM",
        runtime_settings
            .telegram
            .slash_session_budget_allow_from
            .as_deref(),
    );
    let slash_session_memory_allow_from = resolve_optional_string(
        slash_session_memory_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_MEMORY_ALLOW_FROM",
        runtime_settings
            .telegram
            .slash_session_memory_allow_from
            .as_deref(),
    );
    let slash_session_feedback_allow_from = resolve_optional_string(
        slash_session_feedback_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_SESSION_FEEDBACK_ALLOW_FROM",
        runtime_settings
            .telegram
            .slash_session_feedback_allow_from
            .as_deref(),
    );
    let slash_job_allow_from = resolve_optional_string(
        slash_job_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_JOB_ALLOW_FROM",
        runtime_settings.telegram.slash_job_allow_from.as_deref(),
    );
    let slash_jobs_allow_from = resolve_optional_string(
        slash_jobs_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_JOBS_ALLOW_FROM",
        runtime_settings.telegram.slash_jobs_allow_from.as_deref(),
    );
    let slash_bg_allow_from = resolve_optional_string(
        slash_bg_allow_from,
        "OMNI_AGENT_TELEGRAM_SLASH_BG_ALLOW_FROM",
        runtime_settings.telegram.slash_bg_allow_from.as_deref(),
    );
    let webhook_bind = resolve_string(
        webhook_bind,
        "OMNI_AGENT_TELEGRAM_WEBHOOK_BIND",
        runtime_settings.telegram.webhook_bind.as_deref(),
        "127.0.0.1:8081",
    );
    let webhook_path = resolve_string(
        webhook_path,
        "OMNI_AGENT_TELEGRAM_WEBHOOK_PATH",
        runtime_settings.telegram.webhook_path.as_deref(),
        "/telegram/webhook",
    );
    let dedup_backend = resolve_dedup_backend(
        webhook_dedup_backend,
        runtime_settings.telegram.webhook_dedup_backend.as_deref(),
    );
    let webhook_dedup_ttl_secs = resolve_positive_u64(
        webhook_dedup_ttl_secs,
        "OMNI_AGENT_TELEGRAM_WEBHOOK_DEDUP_TTL_SECS",
        runtime_settings.telegram.webhook_dedup_ttl_secs,
        600,
    );
    let webhook_dedup_key_prefix = resolve_string(
        webhook_dedup_key_prefix,
        "OMNI_AGENT_TELEGRAM_WEBHOOK_DEDUP_KEY_PREFIX",
        runtime_settings
            .telegram
            .webhook_dedup_key_prefix
            .as_deref(),
        DEFAULT_REDIS_KEY_PREFIX,
    );
    let token = bot_token
        .or_else(|| std::env::var("TELEGRAM_BOT_TOKEN").ok())
        .ok_or_else(|| anyhow::anyhow!("--bot-token or TELEGRAM_BOT_TOKEN required"))?;
    let secret_token = resolve_webhook_secret_token(channel_mode, webhook_secret_token)?;
    let dedup_config = build_webhook_dedup_config(
        dedup_backend,
        valkey_url,
        webhook_dedup_ttl_secs,
        webhook_dedup_key_prefix,
        runtime_settings,
    )?;

    run_telegram_channel_mode(
        token,
        allowed_users,
        allowed_groups,
        admin_users,
        control_command_allow_from,
        admin_command_rules,
        slash_command_allow_from,
        slash_session_status_allow_from,
        slash_session_budget_allow_from,
        slash_session_memory_allow_from,
        slash_session_feedback_allow_from,
        slash_job_allow_from,
        slash_jobs_allow_from,
        slash_bg_allow_from,
        mcp_config,
        channel_mode,
        webhook_bind,
        webhook_path,
        secret_token,
        dedup_config,
        runtime_settings,
    )
    .await
}

fn resolve_webhook_secret_token(
    channel_mode: TelegramChannelMode,
    cli_secret: Option<String>,
) -> anyhow::Result<Option<String>> {
    let secret = cli_secret
        .or_else(|| std::env::var("TELEGRAM_WEBHOOK_SECRET").ok())
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty());
    if matches!(channel_mode, TelegramChannelMode::Webhook) && secret.is_none() {
        return Err(anyhow::anyhow!(
            "webhook mode requires TELEGRAM_WEBHOOK_SECRET (or --webhook-secret-token)"
        ));
    }
    Ok(secret)
}

async fn run_telegram_channel_mode(
    bot_token: String,
    allowed_users: String,
    allowed_groups: String,
    admin_users: String,
    control_command_allow_from: Option<String>,
    admin_command_rules: String,
    slash_command_allow_from: Option<String>,
    slash_session_status_allow_from: Option<String>,
    slash_session_budget_allow_from: Option<String>,
    slash_session_memory_allow_from: Option<String>,
    slash_session_feedback_allow_from: Option<String>,
    slash_job_allow_from: Option<String>,
    slash_jobs_allow_from: Option<String>,
    slash_bg_allow_from: Option<String>,
    mcp_config_path: std::path::PathBuf,
    mode: TelegramChannelMode,
    webhook_bind: String,
    webhook_path: String,
    webhook_secret_token: Option<String>,
    webhook_dedup_config: WebhookDedupConfig,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let agent = Arc::new(build_agent(&mcp_config_path, runtime_settings).await?);
    let users = parse_comma_separated_entries(&allowed_users);
    let groups = parse_comma_separated_entries(&allowed_groups);
    let admins = parse_comma_separated_entries(&admin_users);
    let control_command_allow_from_entries =
        parse_optional_comma_separated_entries(control_command_allow_from);
    log_control_command_allow_override("telegram", &control_command_allow_from_entries);
    let slash_command_allow_from_entries =
        parse_optional_comma_separated_entries(slash_command_allow_from);
    log_slash_command_allow_override("telegram", &slash_command_allow_from_entries);
    let admin_command_rule_specs = parse_semicolon_separated_entries(&admin_command_rules);
    let slash_command_policy = TelegramSlashCommandPolicy {
        slash_command_allow_from: slash_command_allow_from_entries,
        session_status_allow_from: parse_optional_comma_separated_entries(
            slash_session_status_allow_from,
        ),
        session_budget_allow_from: parse_optional_comma_separated_entries(
            slash_session_budget_allow_from,
        ),
        session_memory_allow_from: parse_optional_comma_separated_entries(
            slash_session_memory_allow_from,
        ),
        session_feedback_allow_from: parse_optional_comma_separated_entries(
            slash_session_feedback_allow_from,
        ),
        job_status_allow_from: parse_optional_comma_separated_entries(slash_job_allow_from),
        jobs_summary_allow_from: parse_optional_comma_separated_entries(slash_jobs_allow_from),
        background_submit_allow_from: parse_optional_comma_separated_entries(slash_bg_allow_from),
    };
    let control_command_policy = TelegramControlCommandPolicy::new(
        admins,
        control_command_allow_from_entries,
        admin_command_rule_specs,
    )
    .with_slash_command_policy(slash_command_policy);
    if users.is_empty() && groups.is_empty() {
        tracing::warn!(
            "Telegram allowed-users and allowed-groups are empty; all inbound will be rejected. \
             Set --allowed-users '<user_id>' or --allowed-groups '<chat_id>' or '*' to allow."
        );
    }
    match mode {
        TelegramChannelMode::Polling => {
            run_telegram_with_control_command_policy(
                Arc::clone(&agent),
                bot_token,
                users,
                groups,
                control_command_policy.clone(),
            )
            .await
        }
        TelegramChannelMode::Webhook => {
            run_telegram_webhook_with_control_command_policy(
                Arc::clone(&agent),
                bot_token,
                users,
                groups,
                control_command_policy,
                &webhook_bind,
                &webhook_path,
                webhook_secret_token,
                webhook_dedup_config,
            )
            .await
        }
    }
}

fn build_webhook_dedup_config(
    backend_mode: WebhookDedupBackendMode,
    valkey_url: Option<String>,
    ttl_secs: u64,
    key_prefix: String,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<WebhookDedupConfig> {
    let backend = match backend_mode {
        WebhookDedupBackendMode::Memory => WebhookDedupBackend::Memory,
        WebhookDedupBackendMode::Valkey => {
            let url = valkey_url
                .or_else(|| std::env::var("VALKEY_URL").ok())
                .or_else(|| runtime_settings.session.valkey_url.clone())
                .ok_or_else(|| {
                    anyhow::anyhow!(
                        "valkey dedup backend requires valkey url (explicit --valkey-url, VALKEY_URL, or session.valkey_url)"
                    )
                })?;
            if url.trim().is_empty() {
                return Err(anyhow::anyhow!(
                    "valkey dedup backend requires a non-empty URL"
                ));
            }
            WebhookDedupBackend::Redis { url, key_prefix }
        }
    };

    Ok(WebhookDedupConfig { backend, ttl_secs })
}
