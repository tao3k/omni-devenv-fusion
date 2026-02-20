use std::sync::Arc;

use omni_agent::{
    DiscordControlCommandPolicy, DiscordRuntimeConfig, DiscordSessionPartition,
    DiscordSlashCommandPolicy, RuntimeSettings, run_discord_ingress,
};

use crate::agent_builder::build_agent;
use crate::resolve::{
    resolve_optional_string, resolve_positive_u64, resolve_positive_usize, resolve_string,
};

use super::ChannelCommandRequest;
use super::common::{
    log_control_command_allow_override, log_slash_command_allow_override, non_empty_string,
    parse_comma_separated_entries, parse_optional_comma_separated_entries,
    parse_semicolon_separated_entries,
};

const DISCORD_DEFAULT_INGRESS_BIND: &str = "0.0.0.0:8082";
const DISCORD_DEFAULT_INGRESS_PATH: &str = "/discord/ingress";
const DISCORD_DEFAULT_INBOUND_QUEUE_CAPACITY: usize = 512;
const DISCORD_DEFAULT_TURN_TIMEOUT_SECS: u64 = 120;

pub(super) async fn run_discord_channel_command(
    req: ChannelCommandRequest,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let ChannelCommandRequest {
        bot_token,
        allowed_users,
        allowed_guilds,
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
        ingress_bind,
        ingress_path,
        ingress_secret_token,
        session_partition,
        inbound_queue_capacity,
        turn_timeout_secs,
        ..
    } = req;

    let token = bot_token
        .or_else(|| std::env::var("DISCORD_BOT_TOKEN").ok())
        .ok_or_else(|| anyhow::anyhow!("--bot-token or DISCORD_BOT_TOKEN required"))?;
    let allowed_users = resolve_string(
        allowed_users,
        "OMNI_AGENT_DISCORD_ALLOWED_USERS",
        runtime_settings.discord.allowed_users.as_deref(),
        "",
    );
    let allowed_guilds = resolve_string(
        allowed_guilds,
        "OMNI_AGENT_DISCORD_ALLOWED_GUILDS",
        runtime_settings.discord.allowed_guilds.as_deref(),
        "",
    );
    let admin_users = resolve_string(
        admin_users,
        "OMNI_AGENT_DISCORD_ADMIN_USERS",
        runtime_settings.discord.admin_users.as_deref(),
        &allowed_users,
    );
    let control_command_allow_from = resolve_optional_string(
        control_command_allow_from,
        "OMNI_AGENT_DISCORD_CONTROL_COMMAND_ALLOW_FROM",
        runtime_settings
            .discord
            .control_command_allow_from
            .as_deref(),
    );
    let admin_command_rules = resolve_string(
        admin_command_rules,
        "OMNI_AGENT_DISCORD_ADMIN_COMMAND_RULES",
        runtime_settings.discord.admin_command_rules.as_deref(),
        "",
    );
    let slash_command_allow_from = resolve_optional_string(
        slash_command_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_COMMAND_ALLOW_FROM",
        runtime_settings.discord.slash_command_allow_from.as_deref(),
    );
    let slash_session_status_allow_from = resolve_optional_string(
        slash_session_status_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_SESSION_STATUS_ALLOW_FROM",
        runtime_settings
            .discord
            .slash_session_status_allow_from
            .as_deref(),
    );
    let slash_session_budget_allow_from = resolve_optional_string(
        slash_session_budget_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_SESSION_BUDGET_ALLOW_FROM",
        runtime_settings
            .discord
            .slash_session_budget_allow_from
            .as_deref(),
    );
    let slash_session_memory_allow_from = resolve_optional_string(
        slash_session_memory_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_SESSION_MEMORY_ALLOW_FROM",
        runtime_settings
            .discord
            .slash_session_memory_allow_from
            .as_deref(),
    );
    let slash_session_feedback_allow_from = resolve_optional_string(
        slash_session_feedback_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_SESSION_FEEDBACK_ALLOW_FROM",
        runtime_settings
            .discord
            .slash_session_feedback_allow_from
            .as_deref(),
    );
    let slash_job_allow_from = resolve_optional_string(
        slash_job_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_JOB_ALLOW_FROM",
        runtime_settings.discord.slash_job_allow_from.as_deref(),
    );
    let slash_jobs_allow_from = resolve_optional_string(
        slash_jobs_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_JOBS_ALLOW_FROM",
        runtime_settings.discord.slash_jobs_allow_from.as_deref(),
    );
    let slash_bg_allow_from = resolve_optional_string(
        slash_bg_allow_from,
        "OMNI_AGENT_DISCORD_SLASH_BG_ALLOW_FROM",
        runtime_settings.discord.slash_bg_allow_from.as_deref(),
    );
    let ingress_bind = resolve_string(
        ingress_bind,
        "OMNI_AGENT_DISCORD_INGRESS_BIND",
        runtime_settings.discord.ingress_bind.as_deref(),
        DISCORD_DEFAULT_INGRESS_BIND,
    );
    let ingress_path = resolve_string(
        ingress_path,
        "OMNI_AGENT_DISCORD_INGRESS_PATH",
        runtime_settings.discord.ingress_path.as_deref(),
        DISCORD_DEFAULT_INGRESS_PATH,
    );
    let ingress_secret_token = resolve_optional_string(
        ingress_secret_token,
        "OMNI_AGENT_DISCORD_INGRESS_SECRET_TOKEN",
        runtime_settings.discord.ingress_secret_token.as_deref(),
    )
    .and_then(non_empty_string);
    let raw_session_partition = resolve_string(
        session_partition,
        "OMNI_AGENT_DISCORD_SESSION_PARTITION",
        runtime_settings.discord.session_partition.as_deref(),
        "guild_channel_user",
    );
    let session_partition = raw_session_partition
        .parse::<DiscordSessionPartition>()
        .map_err(|_| {
            anyhow::anyhow!("invalid discord session partition mode: {raw_session_partition}")
        })?;
    let inbound_queue_capacity = resolve_positive_usize(
        inbound_queue_capacity,
        "OMNI_AGENT_DISCORD_INBOUND_QUEUE_CAPACITY",
        runtime_settings.discord.inbound_queue_capacity,
        DISCORD_DEFAULT_INBOUND_QUEUE_CAPACITY,
    );
    let turn_timeout_secs = resolve_positive_u64(
        turn_timeout_secs,
        "OMNI_AGENT_DISCORD_TURN_TIMEOUT_SECS",
        runtime_settings.discord.turn_timeout_secs,
        DISCORD_DEFAULT_TURN_TIMEOUT_SECS,
    );

    run_discord_channel_mode(
        token,
        allowed_users,
        allowed_guilds,
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
        ingress_bind,
        ingress_path,
        ingress_secret_token,
        session_partition,
        inbound_queue_capacity,
        turn_timeout_secs,
        runtime_settings,
    )
    .await
}

