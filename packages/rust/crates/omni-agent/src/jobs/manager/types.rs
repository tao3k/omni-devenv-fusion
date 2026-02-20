//! Shared types and helpers for background job management.

use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use async_trait::async_trait;

use crate::jobs::JobHealthState;

/// Async turn runner abstraction so background jobs can run via `Agent` or test doubles.
#[async_trait]
pub trait TurnRunner: Send + Sync {
    /// Run a single turn and return the final text output.
    async fn run_turn(&self, session_id: &str, user_message: &str) -> Result<String>;
}

#[async_trait]
impl TurnRunner for crate::agent::Agent {
    async fn run_turn(&self, session_id: &str, user_message: &str) -> Result<String> {
        crate::agent::Agent::run_turn(self, session_id, user_message).await
    }
}

/// Background job state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobState {
    /// Accepted but not started.
    Queued,
    /// Running in worker pool.
    Running,
    /// Completed successfully.
    Succeeded,
    /// Completed with execution error.
    Failed,
    /// Timed out.
    TimedOut,
}

/// Snapshot for one job status query.
#[derive(Debug, Clone)]
pub struct JobStatusSnapshot {
    /// Unique job id.
    pub job_id: String,
    /// Effective isolated session id used by the job turn.
    pub session_id: String,
    /// Current state.
    pub state: JobState,
    /// Prompt preview for quick inspection.
    pub prompt_preview: String,
    /// Seconds since submission.
    pub submitted_age_secs: u64,
    /// Seconds since start if running/finished.
    pub running_age_secs: Option<u64>,
    /// Seconds since finish if completed.
    pub finished_age_secs: Option<u64>,
    /// Output preview for succeeded jobs.
    pub output_preview: Option<String>,
    /// Error text for failed/timed-out jobs.
    pub error: Option<String>,
}

/// Aggregate queue/worker metrics.
#[derive(Debug, Clone)]
pub struct JobMetricsSnapshot {
    /// Total jobs currently tracked in memory.
    pub total_jobs: usize,
    /// Count by state.
    pub queued: usize,
    /// Count by state.
    pub running: usize,
    /// Count by state.
    pub succeeded: usize,
    /// Count by state.
    pub failed: usize,
    /// Count by state.
    pub timed_out: usize,
    /// Age of oldest queued job.
    pub oldest_queued_age_secs: Option<u64>,
    /// Age of longest-running job.
    pub longest_running_age_secs: Option<u64>,
    /// Classified health state from age thresholds.
    pub health_state: JobHealthState,
}

/// Completion result for channel push notification.
#[derive(Debug, Clone)]
pub enum JobCompletionKind {
    /// Completed successfully.
    Succeeded { output: String },
    /// Failed with execution error.
    Failed { error: String },
    /// Timed out.
    TimedOut { timeout_secs: u64 },
}

/// Completion event sent from background workers.
#[derive(Debug, Clone)]
pub struct JobCompletion {
    /// Unique job id.
    pub job_id: String,
    /// Recipient id (e.g. Telegram chat id).
    pub recipient: String,
    /// Completion payload.
    pub kind: JobCompletionKind,
}

/// Config for background queue and watchdog.
#[derive(Debug, Clone)]
pub struct JobManagerConfig {
    /// Bounded queue size for pending jobs.
    pub queue_capacity: usize,
    /// Maximum in-flight workers.
    pub max_in_flight: usize,
    /// Per-job timeout in seconds.
    pub job_timeout_secs: u64,
    /// Heartbeat tick interval in seconds.
    pub heartbeat_interval_secs: u64,
    /// Heartbeat probe timeout in seconds.
    pub heartbeat_probe_timeout_secs: u64,
    /// Queue age threshold for unhealthy state.
    pub max_queued_age_secs: u64,
    /// Running age threshold for unhealthy state.
    pub max_running_age_secs: u64,
}

impl Default for JobManagerConfig {
    fn default() -> Self {
        Self {
            queue_capacity: 256,
            max_in_flight: 8,
            job_timeout_secs: 900,
            heartbeat_interval_secs: 10,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 900,
        }
    }
}

#[derive(Debug, Clone)]
pub(super) struct JobRecord {
    pub(super) session_id: String,
    pub(super) prompt: String,
    pub(super) state: JobState,
    pub(super) submitted_at: Instant,
    pub(super) started_at: Option<Instant>,
    pub(super) finished_at: Option<Instant>,
    pub(super) output_preview: Option<String>,
    pub(super) error: Option<String>,
}

#[derive(Debug, Clone)]
pub(super) struct QueuedJob {
    pub(super) job_id: String,
    pub(super) recipient: String,
    pub(super) session_id: String,
    pub(super) prompt: String,
}

pub(super) fn epoch_millis() -> u128 {
    match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(duration) => duration.as_millis(),
        Err(_) => 0,
    }
}

pub(super) fn elapsed_secs_from(now: Instant, start: Instant) -> u64 {
    now.checked_duration_since(start)
        .map_or(0, |duration| duration.as_secs())
}

pub(super) fn truncate_for_status(text: &str, max_chars: usize) -> String {
    let mut iter = text.chars();
    let truncated: String = iter.by_ref().take(max_chars).collect();
    if iter.next().is_some() {
        format!("{truncated}...")
    } else {
        truncated
    }
}
