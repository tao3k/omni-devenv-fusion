use crate::channels::managed_commands as managed;

use super::types::{ManagedControlCommand, ManagedSlashCommand};

pub fn detect_managed_slash_command(input: &str) -> Option<ManagedSlashCommand> {
    managed::detect_managed_slash_command(input).map(map_managed_slash_command)
}

pub fn detect_managed_control_command(input: &str) -> Option<ManagedControlCommand> {
    managed::detect_managed_control_command(input).map(map_managed_control_command)
}

fn map_managed_slash_command(command: managed::ManagedSlashCommand) -> ManagedSlashCommand {
    match command {
        managed::ManagedSlashCommand::SessionStatus => ManagedSlashCommand::SessionStatus,
        managed::ManagedSlashCommand::SessionBudget => ManagedSlashCommand::SessionBudget,
        managed::ManagedSlashCommand::SessionMemory => ManagedSlashCommand::SessionMemory,
        managed::ManagedSlashCommand::SessionFeedback => ManagedSlashCommand::SessionFeedback,
        managed::ManagedSlashCommand::JobStatus => ManagedSlashCommand::JobStatus,
        managed::ManagedSlashCommand::JobsSummary => ManagedSlashCommand::JobsSummary,
        managed::ManagedSlashCommand::BackgroundSubmit => ManagedSlashCommand::BackgroundSubmit,
    }
}

fn map_managed_control_command(command: managed::ManagedControlCommand) -> ManagedControlCommand {
    match command {
        managed::ManagedControlCommand::Reset => ManagedControlCommand::Reset,
        managed::ManagedControlCommand::ResumeRestore => ManagedControlCommand::ResumeRestore,
        managed::ManagedControlCommand::ResumeStatus => ManagedControlCommand::ResumeStatus,
        managed::ManagedControlCommand::ResumeDrop => ManagedControlCommand::ResumeDrop,
        managed::ManagedControlCommand::SessionAdmin => ManagedControlCommand::SessionAdmin,
        managed::ManagedControlCommand::SessionPartition => ManagedControlCommand::SessionPartition,
    }
}
