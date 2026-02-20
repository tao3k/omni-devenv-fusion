//! Background job manager: bounded queue, concurrent workers, timeout handling, heartbeat.

mod core;
mod types;

pub use core::JobManager;
pub use types::{
    JobCompletion, JobCompletionKind, JobManagerConfig, JobMetricsSnapshot, JobState,
    JobStatusSnapshot, TurnRunner,
};
