//! Test-only compatibility exports for integration tests.
//!
//! This module provides stable wrappers so tests can validate parser behavior
//! without path-compiling source files via `#[path = ...]`.

mod managed_parser;
mod telegram_parser;
mod types;

pub use managed_parser::{detect_managed_control_command, detect_managed_slash_command};
pub use telegram_parser::{
    is_reset_context_command, parse_background_prompt, parse_help_command,
    parse_job_status_command, parse_jobs_summary_command, parse_resume_context_command,
    parse_session_admin_command, parse_session_context_budget_command,
    parse_session_context_memory_command, parse_session_context_status_command,
    parse_session_feedback_command, parse_session_injection_command,
    parse_session_partition_command,
};
pub use types::{
    JobStatusCommand, ManagedControlCommand, ManagedSlashCommand, OutputFormat,
    ResumeContextCommand, SessionAdminAction, SessionAdminCommand, SessionFeedbackCommand,
    SessionFeedbackDirection, SessionInjectionAction, SessionInjectionCommand,
    SessionPartitionCommand, SessionPartitionMode,
};
