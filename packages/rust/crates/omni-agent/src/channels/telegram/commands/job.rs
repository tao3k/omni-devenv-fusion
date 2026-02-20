use super::shared::{
    JobStatusCommand, OutputFormat as JobOutputFormat,
    parse_job_status_command as parse_job_status_command_shared,
    parse_jobs_summary_command as parse_jobs_summary_command_shared,
};

/// Parse `/job <id>` or `/job <id> json`.
pub fn parse_job_status_command(input: &str) -> Option<JobStatusCommand> {
    parse_job_status_command_shared(input)
}

/// Parse `/jobs` or `/jobs json`.
pub fn parse_jobs_summary_command(input: &str) -> Option<JobOutputFormat> {
    parse_jobs_summary_command_shared(input)
}
