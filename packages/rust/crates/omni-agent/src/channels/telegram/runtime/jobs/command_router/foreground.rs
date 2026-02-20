use tokio::sync::mpsc;

use crate::channels::traits::ChannelMessage;

pub(super) async fn forward(
    msg: ChannelMessage,
    foreground_tx: &mpsc::Sender<ChannelMessage>,
) -> bool {
    if foreground_tx.send(msg).await.is_err() {
        tracing::error!("Foreground dispatcher is unavailable");
        return false;
    }
    true
}
