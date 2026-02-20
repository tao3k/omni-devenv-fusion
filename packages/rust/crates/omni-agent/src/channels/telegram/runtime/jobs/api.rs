use std::sync::Arc;

use tokio::sync::mpsc;

use super::background_completion;
use super::command_router;
use super::observability;
use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::{JobCompletion, JobManager};

#[allow(dead_code)]
pub(in crate::channels::telegram::runtime) fn log_preview(s: &str) -> String {
    observability::log_preview(s)
}

pub(in crate::channels::telegram::runtime) async fn handle_inbound_message(
    msg: ChannelMessage,
    channel: &Arc<dyn Channel>,
    foreground_tx: &mpsc::Sender<ChannelMessage>,
    job_manager: &Arc<JobManager>,
    agent: &Arc<Agent>,
) -> bool {
    command_router::handle_inbound_message(msg, channel, foreground_tx, job_manager, agent).await
}

pub(in crate::channels::telegram::runtime) async fn push_background_completion(
    channel: &Arc<dyn Channel>,
    completion: JobCompletion,
) {
    background_completion::push_background_completion(channel, completion).await;
}
