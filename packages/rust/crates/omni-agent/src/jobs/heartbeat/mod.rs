//! Heartbeat and queue-health classification for background jobs.

mod health;
mod probe;

pub use health::{JobHealthState, classify_job_health};
pub use probe::{HeartbeatProbeState, classify_heartbeat_probe_result};
