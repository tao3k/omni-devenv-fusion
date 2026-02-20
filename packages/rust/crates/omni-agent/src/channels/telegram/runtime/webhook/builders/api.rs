use anyhow::Result;
use tokio::sync::mpsc;

use super::super::app::TelegramWebhookApp;
use super::core;
use crate::channels::telegram::TelegramControlCommandPolicy;
use crate::channels::telegram::idempotency::WebhookDedupConfig;
use crate::channels::telegram::session_partition::TelegramSessionPartition;
use crate::channels::traits::ChannelMessage;

/// Build a Telegram webhook app with configured dedup backend.
pub fn build_telegram_webhook_app(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
    tx: mpsc::Sender<ChannelMessage>,
) -> Result<TelegramWebhookApp> {
    let admin_users = Vec::new();
    build_telegram_webhook_app_with_admin_users(
        bot_token,
        allowed_users,
        allowed_groups,
        admin_users,
        webhook_path,
        secret_token,
        dedup_config,
        tx,
    )
}

/// Build a Telegram webhook app with explicit admin user allowlist.
pub fn build_telegram_webhook_app_with_admin_users(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    admin_users: Vec<String>,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
    tx: mpsc::Sender<ChannelMessage>,
) -> Result<TelegramWebhookApp> {
    build_telegram_webhook_app_with_admin_users_and_command_rules(
        bot_token,
        allowed_users,
        allowed_groups,
        admin_users,
        None,
        Vec::new(),
        webhook_path,
        secret_token,
        dedup_config,
        tx,
    )
}

/// Build a Telegram webhook app with explicit admin user allowlist and per-command admin rules.
pub fn build_telegram_webhook_app_with_admin_users_and_command_rules(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    admin_users: Vec<String>,
    control_command_allow_from: Option<Vec<String>>,
    admin_command_rule_specs: Vec<String>,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
    tx: mpsc::Sender<ChannelMessage>,
) -> Result<TelegramWebhookApp> {
    build_telegram_webhook_app_with_control_command_policy(
        bot_token,
        allowed_users,
        allowed_groups,
        TelegramControlCommandPolicy::new(
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
        ),
        webhook_path,
        secret_token,
        dedup_config,
        tx,
    )
}

/// Build a Telegram webhook app with structured control-command policy.
pub fn build_telegram_webhook_app_with_control_command_policy(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    control_command_policy: TelegramControlCommandPolicy,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
    tx: mpsc::Sender<ChannelMessage>,
) -> Result<TelegramWebhookApp> {
    build_telegram_webhook_app_with_partition_and_control_command_policy(
        bot_token,
        allowed_users,
        allowed_groups,
        control_command_policy,
        webhook_path,
        secret_token,
        dedup_config,
        TelegramSessionPartition::from_env(),
        tx,
    )
}

/// Build a Telegram webhook app with explicit session partition strategy.
#[doc(hidden)]
pub fn build_telegram_webhook_app_with_partition(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    admin_users: Vec<String>,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
    session_partition: TelegramSessionPartition,
    tx: mpsc::Sender<ChannelMessage>,
) -> Result<TelegramWebhookApp> {
    build_telegram_webhook_app_with_partition_and_control_command_policy(
        bot_token,
        allowed_users,
        allowed_groups,
        TelegramControlCommandPolicy::new(admin_users, None, Vec::new()),
        webhook_path,
        secret_token,
        dedup_config,
        session_partition,
        tx,
    )
}

/// Build a Telegram webhook app with explicit session partition strategy and per-command admin
/// authorization rules.
#[doc(hidden)]
pub fn build_telegram_webhook_app_with_partition_and_control_command_policy(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    control_command_policy: TelegramControlCommandPolicy,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
    session_partition: TelegramSessionPartition,
    tx: mpsc::Sender<ChannelMessage>,
) -> Result<TelegramWebhookApp> {
    core::build_telegram_webhook_app_with_partition_and_control_command_policy(
        bot_token,
        allowed_users,
        allowed_groups,
        control_command_policy,
        webhook_path,
        secret_token,
        dedup_config,
        session_partition,
        tx,
    )
}
