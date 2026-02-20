use std::sync::Arc;

use anyhow::Result;
use axum::{Router, routing::post};
use tokio::sync::mpsc;

use crate::channels::telegram::idempotency::WebhookDedupConfig;
use crate::channels::telegram::session_partition::TelegramSessionPartition;
use crate::channels::telegram::{TelegramChannel, TelegramControlCommandPolicy};
use crate::channels::traits::ChannelMessage;

use super::super::app::TelegramWebhookApp;
use super::super::handler::telegram_webhook_handler;
use super::super::path::normalize_webhook_path;
use super::super::state::TelegramWebhookState;

pub(super) fn build_telegram_webhook_app_with_partition_and_control_command_policy(
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
    let dedup_config = dedup_config.normalized();
    let deduplicator = dedup_config.build_store()?;
    let channel = Arc::new(
        TelegramChannel::new_with_partition_and_control_command_policy(
            bot_token,
            allowed_users,
            allowed_groups,
            control_command_policy,
            session_partition,
        )?,
    );
    let webhook_state = TelegramWebhookState {
        channel: Arc::clone(&channel),
        tx,
        secret_token,
        deduplicator,
    };

    let path = normalize_webhook_path(webhook_path);
    let app = Router::new()
        .route(&path, post(telegram_webhook_handler))
        .with_state(webhook_state);

    Ok(TelegramWebhookApp {
        app,
        channel,
        path,
        dedup_config,
    })
}
