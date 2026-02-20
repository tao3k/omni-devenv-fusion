//! Telegram runtime wiring (polling/webhook + foreground/background execution).

mod console;
mod dispatch;
mod jobs;
mod run_polling;
mod run_webhook;
#[cfg(test)]
#[path = "../../../../tests/telegram_runtime/mod.rs"]
mod tests;
mod webhook;

pub use run_polling::{run_telegram, run_telegram_with_control_command_policy};
pub use run_webhook::{run_telegram_webhook, run_telegram_webhook_with_control_command_policy};
pub use webhook::build_telegram_webhook_app_with_partition;
pub use webhook::{
    TelegramWebhookApp, build_telegram_webhook_app,
    build_telegram_webhook_app_with_control_command_policy,
};
