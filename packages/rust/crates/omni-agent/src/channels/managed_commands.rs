//! Shared managed-command classification and slash scope constants.
//!
//! These commands are platform-facing operational commands (session/job/background control)
//! handled outside generic LLM conversation flow.

use crate::channels::managed_runtime::parsing::{
    parse_session_partition_command as parse_session_partition_shared,
    parse_session_partition_mode_token,
};

pub(crate) const SLASH_SCOPE_SESSION_STATUS: &str = "session.status";
pub(crate) const SLASH_SCOPE_SESSION_BUDGET: &str = "session.budget";
pub(crate) const SLASH_SCOPE_SESSION_MEMORY: &str = "session.memory";
pub(crate) const SLASH_SCOPE_SESSION_FEEDBACK: &str = "session.feedback";
pub(crate) const SLASH_SCOPE_JOB_STATUS: &str = "job.status";
pub(crate) const SLASH_SCOPE_JOBS_SUMMARY: &str = "jobs.summary";
pub(crate) const SLASH_SCOPE_BACKGROUND_SUBMIT: &str = "background.submit";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ManagedSlashCommand {
    SessionStatus,
    SessionBudget,
    SessionMemory,
    SessionFeedback,
    JobStatus,
    JobsSummary,
    BackgroundSubmit,
}

impl ManagedSlashCommand {
    pub(crate) const fn scope(self) -> &'static str {
        match self {
            Self::SessionStatus => SLASH_SCOPE_SESSION_STATUS,
            Self::SessionBudget => SLASH_SCOPE_SESSION_BUDGET,
            Self::SessionMemory => SLASH_SCOPE_SESSION_MEMORY,
            Self::SessionFeedback => SLASH_SCOPE_SESSION_FEEDBACK,
            Self::JobStatus => SLASH_SCOPE_JOB_STATUS,
            Self::JobsSummary => SLASH_SCOPE_JOBS_SUMMARY,
            Self::BackgroundSubmit => SLASH_SCOPE_BACKGROUND_SUBMIT,
        }
    }

    pub(crate) const fn canonical_command(self) -> &'static str {
        match self {
            Self::SessionStatus => "/session",
            Self::SessionBudget => "/session budget",
            Self::SessionMemory => "/session memory",
            Self::SessionFeedback => "/session feedback",
            Self::JobStatus => "/job",
            Self::JobsSummary => "/jobs",
            Self::BackgroundSubmit => "/bg",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ManagedControlCommand {
    Reset,
    ResumeRestore,
    ResumeStatus,
    ResumeDrop,
    SessionAdmin,
    SessionPartition,
}

impl ManagedControlCommand {
    pub(crate) const fn canonical_command(self) -> &'static str {
        match self {
            Self::Reset => "/reset",
            Self::ResumeRestore => "/resume",
            Self::ResumeStatus => "/resume status",
            Self::ResumeDrop => "/resume drop",
            Self::SessionAdmin => "/session admin",
            Self::SessionPartition => "/session partition",
        }
    }
}

/// Detect managed non-privileged slash commands that are ACL-scoped by `Channel::is_authorized_for_slash_command`.
pub(crate) fn detect_managed_slash_command(input: &str) -> Option<ManagedSlashCommand> {
    let normalized = normalize_command_input(input);
    let tokens: Vec<&str> = normalized.split_whitespace().collect();
    let command = *tokens.first()?;

    if is_session_family_command(command) {
        return detect_session_family_slash_command(&tokens);
    }
    if command.eq_ignore_ascii_case("feedback") {
        return detect_short_feedback_command(&tokens);
    }
    if command.eq_ignore_ascii_case("job") {
        return detect_job_status_command(&tokens);
    }
    if command.eq_ignore_ascii_case("jobs") {
        return detect_jobs_summary_command(&tokens);
    }
    if command.eq_ignore_ascii_case("bg") || command.eq_ignore_ascii_case("research") {
        return detect_background_submit_command(&tokens);
    }
    None
}

/// Detect privileged managed control commands that are ACL-scoped by
/// `Channel::is_authorized_for_control_command`.
pub(crate) fn detect_managed_control_command(input: &str) -> Option<ManagedControlCommand> {
    let normalized = normalize_command_input(input);
    let tokens: Vec<&str> = normalized.split_whitespace().collect();
    let command = *tokens.first()?;

    if (command.eq_ignore_ascii_case("reset") || command.eq_ignore_ascii_case("clear"))
        && tokens.len() == 1
    {
        return Some(ManagedControlCommand::Reset);
    }

    if command.eq_ignore_ascii_case("resume") {
        return match tokens.as_slice() {
            [_] => Some(ManagedControlCommand::ResumeRestore),
            [_, sub]
                if sub.eq_ignore_ascii_case("status")
                    || sub.eq_ignore_ascii_case("stats")
                    || sub.eq_ignore_ascii_case("info") =>
            {
                Some(ManagedControlCommand::ResumeStatus)
            }
            [_, sub] if sub.eq_ignore_ascii_case("drop") || sub.eq_ignore_ascii_case("discard") => {
                Some(ManagedControlCommand::ResumeDrop)
            }
            _ => None,
        };
    }

    if is_session_partition_control_command(normalized) {
        return Some(ManagedControlCommand::SessionPartition);
    }
    if is_session_admin_control_command(normalized) {
        return Some(ManagedControlCommand::SessionAdmin);
    }

    None
}

fn normalize_command_input(input: &str) -> &str {
    let mut normalized = input.trim();
    if normalized.starts_with('[')
        && let Some(end) = normalized.find(']')
    {
        let tag = &normalized[1..end];
        if tag.to_ascii_lowercase().starts_with("bbx-") {
            normalized = normalized[end + 1..].trim_start();
        }
    }
    normalized.trim_start_matches('/')
}

