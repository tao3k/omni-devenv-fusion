//! Background job queue for long-running turns (e.g. research-heavy requests).

mod heartbeat;
mod manager;
mod scheduler;

pub use heartbeat::{
    HeartbeatProbeState, JobHealthState, classify_heartbeat_probe_result, classify_job_health,
};
pub use manager::{
    JobCompletion, JobCompletionKind, JobManager, JobManagerConfig, JobMetricsSnapshot, JobState,
    JobStatusSnapshot, TurnRunner,
};
pub use scheduler::{RecurringScheduleConfig, RecurringScheduleOutcome, run_recurring_schedule};
