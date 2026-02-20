use std::sync::Arc;

use axum::Router;

use crate::channels::telegram::TelegramChannel;
use crate::channels::telegram::idempotency::WebhookDedupConfig;

/// Built webhook components for Telegram handler testing and runtime wiring.
pub struct TelegramWebhookApp {
    /// Axum router that serves Telegram webhook endpoint.
    pub app: Router,
    /// Telegram channel instance used by this webhook app.
    pub channel: Arc<TelegramChannel>,
    /// Normalized webhook route path.
    pub path: String,
    /// Normalized dedup config actually used by this app.
    pub dedup_config: WebhookDedupConfig,
}
