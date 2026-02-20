use std::sync::Arc;

use tokio::sync::mpsc;

use super::background;
use super::foreground;
use super::session;
use crate::agent::Agent;
use crate::channels::managed_runtime::turn::build_session_id;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::JobManager;

pub(in crate::channels::telegram::runtime::jobs) async fn handle_inbound_message(
    msg: ChannelMessage,
    channel: &Arc<dyn Channel>,
    foreground_tx: &mpsc::Sender<ChannelMessage>,
    job_manager: &Arc<JobManager>,
    agent: &Arc<Agent>,
) -> bool {
    let session_id = build_session_id(&msg.channel, &msg.session_key);

    if session::try_handle(&msg, channel, agent, &session_id).await {
        return true;
    }
    if background::try_handle(&msg, channel, job_manager, &session_id).await {
        return true;
    }

    foreground::forward(msg, foreground_tx).await
}
