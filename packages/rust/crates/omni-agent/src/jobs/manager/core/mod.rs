//! Core runtime for background job queue execution.

mod metrics;
mod runtime;

use std::collections::HashMap;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant};

use anyhow::{Result, anyhow};
use tokio::sync::{RwLock, mpsc};

use crate::jobs::manager::types::{
    JobManagerConfig, JobRecord, JobState, QueuedJob, TurnRunner, epoch_millis,
};

/// Manages background jobs with a bounded queue + concurrent workers.
pub struct JobManager {
    runner: Arc<dyn TurnRunner>,
    queue_tx: mpsc::Sender<QueuedJob>,
    records: Arc<RwLock<HashMap<String, JobRecord>>>,
    next_job_seq: AtomicU64,
    job_timeout: Duration,
    heartbeat_interval: Duration,
    heartbeat_probe_timeout: Duration,
    max_queued_age_secs: u64,
    max_running_age_secs: u64,
}

impl JobManager {
    /// Start the manager and return `(manager, completion_receiver)`.
    pub fn start(
        runner: Arc<dyn TurnRunner>,
        mut config: JobManagerConfig,
    ) -> (
        Arc<Self>,
        tokio::sync::mpsc::Receiver<crate::jobs::manager::types::JobCompletion>,
    ) {
        config.queue_capacity = config.queue_capacity.max(1);
        config.max_in_flight = config.max_in_flight.max(1);
        config.job_timeout_secs = config.job_timeout_secs.max(1);
        config.heartbeat_interval_secs = config.heartbeat_interval_secs.max(1);
        config.heartbeat_probe_timeout_secs = config.heartbeat_probe_timeout_secs.max(1);
        config.max_queued_age_secs = config.max_queued_age_secs.max(1);
        config.max_running_age_secs = config.max_running_age_secs.max(1);

        let (queue_tx, queue_rx) = mpsc::channel::<QueuedJob>(config.queue_capacity);
        let (completion_tx, completion_rx) = mpsc::channel::<
            crate::jobs::manager::types::JobCompletion,
        >(config.queue_capacity.saturating_mul(2));

        let manager = Arc::new(Self {
            runner,
            queue_tx,
            records: Arc::new(RwLock::new(HashMap::new())),
            next_job_seq: AtomicU64::new(0),
            job_timeout: Duration::from_secs(config.job_timeout_secs),
            heartbeat_interval: Duration::from_secs(config.heartbeat_interval_secs),
            heartbeat_probe_timeout: Duration::from_secs(config.heartbeat_probe_timeout_secs),
            max_queued_age_secs: config.max_queued_age_secs,
            max_running_age_secs: config.max_running_age_secs,
        });

        manager.spawn_dispatch_loop(queue_rx, completion_tx, config.max_in_flight);
        manager.spawn_heartbeat_loop();

        (manager, completion_rx)
    }

    /// Submit one background job. Returns generated job id.
    pub async fn submit(
        &self,
        session_prefix: &str,
        recipient: String,
        prompt: String,
    ) -> Result<String> {
        let job_id = self.next_job_id();
        let session_id = format!("{session_prefix}:job:{job_id}");
        let now = Instant::now();

        let record = JobRecord {
            session_id: session_id.clone(),
            prompt: prompt.clone(),
            state: JobState::Queued,
            submitted_at: now,
            started_at: None,
            finished_at: None,
            output_preview: None,
            error: None,
        };
        self.records.write().await.insert(job_id.clone(), record);

        let queued = QueuedJob {
            job_id: job_id.clone(),
            recipient,
            session_id,
            prompt,
        };

        if self.queue_tx.send(queued).await.is_err() {
            let error = "background queue is closed".to_string();
            self.mark_terminal(&job_id, JobState::Failed, None, Some(error.clone()))
                .await;
            return Err(anyhow!(error));
        }

        Ok(job_id)
    }

    async fn mark_running(&self, job_id: &str) {
        if let Some(record) = self.records.write().await.get_mut(job_id) {
            record.state = JobState::Running;
            record.started_at = Some(Instant::now());
            record.error = None;
        }
    }

    async fn mark_terminal(
        &self,
        job_id: &str,
        state: JobState,
        output_preview: Option<String>,
        error: Option<String>,
    ) {
        if let Some(record) = self.records.write().await.get_mut(job_id) {
            record.state = state;
            record.finished_at = Some(Instant::now());
            record.output_preview = output_preview;
            record.error = error;
        }
    }

    fn next_job_id(&self) -> String {
        let seq = self.next_job_seq.fetch_add(1, Ordering::Relaxed);
        format!("job-{}-{seq}", epoch_millis())
    }
}
