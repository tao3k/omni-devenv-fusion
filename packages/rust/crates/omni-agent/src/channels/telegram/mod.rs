//! Telegram channel integration.

mod channel;
pub(crate) mod commands;
mod idempotency;
mod runtime;
mod runtime_config;
mod session_gate;
mod session_partition;

pub use channel::{
    TELEGRAM_MAX_MESSAGE_LENGTH, TelegramChannel, TelegramControlCommandPolicy,
    TelegramSlashCommandPolicy, chunk_marker_reserve_chars, decorate_chunk_for_telegram,
    markdown_to_telegram_html, markdown_to_telegram_markdown_v2, split_message_for_telegram,
};
pub use idempotency::{DEFAULT_REDIS_KEY_PREFIX, WebhookDedupBackend, WebhookDedupConfig};
pub use runtime::{
    TelegramWebhookApp, build_telegram_webhook_app,
    build_telegram_webhook_app_with_control_command_policy,
    build_telegram_webhook_app_with_partition, run_telegram, run_telegram_webhook,
    run_telegram_webhook_with_control_command_policy, run_telegram_with_control_command_policy,
};
pub use runtime_config::TelegramRuntimeConfig;
pub use session_gate::SessionGate;
pub use session_partition::TelegramSessionPartition;
