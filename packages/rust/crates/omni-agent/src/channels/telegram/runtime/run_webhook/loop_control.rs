use std::sync::Arc;
use std::time::Duration;

use tokio::sync::mpsc;

use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::{JobCompletion, JobManager};

use super::super::jobs::{handle_inbound_message, push_background_completion};
use super::server::drain_finished_webhook_server;

pub(super) async fn run_webhook_event_loop(
    inbound_rx: &mut mpsc::Receiver<ChannelMessage>,
    completion_rx: &mut mpsc::Receiver<JobCompletion>,
    channel_for_send: &Arc<dyn Channel>,
    foreground_tx: &mpsc::Sender<ChannelMessage>,
    job_manager: &Arc<JobManager>,
    agent: &Arc<Agent>,
    webhook_server: &mut tokio::task::JoinHandle<std::io::Result<()>>,
) {
    let mut health_tick = tokio::time::interval(Duration::from_secs(1));
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
            _ = health_tick.tick() => {
                if drain_finished_webhook_server(webhook_server).await {
                    break;
                }
            }
        }
    }
}
