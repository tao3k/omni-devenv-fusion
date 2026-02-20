use crate::channels::telegram::commands as telegram;

use super::types::{
    JobStatusCommand, ResumeContextCommand, SessionAdminAction, SessionAdminCommand,
    SessionFeedbackCommand, SessionFeedbackDirection, SessionInjectionAction,
    SessionInjectionCommand, SessionPartitionCommand, SessionPartitionMode, map_output_format,
};

pub fn parse_help_command(input: &str) -> Option<super::types::OutputFormat> {
    telegram::parse_help_command(input).map(|format| map_output_format(format.is_json()))
}

pub fn parse_background_prompt(input: &str) -> Option<String> {
    telegram::parse_background_prompt(input)
}

pub fn parse_job_status_command(input: &str) -> Option<JobStatusCommand> {
    telegram::parse_job_status_command(input).map(|parsed| JobStatusCommand {
        job_id: parsed.job_id,
        format: map_output_format(parsed.format.is_json()),
    })
}

pub fn parse_jobs_summary_command(input: &str) -> Option<super::types::OutputFormat> {
    telegram::parse_jobs_summary_command(input).map(|format| map_output_format(format.is_json()))
}

pub fn parse_session_context_status_command(input: &str) -> Option<super::types::OutputFormat> {
    telegram::parse_session_context_status_command(input)
        .map(|format| map_output_format(format.is_json()))
}

pub fn parse_session_context_budget_command(input: &str) -> Option<super::types::OutputFormat> {
    telegram::parse_session_context_budget_command(input)
        .map(|format| map_output_format(format.is_json()))
}

pub fn parse_session_context_memory_command(input: &str) -> Option<super::types::OutputFormat> {
    telegram::parse_session_context_memory_command(input)
        .map(|format| map_output_format(format.is_json()))
}

pub fn parse_session_feedback_command(input: &str) -> Option<SessionFeedbackCommand> {
    telegram::parse_session_feedback_command(input).map(|parsed| SessionFeedbackCommand {
        direction: map_feedback_direction(parsed.direction),
        format: map_output_format(parsed.format.is_json()),
    })
}

pub fn parse_session_injection_command(input: &str) -> Option<SessionInjectionCommand> {
    telegram::parse_session_injection_command(input).map(|parsed| SessionInjectionCommand {
        action: match parsed.action {
            telegram::SessionInjectionAction::Status => SessionInjectionAction::Status,
            telegram::SessionInjectionAction::Clear => SessionInjectionAction::Clear,
            telegram::SessionInjectionAction::SetXml(xml) => SessionInjectionAction::SetXml(xml),
        },
        format: map_output_format(parsed.format.is_json()),
    })
}

pub fn parse_session_admin_command(input: &str) -> Option<SessionAdminCommand> {
    telegram::parse_session_admin_command(input).map(|parsed| SessionAdminCommand {
        action: match parsed.action {
            telegram::SessionAdminAction::List => SessionAdminAction::List,
            telegram::SessionAdminAction::Set(entries) => SessionAdminAction::Set(entries),
            telegram::SessionAdminAction::Add(entries) => SessionAdminAction::Add(entries),
            telegram::SessionAdminAction::Remove(entries) => SessionAdminAction::Remove(entries),
            telegram::SessionAdminAction::Clear => SessionAdminAction::Clear,
        },
        format: map_output_format(parsed.format.is_json()),
    })
}

pub fn parse_session_partition_command(input: &str) -> Option<SessionPartitionCommand> {
    telegram::parse_session_partition_command(input).map(|parsed| SessionPartitionCommand {
        mode: parsed.mode.map(map_session_partition_mode),
        format: map_output_format(parsed.format.is_json()),
    })
}

pub fn is_reset_context_command(input: &str) -> bool {
    telegram::is_reset_context_command(input)
}

pub fn parse_resume_context_command(input: &str) -> Option<ResumeContextCommand> {
    telegram::parse_resume_context_command(input).map(map_resume_command)
}

fn map_feedback_direction(
    direction: telegram::SessionFeedbackDirection,
) -> SessionFeedbackDirection {
    match direction {
        telegram::SessionFeedbackDirection::Up => SessionFeedbackDirection::Up,
        telegram::SessionFeedbackDirection::Down => SessionFeedbackDirection::Down,
    }
}

fn map_session_partition_mode(mode: telegram::SessionPartitionMode) -> SessionPartitionMode {
    match mode {
        telegram::SessionPartitionMode::Chat => SessionPartitionMode::Chat,
        telegram::SessionPartitionMode::ChatUser => SessionPartitionMode::ChatUser,
        telegram::SessionPartitionMode::User => SessionPartitionMode::User,
        telegram::SessionPartitionMode::ChatThreadUser => SessionPartitionMode::ChatThreadUser,
    }
}

fn map_resume_command(command: telegram::ResumeContextCommand) -> ResumeContextCommand {
    match command {
        telegram::ResumeContextCommand::Restore => ResumeContextCommand::Restore,
        telegram::ResumeContextCommand::Status => ResumeContextCommand::Status,
        telegram::ResumeContextCommand::Drop => ResumeContextCommand::Drop,
    }
}
