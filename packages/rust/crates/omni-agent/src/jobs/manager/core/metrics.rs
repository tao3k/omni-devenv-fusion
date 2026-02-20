use std::time::Instant;

use crate::jobs::JobHealthState;
use crate::jobs::heartbeat::classify_job_health;
use crate::jobs::manager::types::{
    JobMetricsSnapshot, JobState, JobStatusSnapshot, elapsed_secs_from, truncate_for_status,
};

use super::JobManager;

impl JobManager {
    /// Query one job.
    pub async fn get_status(&self, job_id: &str) -> Option<JobStatusSnapshot> {
        let now = Instant::now();
        let records = self.records.read().await;
        let record = records.get(job_id)?.clone();

        Some(JobStatusSnapshot {
            job_id: job_id.to_string(),
            session_id: record.session_id,
            state: record.state,
            prompt_preview: truncate_for_status(&record.prompt, 140),
            submitted_age_secs: elapsed_secs_from(now, record.submitted_at),
            running_age_secs: record.started_at.map(|t| elapsed_secs_from(now, t)),
            finished_age_secs: record.finished_at.map(|t| elapsed_secs_from(now, t)),
            output_preview: record.output_preview,
            error: record.error,
        })
    }

    /// Aggregate metrics for `/jobs` and heartbeat.
    pub async fn metrics(&self) -> JobMetricsSnapshot {
        let now = Instant::now();
        let records = self.records.read().await;

        let mut queued = 0usize;
        let mut running = 0usize;
        let mut succeeded = 0usize;
        let mut failed = 0usize;
        let mut timed_out = 0usize;
        let mut oldest_queued = None::<u64>;
        let mut longest_running = None::<u64>;

        for record in records.values() {
            match record.state {
                JobState::Queued => {
                    queued += 1;
                    let age = elapsed_secs_from(now, record.submitted_at);
                    oldest_queued = Some(oldest_queued.map_or(age, |v| v.max(age)));
                }
                JobState::Running => {
                    running += 1;
                    if let Some(started_at) = record.started_at {
                        let age = elapsed_secs_from(now, started_at);
                        longest_running = Some(longest_running.map_or(age, |v| v.max(age)));
                    }
                }
                JobState::Succeeded => {
                    succeeded += 1;
                }
                JobState::Failed => {
                    failed += 1;
                }
                JobState::TimedOut => {
                    timed_out += 1;
                }
            }
        }

        let mut snapshot = JobMetricsSnapshot {
            total_jobs: records.len(),
            queued,
            running,
            succeeded,
            failed,
            timed_out,
            oldest_queued_age_secs: oldest_queued,
            longest_running_age_secs: longest_running,
            health_state: JobHealthState::Healthy,
        };
        snapshot.health_state = classify_job_health(
            &snapshot,
            self.max_queued_age_secs,
            self.max_running_age_secs,
        );
        snapshot
    }
}