fn is_session_family_command(command: &str) -> bool {
    command.eq_ignore_ascii_case("session")
        || command.eq_ignore_ascii_case("window")
        || command.eq_ignore_ascii_case("context")
}

fn is_json_token(token: &str) -> bool {
    token.eq_ignore_ascii_case("json")
}

fn is_status_alias(token: &str) -> bool {
    token.eq_ignore_ascii_case("status")
        || token.eq_ignore_ascii_case("stats")
        || token.eq_ignore_ascii_case("info")
}

fn is_memory_alias(token: &str) -> bool {
    token.eq_ignore_ascii_case("memory") || token.eq_ignore_ascii_case("recall")
}

fn is_feedback_direction(token: &str) -> bool {
    token.eq_ignore_ascii_case("up")
        || token.eq_ignore_ascii_case("success")
        || token.eq_ignore_ascii_case("positive")
        || token.eq_ignore_ascii_case("good")
        || token == "+"
        || token.eq_ignore_ascii_case("down")
        || token.eq_ignore_ascii_case("failure")
        || token.eq_ignore_ascii_case("negative")
        || token.eq_ignore_ascii_case("bad")
        || token.eq_ignore_ascii_case("fail")
        || token == "-"
}

fn is_session_partition_control_command(input: &str) -> bool {
    parse_session_partition_shared(input, parse_session_partition_mode_token).is_some()
}

fn is_session_admin_control_command(input: &str) -> bool {
    let tokens: Vec<&str> = input.split_whitespace().collect();
    match tokens.as_slice() {
        [scope, admin]
            if (scope.eq_ignore_ascii_case("session")
                || scope.eq_ignore_ascii_case("window")
                || scope.eq_ignore_ascii_case("context"))
                && admin.eq_ignore_ascii_case("admin") =>
        {
            true
        }
        [scope, admin, third]
            if (scope.eq_ignore_ascii_case("session")
                || scope.eq_ignore_ascii_case("window")
                || scope.eq_ignore_ascii_case("context"))
                && admin.eq_ignore_ascii_case("admin")
                && (third.eq_ignore_ascii_case("json")
                    || third.eq_ignore_ascii_case("list")
                    || third.eq_ignore_ascii_case("clear")) =>
        {
            true
        }
        [scope, admin, action, ..]
            if (scope.eq_ignore_ascii_case("session")
                || scope.eq_ignore_ascii_case("window")
                || scope.eq_ignore_ascii_case("context"))
                && admin.eq_ignore_ascii_case("admin")
                && (action.eq_ignore_ascii_case("set")
                    || action.eq_ignore_ascii_case("add")
                    || action.eq_ignore_ascii_case("remove")
                    || action.eq_ignore_ascii_case("rm")
                    || action.eq_ignore_ascii_case("del")) =>
        {
            true
        }
        _ => false,
    }
}

fn detect_session_family_slash_command(tokens: &[&str]) -> Option<ManagedSlashCommand> {
    match tokens {
        [_] => Some(ManagedSlashCommand::SessionStatus),
        [_, one] if is_json_token(one) || is_status_alias(one) => {
            Some(ManagedSlashCommand::SessionStatus)
        }
        [_, one] if one.eq_ignore_ascii_case("budget") => Some(ManagedSlashCommand::SessionBudget),
        [_, one] if is_memory_alias(one) => Some(ManagedSlashCommand::SessionMemory),
        [_, one, two]
            if (is_status_alias(one)
                || one.eq_ignore_ascii_case("budget")
                || is_memory_alias(one))
                && is_json_token(two) =>
        {
            if is_status_alias(one) {
                Some(ManagedSlashCommand::SessionStatus)
            } else if one.eq_ignore_ascii_case("budget") {
                Some(ManagedSlashCommand::SessionBudget)
            } else {
                Some(ManagedSlashCommand::SessionMemory)
            }
        }
        [_, sub, direction]
            if sub.eq_ignore_ascii_case("feedback") && is_feedback_direction(direction) =>
        {
            Some(ManagedSlashCommand::SessionFeedback)
        }
        [_, sub, direction, fmt]
            if sub.eq_ignore_ascii_case("feedback")
                && is_feedback_direction(direction)
                && is_json_token(fmt) =>
        {
            Some(ManagedSlashCommand::SessionFeedback)
        }
        _ => None,
    }
}

fn detect_short_feedback_command(tokens: &[&str]) -> Option<ManagedSlashCommand> {
    match tokens {
        [_, direction] if is_feedback_direction(direction) => {
            Some(ManagedSlashCommand::SessionFeedback)
        }
        [_, direction, fmt] if is_feedback_direction(direction) && is_json_token(fmt) => {
            Some(ManagedSlashCommand::SessionFeedback)
        }
        _ => None,
    }
}

fn detect_job_status_command(tokens: &[&str]) -> Option<ManagedSlashCommand> {
    match tokens {
        [_, _job_id] => Some(ManagedSlashCommand::JobStatus),
        [_, _job_id, fmt] if is_json_token(fmt) => Some(ManagedSlashCommand::JobStatus),
        _ => None,
    }
}

fn detect_jobs_summary_command(tokens: &[&str]) -> Option<ManagedSlashCommand> {
    match tokens {
        [_] => Some(ManagedSlashCommand::JobsSummary),
        [_, fmt] if is_json_token(fmt) => Some(ManagedSlashCommand::JobsSummary),
        _ => None,
    }
}

fn detect_background_submit_command(tokens: &[&str]) -> Option<ManagedSlashCommand> {
    if tokens.len() >= 2 {
        Some(ManagedSlashCommand::BackgroundSubmit)
    } else {
        None
    }
}
