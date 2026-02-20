pub(super) use crate::channels::managed_runtime::parsing::{
    FeedbackDirection, ResumeCommand, SessionFeedbackCommand,
    SessionPartitionCommand as SharedSessionPartitionCommand,
};
use crate::channels::managed_runtime::parsing::{
    OutputFormat, SessionPartitionModeToken, parse_background_prompt, parse_help_command,
    parse_job_status_command, parse_jobs_summary_command, parse_resume_context_command,
    parse_session_context_budget_command, parse_session_context_memory_command,
    parse_session_context_status_command, parse_session_feedback_command,
    parse_session_partition_command as parse_session_partition_shared,
    parse_session_partition_mode_token as parse_partition_mode_token,
};

use super::super::super::session_partition::DiscordSessionPartition;

pub(super) type CommandOutputFormat = OutputFormat;
type SessionPartitionMode = DiscordSessionPartition;
pub(super) type SessionPartitionCommand = SharedSessionPartitionCommand<SessionPartitionMode>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub(super) enum ManagedCommand {
    Help(CommandOutputFormat),
    Reset,
    Resume(ResumeCommand),
    SessionStatus(CommandOutputFormat),
    SessionBudget(CommandOutputFormat),
    SessionMemory(CommandOutputFormat),
    SessionFeedback(SessionFeedbackCommand),
    SessionPartition(SessionPartitionCommand),
    JobStatus {
        job_id: String,
        format: CommandOutputFormat,
    },
    JobsSummary(CommandOutputFormat),
    BackgroundSubmit(String),
}

pub(super) fn parse_managed_command(input: &str) -> Option<ManagedCommand> {
    if let Some(format) = parse_help_command(input) {
        return Some(ManagedCommand::Help(format));
    }
    if crate::channels::managed_runtime::parsing::is_reset_context_command(input) {
        return Some(ManagedCommand::Reset);
    }
    if let Some(resume) = parse_resume_context_command(input) {
        return Some(ManagedCommand::Resume(resume));
    }
    if let Some(command) = parse_session_partition_command(input) {
        return Some(ManagedCommand::SessionPartition(command));
    }
    if let Some(format) = parse_session_context_status_command(input) {
        return Some(ManagedCommand::SessionStatus(format));
    }
    if let Some(format) = parse_session_context_budget_command(input) {
        return Some(ManagedCommand::SessionBudget(format));
    }
    if let Some(format) = parse_session_context_memory_command(input) {
        return Some(ManagedCommand::SessionMemory(format));
    }
    if let Some(command) = parse_session_feedback_command(input) {
        return Some(ManagedCommand::SessionFeedback(command));
    }
    if let Some(command) = parse_job_status_command(input) {
        return Some(ManagedCommand::JobStatus {
            job_id: command.job_id,
            format: command.format,
        });
    }
    if let Some(format) = parse_jobs_summary_command(input) {
        return Some(ManagedCommand::JobsSummary(format));
    }
    if let Some(prompt) = parse_background_prompt(input) {
        return Some(ManagedCommand::BackgroundSubmit(prompt));
    }
    None
}

fn parse_session_partition_command(input: &str) -> Option<SessionPartitionCommand> {
    parse_session_partition_shared(input, parse_session_partition_mode)
}

fn parse_session_partition_mode(raw: &str) -> Option<SessionPartitionMode> {
    let token = parse_partition_mode_token(raw)?;
    match token {
        SessionPartitionModeToken::Chat | SessionPartitionModeToken::Channel => {
            Some(DiscordSessionPartition::ChannelOnly)
        }
        SessionPartitionModeToken::ChatUser
        | SessionPartitionModeToken::ChatThreadUser
        | SessionPartitionModeToken::GuildChannelUser => {
            Some(DiscordSessionPartition::GuildChannelUser)
        }
        SessionPartitionModeToken::User => Some(DiscordSessionPartition::UserOnly),
        SessionPartitionModeToken::GuildUser => Some(DiscordSessionPartition::GuildUser),
    }
}
