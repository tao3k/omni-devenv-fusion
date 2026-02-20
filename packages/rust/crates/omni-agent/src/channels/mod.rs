//! Chat channels (Telegram, etc.) — bridge messaging platforms to the agent.

mod control_command_authorization;
mod control_command_rule_specs;
mod discord;
pub(crate) mod managed_commands;
mod managed_runtime;
pub(crate) mod telegram;
mod traits;

pub use discord::{
    DISCORD_MAX_MESSAGE_LENGTH, DiscordChannel, DiscordControlCommandPolicy, DiscordIngressApp,
    DiscordRuntimeConfig, DiscordSessionPartition, DiscordSlashCommandPolicy,
    build_discord_ingress_app, build_discord_ingress_app_with_control_command_policy,
    build_discord_ingress_app_with_partition_and_control_command_policy, run_discord_ingress,
    split_message_for_discord,
};
pub use telegram::{
    DEFAULT_REDIS_KEY_PREFIX, SessionGate, TELEGRAM_MAX_MESSAGE_LENGTH, TelegramChannel,
    TelegramControlCommandPolicy, TelegramRuntimeConfig, TelegramSessionPartition,
    TelegramSlashCommandPolicy, TelegramWebhookApp, WebhookDedupBackend, WebhookDedupConfig,
    build_telegram_webhook_app, build_telegram_webhook_app_with_control_command_policy,
    build_telegram_webhook_app_with_partition, chunk_marker_reserve_chars,
    decorate_chunk_for_telegram, markdown_to_telegram_html, markdown_to_telegram_markdown_v2,
    run_telegram, run_telegram_webhook, run_telegram_webhook_with_control_command_policy,
    run_telegram_with_control_command_policy, split_message_for_telegram,
};
pub use traits::{Channel, ChannelMessage, RecipientCommandAdminUsersMutation};
