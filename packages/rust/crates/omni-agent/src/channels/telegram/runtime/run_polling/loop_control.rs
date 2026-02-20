use std::sync::Arc;

use tokio::sync::mpsc;

use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::{JobCompletion, JobManager};

use super::super::jobs::{handle_inbound_message, push_background_completion};

pub(super) async fn run_polling_event_loop(
    inbound_rx: &mut mpsc::Receiver<ChannelMessage>,
    completion_rx: &mut mpsc::Receiver<JobCompletion>,
    channel_for_send: &Arc<dyn Channel>,
    foreground_tx: &mpsc::Sender<ChannelMessage>,
    job_manager: &Arc<JobManager>,
    agent: &Arc<Agent>,
) {
    loop {
        tokio::select! {
            maybe_msg = inbound_rx.recv() => {
                let Some(msg) = maybe_msg else {
                    break;
                };
                if !handle_inbound_message(msg, channel_for_send, foreground_tx, job_manager, agent).await {
                    break;
                }
            }
            maybe_completion = completion_rx.recv() => {
                let Some(completion) = maybe_completion else {
                    continue;
                };
                push_background_completion(channel_for_send, completion).await;
            }
            _ = tokio::signal::ctrl_c() => {
                println!("Shutting down...");
                break;
            }
        }
    }
}