async fn run_discord_channel_mode(
    bot_token: String,
    allowed_users: String,
    allowed_guilds: String,
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
    ingress_bind: String,
    ingress_path: String,
    ingress_secret_token: Option<String>,
    session_partition: DiscordSessionPartition,
    inbound_queue_capacity: usize,
    turn_timeout_secs: u64,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    let agent = Arc::new(build_agent(&mcp_config_path, runtime_settings).await?);
    let users = parse_comma_separated_entries(&allowed_users);
    let guilds = parse_comma_separated_entries(&allowed_guilds);
    let admins = parse_comma_separated_entries(&admin_users);
    let control_command_allow_from_entries =
        parse_optional_comma_separated_entries(control_command_allow_from);
    log_control_command_allow_override("discord", &control_command_allow_from_entries);
    let slash_command_allow_from_entries =
        parse_optional_comma_separated_entries(slash_command_allow_from);
    log_slash_command_allow_override("discord", &slash_command_allow_from_entries);
    let admin_command_rule_specs = parse_semicolon_separated_entries(&admin_command_rules);
    let slash_command_policy = DiscordSlashCommandPolicy {
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
    let control_command_policy = DiscordControlCommandPolicy::new(
        admins,
        control_command_allow_from_entries,
        admin_command_rule_specs,
    )
    .with_slash_command_policy(slash_command_policy);

    if users.is_empty() && guilds.is_empty() {
        tracing::warn!(
            "Discord allowed-users and allowed-guilds are empty; all inbound will be rejected. \
             Set --allowed-users '<user_id>' or --allowed-guilds '<guild_id>' or '*' to allow."
        );
    }

    run_discord_ingress(
        Arc::clone(&agent),
        bot_token,
        users,
        guilds,
        control_command_policy,
        &ingress_bind,
        &ingress_path,
        ingress_secret_token,
        DiscordRuntimeConfig {
            session_partition,
            inbound_queue_capacity,
            turn_timeout_secs,
        },
    )
    .await
}
