use super::shared::{
    SessionPartitionModeToken, is_reset_context_command as is_reset_context_command_shared,
    normalize_command_input, parse_resume_context_command as parse_resume_shared,
    parse_session_context_budget_command as parse_session_budget_shared,
    parse_session_context_memory_command as parse_session_memory_shared,
    parse_session_context_status_command as parse_session_status_shared,
    parse_session_feedback_command as parse_session_feedback_shared,
    parse_session_partition_command as parse_session_partition_shared,
    parse_session_partition_mode_token as parse_partition_mode_token,
    slice_original_command_suffix,
};

pub type ResumeContextCommand = super::shared::ResumeCommand;
pub type SessionFeedbackDirection = super::shared::FeedbackDirection;
pub type SessionFeedbackCommand = super::shared::SessionFeedbackCommand;
pub type SessionOutputFormat = super::shared::OutputFormat;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SessionInjectionAction {
    Status,
    Clear,
    SetXml(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionInjectionCommand {
    pub action: SessionInjectionAction,
    pub format: SessionOutputFormat,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SessionAdminAction {
    List,
    Set(Vec<String>),
    Add(Vec<String>),
    Remove(Vec<String>),
    Clear,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SessionAdminCommand {
    pub action: SessionAdminAction,
    pub format: SessionOutputFormat,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SessionPartitionMode {
    Chat,
    ChatUser,
    User,
    ChatThreadUser,
}

impl SessionPartitionMode {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Chat => "chat",
            Self::ChatUser => "chat_user",
            Self::User => "user",
            Self::ChatThreadUser => "chat_thread_user",
        }
    }
}

pub type SessionPartitionCommand = super::shared::SessionPartitionCommand<SessionPartitionMode>;

/// Parse session status command and return output format.
pub fn parse_session_context_status_command(input: &str) -> Option<SessionOutputFormat> {
    parse_session_status_shared(input)
}

/// Parse session budget command and return output format.
pub fn parse_session_context_budget_command(input: &str) -> Option<SessionOutputFormat> {
    parse_session_budget_shared(input)
}

/// Parse session memory command and return output format.
pub fn parse_session_context_memory_command(input: &str) -> Option<SessionOutputFormat> {
    parse_session_memory_shared(input)
}

/// Parse session partition command:
/// - `/session partition` (status)
/// - `/session partition json`
/// - `/session partition on|off`
/// - `/session partition chat|chat_user|user|chat_thread_user [json]`
pub fn parse_session_partition_command(input: &str) -> Option<SessionPartitionCommand> {
    parse_session_partition_shared(input, parse_session_partition_mode)
}

/// Parse session recall-feedback command:
/// - `/session feedback up|down [json]`
/// - `/window feedback up|down [json]`
/// - `/context feedback up|down [json]`
/// - `/feedback up|down [json]`
pub fn parse_session_feedback_command(input: &str) -> Option<SessionFeedbackCommand> {
    parse_session_feedback_shared(input)
}

/// Parse session system prompt injection command:
/// - `/session inject` or `/session inject status [json]`
/// - `/session inject clear [json]`
/// - `/session inject set <xml>`
/// - `/session inject <xml>`
pub fn parse_session_injection_command(input: &str) -> Option<SessionInjectionCommand> {
    let normalized = normalize_command_input(input);
    let lowered = normalized.to_ascii_lowercase();
    let prefixes = [
        "session inject",
        "window inject",
        "context inject",
        "session injection",
        "window injection",
        "context injection",
    ];

    let rest = prefixes.iter().find_map(|prefix| {
        lowered.strip_prefix(prefix).and_then(|suffix| {
            if suffix.trim().is_empty() {
                Some(String::new())
            } else {
                slice_original_command_suffix(normalized, suffix).map(ToString::to_string)
            }
        })
    })?;

    let tail = rest.trim();
    if tail.is_empty() {
        return Some(SessionInjectionCommand {
            action: SessionInjectionAction::Status,
            format: SessionOutputFormat::Dashboard,
        });
    }
    if tail.eq_ignore_ascii_case("json") {
        return Some(SessionInjectionCommand {
            action: SessionInjectionAction::Status,
            format: SessionOutputFormat::Json,
        });
    }
    if tail.eq_ignore_ascii_case("status") {
        return Some(SessionInjectionCommand {
            action: SessionInjectionAction::Status,
            format: SessionOutputFormat::Dashboard,
        });
    }
    if tail.eq_ignore_ascii_case("status json") {
        return Some(SessionInjectionCommand {
            action: SessionInjectionAction::Status,
            format: SessionOutputFormat::Json,
        });
    }
    if tail.eq_ignore_ascii_case("clear") {
        return Some(SessionInjectionCommand {
            action: SessionInjectionAction::Clear,
            format: SessionOutputFormat::Dashboard,
        });
    }
    if tail.eq_ignore_ascii_case("clear json") {
        return Some(SessionInjectionCommand {
            action: SessionInjectionAction::Clear,
            format: SessionOutputFormat::Json,
        });
    }
    if tail.eq_ignore_ascii_case("set") {
        return None;
    }
    let lowered_tail = tail.to_ascii_lowercase();
    if lowered_tail.starts_with("status ") || lowered_tail.starts_with("clear ") {
        return None;
    }

    let payload = if lowered_tail.starts_with("set ") {
        tail[4..].trim()
    } else {
        tail
    };
    if payload.is_empty() {
        return None;
    }
    Some(SessionInjectionCommand {
        action: SessionInjectionAction::SetXml(payload.to_string()),
        format: SessionOutputFormat::Dashboard,
    })
}

/// Parse delegated session-admin command:
/// - `/session admin` or `/session admin list [json]`
/// - `/session admin set <user_ids...> [json]`
/// - `/session admin add <user_ids...> [json]`
/// - `/session admin remove <user_ids...> [json]`
/// - `/session admin clear [json]`
pub fn parse_session_admin_command(input: &str) -> Option<SessionAdminCommand> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let root = parts.next()?;
    if !root.eq_ignore_ascii_case("session")
        && !root.eq_ignore_ascii_case("window")
        && !root.eq_ignore_ascii_case("context")
    {
        return None;
    }
    let Some(sub) = parts.next() else {
        return None;
    };
    if !sub.eq_ignore_ascii_case("admin") {
        return None;
    }
    let tokens: Vec<&str> = parts.collect();
    if tokens.is_empty() {
        return Some(SessionAdminCommand {
            action: SessionAdminAction::List,
            format: SessionOutputFormat::Dashboard,
        });
    }
    if tokens.len() == 1 && tokens[0].eq_ignore_ascii_case("json") {
        return Some(SessionAdminCommand {
            action: SessionAdminAction::List,
            format: SessionOutputFormat::Json,
        });
    }

    let mut format = SessionOutputFormat::Dashboard;
    let args_end = if tokens
        .last()
        .is_some_and(|token| token.eq_ignore_ascii_case("json"))
    {
        format = SessionOutputFormat::Json;
        tokens.len().saturating_sub(1)
    } else {
        tokens.len()
    };
    if args_end == 0 {
        return None;
    }
    let command = tokens[0];
    let id_tokens = &tokens[1..args_end];
    let action = if command.eq_ignore_ascii_case("list") {
        if !id_tokens.is_empty() {
            return None;
        }
        SessionAdminAction::List
    } else if command.eq_ignore_ascii_case("clear") {
        if !id_tokens.is_empty() {
            return None;
        }
        SessionAdminAction::Clear
    } else if command.eq_ignore_ascii_case("set") {
        SessionAdminAction::Set(parse_admin_user_ids(id_tokens)?)
    } else if command.eq_ignore_ascii_case("add") {
        SessionAdminAction::Add(parse_admin_user_ids(id_tokens)?)
    } else if command.eq_ignore_ascii_case("remove")
        || command.eq_ignore_ascii_case("rm")
        || command.eq_ignore_ascii_case("del")
    {
        SessionAdminAction::Remove(parse_admin_user_ids(id_tokens)?)
    } else if command.eq_ignore_ascii_case("json") {
        return None;
    } else {
        SessionAdminAction::Set(parse_admin_user_ids(&tokens[..args_end])?)
    };

    Some(SessionAdminCommand { action, format })
}

/// Parse `/reset`, `/clear`, `reset`, or `clear`.
pub fn is_reset_context_command(input: &str) -> bool {
    is_reset_context_command_shared(input)
}

/// Parse `/resume` or `resume`, with optional `/resume status`.
pub fn parse_resume_context_command(input: &str) -> Option<ResumeContextCommand> {
    parse_resume_shared(input)
}

fn parse_session_partition_mode(raw: &str) -> Option<SessionPartitionMode> {
    let token = parse_partition_mode_token(raw)?;
    match token {
        SessionPartitionModeToken::Chat => Some(SessionPartitionMode::Chat),
        SessionPartitionModeToken::ChatUser => Some(SessionPartitionMode::ChatUser),
        SessionPartitionModeToken::User => Some(SessionPartitionMode::User),
        SessionPartitionModeToken::ChatThreadUser => Some(SessionPartitionMode::ChatThreadUser),
        SessionPartitionModeToken::GuildChannelUser
        | SessionPartitionModeToken::Channel
        | SessionPartitionModeToken::GuildUser => None,
    }
}

fn parse_admin_user_ids(raw_tokens: &[&str]) -> Option<Vec<String>> {
    if raw_tokens.is_empty() {
        return None;
    }
    let values: Vec<String> = raw_tokens
        .iter()
        .flat_map(|token| token.split(','))
        .map(str::trim)
        .filter(|token| !token.is_empty())
        .map(ToString::to_string)
        .collect();
    if values.is_empty() {
        return None;
    }
    Some(values)
}
