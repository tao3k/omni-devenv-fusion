use std::sync::Arc;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::agent::Agent;
use crate::channels::telegram::runtime_config::TelegramRuntimeConfig;
use crate::channels::telegram::session_gate::SessionGate;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::{JobCompletion, JobManager, JobManagerConfig, TurnRunner};

use super::worker_pool::spawn_foreground_dispatcher;

pub(in crate::channels::telegram::runtime) fn start_telegram_runtime(
    agent: Arc<Agent>,
    channel: Arc<dyn Channel>,
    runtime_config: TelegramRuntimeConfig,
) -> Result<(
    String,
    mpsc::Sender<ChannelMessage>,
    tokio::task::JoinHandle<()>,
    Arc<JobManager>,
    mpsc::Receiver<JobCompletion>,
)> {
    let (foreground_tx, foreground_rx) =
        mpsc::channel::<ChannelMessage>(runtime_config.foreground_queue_capacity);
    let session_gate = SessionGate::from_env()?;
    let session_gate_backend = session_gate.backend_name().to_string();
    tracing::info!(
        backend = %session_gate_backend,
        "telegram foreground session gate ready"
    );
    let foreground_dispatcher = spawn_foreground_dispatcher(
        Arc::clone(&agent),
        Arc::clone(&channel),
        foreground_rx,
        runtime_config,
        session_gate,
    );

    let runner: Arc<dyn TurnRunner> = agent;
    let (job_manager, completion_rx) = JobManager::start(runner, JobManagerConfig::default());
    Ok((
        session_gate_backend,
        foreground_tx,
        foreground_dispatcher,
        job_manager,
        completion_rx,
    ))
}
