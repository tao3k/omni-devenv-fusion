use tokio::time::error::Elapsed;

/// Result classification for a heartbeat probe with timeout.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HeartbeatProbeState {
    /// Probe finished inside the timeout window.
    Healthy,
    /// Probe timed out.
    Timeout,
}

/// Classify a timeout-wrapped heartbeat probe result.
pub fn classify_heartbeat_probe_result<T>(result: &Result<T, Elapsed>) -> HeartbeatProbeState {
    match result {
        Ok(_) => HeartbeatProbeState::Healthy,
        Err(_) => HeartbeatProbeState::Timeout,
    }
}
