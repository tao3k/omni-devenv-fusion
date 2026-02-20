use crate::jobs::manager::JobMetricsSnapshot;

/// Queue health state from metrics (used by heartbeat logs and `/jobs` checks).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum JobHealthState {
    /// Queue/running jobs are within configured age bounds.
    Healthy,
    /// Old queued job indicates backlog stall.
    QueueStalled,
    /// Long-running job indicates execution stall.
    RunningStalled,
}

/// Classify job health from age thresholds.
pub fn classify_job_health(
    metrics: &JobMetricsSnapshot,
    max_queued_age_secs: u64,
    max_running_age_secs: u64,
) -> JobHealthState {
    if metrics.oldest_queued_age_secs.unwrap_or(0) > max_queued_age_secs {
        return JobHealthState::QueueStalled;
    }
    if metrics.longest_running_age_secs.unwrap_or(0) > max_running_age_secs {
        return JobHealthState::RunningStalled;
    }
    JobHealthState::Healthy
}
