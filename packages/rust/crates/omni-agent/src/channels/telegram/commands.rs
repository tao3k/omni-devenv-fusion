//! Parsing helpers for Telegram channel control commands.

#[path = "commands/background.rs"]
mod background;
#[path = "commands/help.rs"]
mod help;
#[path = "commands/job.rs"]
mod job;
#[path = "commands/session.rs"]
mod session;

pub(crate) use crate::channels::managed_runtime::parsing as shared;

pub use background::parse_background_prompt;
pub use help::parse_help_command;
pub use job::{parse_job_status_command, parse_jobs_summary_command};
pub use session::{
    ResumeContextCommand, SessionAdminAction, SessionFeedbackDirection, SessionInjectionAction,
    SessionPartitionMode, is_reset_context_command, parse_resume_context_command,
    parse_session_admin_command, parse_session_context_budget_command,
    parse_session_context_memory_command, parse_session_context_status_command,
    parse_session_feedback_command, parse_session_injection_command,
    parse_session_partition_command,
};
