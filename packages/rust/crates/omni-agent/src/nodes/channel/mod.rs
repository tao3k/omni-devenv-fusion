mod common;
mod discord;
mod telegram;

use std::path::PathBuf;

use omni_agent::RuntimeSettings;

use crate::cli::{ChannelProvider, TelegramChannelMode, WebhookDedupBackendMode};

pub(crate) struct ChannelCommandRequest {
    pub(crate) provider: ChannelProvider,
    pub(crate) bot_token: Option<String>,
    pub(crate) allowed_users: Option<String>,
    pub(crate) allowed_groups: Option<String>,
    pub(crate) allowed_guilds: Option<String>,
    pub(crate) admin_users: Option<String>,
    pub(crate) control_command_allow_from: Option<String>,
    pub(crate) admin_command_rules: Option<String>,
    pub(crate) slash_command_allow_from: Option<String>,
    pub(crate) slash_session_status_allow_from: Option<String>,
    pub(crate) slash_session_budget_allow_from: Option<String>,
    pub(crate) slash_session_memory_allow_from: Option<String>,
    pub(crate) slash_session_feedback_allow_from: Option<String>,
    pub(crate) slash_job_allow_from: Option<String>,
    pub(crate) slash_jobs_allow_from: Option<String>,
    pub(crate) slash_bg_allow_from: Option<String>,
    pub(crate) mcp_config: PathBuf,
    pub(crate) mode: Option<TelegramChannelMode>,
    pub(crate) webhook_bind: Option<String>,
    pub(crate) webhook_path: Option<String>,
    pub(crate) webhook_secret_token: Option<String>,
    pub(crate) ingress_bind: Option<String>,
    pub(crate) ingress_path: Option<String>,
    pub(crate) ingress_secret_token: Option<String>,
    pub(crate) session_partition: Option<String>,
    pub(crate) inbound_queue_capacity: Option<usize>,
    pub(crate) turn_timeout_secs: Option<u64>,
    pub(crate) webhook_dedup_backend: Option<WebhookDedupBackendMode>,
    pub(crate) valkey_url: Option<String>,
    pub(crate) webhook_dedup_ttl_secs: Option<u64>,
    pub(crate) webhook_dedup_key_prefix: Option<String>,
}

pub(crate) async fn run_channel_command(
    req: ChannelCommandRequest,
    runtime_settings: &RuntimeSettings,
) -> anyhow::Result<()> {
    match req.provider {
        ChannelProvider::Telegram => {
            telegram::run_telegram_channel_command(req, runtime_settings).await
        }
        ChannelProvider::Discord => {
            discord::run_discord_channel_command(req, runtime_settings).await
        }
    }
}
