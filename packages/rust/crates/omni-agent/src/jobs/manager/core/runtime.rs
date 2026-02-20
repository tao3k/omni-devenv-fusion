use std::sync::Arc;

use tokio::sync::{Semaphore, mpsc};
use tokio::task::JoinSet;

use crate::jobs::JobHealthState;
use crate::jobs::heartbeat::{HeartbeatProbeState, classify_heartbeat_probe_result};
use crate::jobs::manager::types::{
    JobCompletion, JobCompletionKind, JobState, QueuedJob, truncate_for_status,
};

use super::JobManager;

impl JobManager {
    pub(super) fn spawn_dispatch_loop(
        self: &Arc<Self>,
        mut queue_rx: mpsc::Receiver<QueuedJob>,
        completion_tx: mpsc::Sender<JobCompletion>,
        max_in_flight: usize,
    ) {
        let manager = Arc::clone(self);
        tokio::spawn(async move {
            let semaphore = Arc::new(Semaphore::new(max_in_flight));
            let mut workers = JoinSet::new();

            while let Some(job) = queue_rx.recv().await {
                let permit = match Arc::clone(&semaphore).acquire_owned().await {
                    Ok(permit) => permit,
                    Err(_) => break,
                };
                let worker_manager = Arc::clone(&manager);
                let worker_completion_tx = completion_tx.clone();
                workers.spawn(async move {
                    let _permit = permit;
                    worker_manager.process_job(job, worker_completion_tx).await;
                });

                while let Some(result) = workers.try_join_next() {
                    if let Err(error) = result {
                        tracing::error!("background job worker crashed: {error}");
                    }
                }
            }

            while let Some(result) = workers.join_next().await {
                if let Err(error) = result {
                    tracing::error!("background job worker crashed: {error}");
                }
            }
        });
    }

    pub(super) fn spawn_heartbeat_loop(self: &Arc<Self>) {
        let manager = Arc::clone(self);
        tokio::spawn(async move {
            let mut interval = tokio::time::interval(manager.heartbeat_interval);
            loop {
                interval.tick().await;

                let probe =
                    tokio::time::timeout(manager.heartbeat_probe_timeout, manager.metrics()).await;
                let probe_state = classify_heartbeat_probe_result(&probe);
                if probe_state == HeartbeatProbeState::Timeout {
                    tracing::warn!(
                        "background heartbeat probe timed out after {:?}",
                        manager.heartbeat_probe_timeout
                    );
                    continue;
                }

                let metrics = match probe {
                    Ok(metrics) => metrics,
                    Err(_) => continue,
                };
                match metrics.health_state {
                    JobHealthState::Healthy => {
                        tracing::trace!(
                            "background heartbeat healthy: queued={}, running={}, timed_out={}",
                            metrics.queued,
                            metrics.running,
                            metrics.timed_out
                        );
                    }
                    JobHealthState::QueueStalled => {
                        tracing::warn!(
                            "background queue stalled: oldest_queued_age={}s threshold={}s",
                            metrics.oldest_queued_age_secs.unwrap_or_default(),
                            manager.max_queued_age_secs
                        );
                    }
                    JobHealthState::RunningStalled => {
                        tracing::warn!(
                            "background running stalled: longest_running_age={}s threshold={}s",
                            metrics.longest_running_age_secs.unwrap_or_default(),
                            manager.max_running_age_secs
                        );
                    }
                }
            }
        });
    }

    async fn process_job(
        self: Arc<Self>,
        job: QueuedJob,
        completion_tx: mpsc::Sender<JobCompletion>,
    ) {
        self.mark_running(&job.job_id).await;

        let run_result = tokio::time::timeout(
            self.job_timeout,
            self.runner.run_turn(&job.session_id, &job.prompt),
        )
        .await;

        match run_result {
            Ok(Ok(output)) => {
                let preview = truncate_for_status(&output, 400);
                self.mark_terminal(&job.job_id, JobState::Succeeded, Some(preview), None)
                    .await;
                let _ = completion_tx
                    .send(JobCompletion {
                        job_id: job.job_id,
                        recipient: job.recipient,
                        kind: JobCompletionKind::Succeeded { output },
                    })
                    .await;
            }
            Ok(Err(error)) => {
                let err = error.to_string();
                self.mark_terminal(&job.job_id, JobState::Failed, None, Some(err.clone()))
                    .await;
                let _ = completion_tx
                    .send(JobCompletion {
                        job_id: job.job_id,
                        recipient: job.recipient,
                        kind: JobCompletionKind::Failed { error: err },
                    })
                    .await;
            }
            Err(_) => {
                let timeout_secs = self.job_timeout.as_secs();
                let err = format!("timed out after {timeout_secs}s");
                self.mark_terminal(&job.job_id, JobState::TimedOut, None, Some(err))
                    .await;
                let _ = completion_tx
                    .send(JobCompletion {
                        job_id: job.job_id,
                        recipient: job.recipient,
                        kind: JobCompletionKind::TimedOut { timeout_secs },
                    })
                    .await;
            }
        }
    }
}
