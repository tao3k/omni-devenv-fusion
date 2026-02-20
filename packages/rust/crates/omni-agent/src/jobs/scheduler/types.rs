/// Config for recurring scheduler runs.
#[derive(Debug, Clone)]
pub struct RecurringScheduleConfig {
    /// Logical schedule id for logs and session namespacing.
    pub schedule_id: String,
    /// Session prefix used by the queued jobs.
    pub session_prefix: String,
    /// Recipient identifier associated with queued jobs.
    pub recipient: String,
    /// Prompt executed on each schedule tick.
    pub prompt: String,
    /// Interval between submissions in seconds.
    pub interval_secs: u64,
    /// Optional run limit; `None` means run until Ctrl+C.
    pub max_runs: Option<u64>,
    /// Grace period to wait for in-flight completions before returning.
    pub wait_for_completion_secs: u64,
}

impl Default for RecurringScheduleConfig {
    fn default() -> Self {
        Self {
            schedule_id: "default".to_string(),
            session_prefix: "scheduler".to_string(),
            recipient: "scheduler".to_string(),
            prompt: String::new(),
            interval_secs: 300,
            max_runs: None,
            wait_for_completion_secs: 30,
        }
    }
}

/// Aggregated scheduler outcome counters.
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct RecurringScheduleOutcome {
    /// Number of submissions accepted by `JobManager`.
    pub submitted: u64,
    /// Number of completion events observed.
    pub completed: u64,
    /// Number of successful completions.
    pub succeeded: u64,
    /// Number of failed completions.
    pub failed: u64,
    /// Number of timed-out completions.
    pub timed_out: u64,
}
