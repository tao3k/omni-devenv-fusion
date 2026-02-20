use std::sync::Arc;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::channels::telegram::TelegramControlCommandPolicy;
use crate::channels::traits::{Channel, ChannelMessage};

use super::super::super::channel::TelegramChannel;

pub(super) fn start_polling_listener(
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    control_command_policy: TelegramControlCommandPolicy,
    inbound_queue_capacity: usize,
) -> Result<(
    Arc<TelegramChannel>,
    Arc<dyn Channel>,
    mpsc::Receiver<ChannelMessage>,
    tokio::task::JoinHandle<()>,
)> {
    let channel = Arc::new(
        TelegramChannel::new_with_partition_and_control_command_policy(
            bot_token,
            allowed_users,
            allowed_groups,
            control_command_policy,
            super::super::super::session_partition::TelegramSessionPartition::from_env(),
        )?,
    );
    let channel_for_send: Arc<dyn Channel> = channel.clone();

    let (tx, inbound_rx) = mpsc::channel::<ChannelMessage>(inbound_queue_capacity);
    let listener_channel = Arc::clone(&channel_for_send);
    let listener = tokio::spawn(async move {
        if let Err(error) = listener_channel.listen(tx).await {
            tracing::error!("Telegram listener error: {error}");
        }
    });

    Ok((channel, channel_for_send, inbound_rx, listener))
}
