use std::sync::Arc;

use tokio::sync::mpsc;

use crate::channels::telegram::TelegramChannel;
use crate::channels::telegram::idempotency::UpdateDeduplicator;
use crate::channels::traits::ChannelMessage;

#[derive(Clone)]
pub(super) struct TelegramWebhookState {
    pub(super) channel: Arc<TelegramChannel>,
    pub(super) tx: mpsc::Sender<ChannelMessage>,
    pub(super) secret_token: Option<String>,
    pub(super) deduplicator: Arc<dyn UpdateDeduplicator>,
}
