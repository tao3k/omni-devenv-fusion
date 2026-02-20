macro_rules! eq_any_ignore_ascii {
    ($value:expr; $($candidate:literal),+ $(,)?) => {{
        let value = $value;
        false $(|| value.eq_ignore_ascii_case($candidate))+
    }};
}

macro_rules! define_session_partition_modes {
    (
        $(
            $variant:ident => {
                canonical: $canonical:literal,
                aliases: [$($alias:literal),* $(,)?],
            }
        ),+ $(,)?
    ) => {
        #[derive(Debug, Clone, Copy, PartialEq, Eq)]
        pub(crate) enum SessionPartitionModeToken {
            $($variant),+
        }

        pub(crate) const fn session_partition_mode_name(mode: SessionPartitionModeToken) -> &'static str {
            match mode {
                $(SessionPartitionModeToken::$variant => $canonical,)+
            }
        }

        pub(crate) fn parse_session_partition_mode_token(raw: &str) -> Option<SessionPartitionModeToken> {
            match raw.trim().to_ascii_lowercase().as_str() {
                $(
                    $canonical $(| $alias)* => Some(SessionPartitionModeToken::$variant),
                )+
                _ => None,
            }
        }
    };
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum OutputFormat {
    Dashboard,
    Json,
}

impl OutputFormat {
    pub(crate) fn is_json(self) -> bool {
        matches!(self, Self::Json)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ResumeCommand {
    Restore,
    Status,
    Drop,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum SessionContextCommandKind {
    Status,
    Budget,
    Memory,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum FeedbackDirection {
    Up,
    Down,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct SessionFeedbackCommand {
    pub(crate) direction: FeedbackDirection,
    pub(crate) format: OutputFormat,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct JobStatusCommand {
    pub(crate) job_id: String,
    pub(crate) format: OutputFormat,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct SessionPartitionCommand<Mode> {
    pub(crate) mode: Option<Mode>,
    pub(crate) format: OutputFormat,
}

define_session_partition_modes! {
    Chat => {
        canonical: "chat",
        aliases: ["on", "enable", "enabled", "shared", "group"],
    },
    ChatUser => {
        canonical: "chat_user",
        aliases: [
            "off",
            "disable",
            "disabled",
            "isolated",
            "chat-user",
            "chatuser",
            "channel_user",
            "channel-user",
            "channeluser",
        ],
    },
    User => {
        canonical: "user",
        aliases: ["user_only", "user-only", "useronly"],
    },
    ChatThreadUser => {
        canonical: "chat_thread_user",
        aliases: ["chat-thread-user", "chatthreaduser", "topic_user", "topic-user", "topicuser"],
    },
    GuildChannelUser => {
        canonical: "guild_channel_user",
        aliases: ["guild-channel-user", "guildchanneluser"],
    },
    Channel => {
        canonical: "channel",
        aliases: ["channel_only", "channel-only", "channelonly"],
    },
    GuildUser => {
        canonical: "guild_user",
        aliases: ["guild-user", "guilduser"],
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
struct SessionContextCommand {
    kind: SessionContextCommandKind,
    format: OutputFormat,
}

pub(crate) fn normalize_command_input(input: &str) -> &str {
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

pub(crate) fn slice_original_command_suffix<'a>(
    normalized: &'a str,
    lowered_suffix: &str,
) -> Option<&'a str> {
    let start = normalized.len().checked_sub(lowered_suffix.len())?;
    normalized
        .get(start..)
        .map(str::trim)
        .filter(|s| !s.is_empty())
}

pub(crate) fn parse_help_command(input: &str) -> Option<OutputFormat> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let command = parts.next()?;
    let arg1 = parts.next();
    let arg2 = parts.next();
    if parts.next().is_some() {
        return None;
    }

    match (command, arg1, arg2) {
        ("help", None, None) => Some(OutputFormat::Dashboard),
        ("help", Some(fmt), None) if eq_any_ignore_ascii!(fmt; "json") => Some(OutputFormat::Json),
        ("slash", Some(sub), None) if eq_any_ignore_ascii!(sub; "help") => {
            Some(OutputFormat::Dashboard)
        }
        ("slash", Some(sub), Some(fmt))
            if eq_any_ignore_ascii!(sub; "help") && eq_any_ignore_ascii!(fmt; "json") =>
        {
            Some(OutputFormat::Json)
        }
        ("commands", None, None) => Some(OutputFormat::Dashboard),
        ("commands", Some(fmt), None) if eq_any_ignore_ascii!(fmt; "json") => {
            Some(OutputFormat::Json)
        }
        _ => None,
    }
}

pub(crate) fn parse_background_prompt(input: &str) -> Option<String> {
    let normalized = normalize_command_input(input);
    let lower = normalized.to_ascii_lowercase();
    if let Some(rest) = lower.strip_prefix("bg ") {
        return slice_original_command_suffix(normalized, rest).map(ToString::to_string);
    }
    if let Some(rest) = lower.strip_prefix("research ") {
        let original = slice_original_command_suffix(normalized, rest)?;
        return Some(format!("research {}", original.trim()));
    }
    None
}

pub(crate) fn parse_job_status_command(input: &str) -> Option<JobStatusCommand> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let cmd = parts.next()?;
    if !eq_any_ignore_ascii!(cmd; "job") {
        return None;
    }

    let id = parts.next()?.trim();
    if id.is_empty() {
        return None;
    }
    let format = match parts.next() {
        None => OutputFormat::Dashboard,
        Some(value) if eq_any_ignore_ascii!(value; "json") => OutputFormat::Json,
        Some(_) => return None,
    };
    if parts.next().is_some() {
        return None;
    }
    Some(JobStatusCommand {
        job_id: id.to_string(),
        format,
    })
}

pub(crate) fn parse_jobs_summary_command(input: &str) -> Option<OutputFormat> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let cmd = parts.next()?;
    if !eq_any_ignore_ascii!(cmd; "jobs") {
        return None;
    }

    let format = match parts.next() {
        None => OutputFormat::Dashboard,
        Some(value) if eq_any_ignore_ascii!(value; "json") => OutputFormat::Json,
        Some(_) => return None,
    };
    if parts.next().is_some() {
        return None;
    }
    Some(format)
}

pub(crate) fn parse_session_context_status_command(input: &str) -> Option<OutputFormat> {
    let command = parse_session_context_command(input)?;
    if matches!(command.kind, SessionContextCommandKind::Status) {
        return Some(command.format);
    }
    None
}

pub(crate) fn parse_session_context_budget_command(input: &str) -> Option<OutputFormat> {
    let command = parse_session_context_command(input)?;
    if matches!(command.kind, SessionContextCommandKind::Budget) {
        return Some(command.format);
    }
    None
}

pub(crate) fn parse_session_context_memory_command(input: &str) -> Option<OutputFormat> {
    let command = parse_session_context_command(input)?;
    if matches!(command.kind, SessionContextCommandKind::Memory) {
        return Some(command.format);
    }
    None
}

pub(crate) fn parse_session_feedback_command(input: &str) -> Option<SessionFeedbackCommand> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let command = parts.next()?;

    let (direction_raw, format_raw) = if eq_any_ignore_ascii!(command; "feedback") {
        (parts.next()?, parts.next())
    } else {
        if !is_session_family_command(command) {
            return None;
        }
        let sub = parts.next()?;
        if !eq_any_ignore_ascii!(sub; "feedback") {
            return None;
        }
        (parts.next()?, parts.next())
    };
    if parts.next().is_some() {
        return None;
    }

    let direction = parse_feedback_direction(direction_raw)?;
    let format = match format_raw {
        None => OutputFormat::Dashboard,
        Some(value) if eq_any_ignore_ascii!(value; "json") => OutputFormat::Json,
        Some(_) => return None,
    };
    Some(SessionFeedbackCommand { direction, format })
}

pub(crate) fn parse_session_partition_command<Mode, F>(
    input: &str,
    parse_mode: F,
) -> Option<SessionPartitionCommand<Mode>>
where
    F: Fn(&str) -> Option<Mode>,
{
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let command = parts.next()?;
    if !is_session_family_command(command) {
        return None;
    }

    let sub = parts.next()?;
    if !eq_any_ignore_ascii!(sub; "partition") {
        return None;
    }

    let arg = parts.next();
    let maybe_json = parts.next();
    if parts.next().is_some() {
        return None;
    }

    match (arg, maybe_json) {
        (None, None) => Some(SessionPartitionCommand {
            mode: None,
            format: OutputFormat::Dashboard,
        }),
        (Some(value), None) if eq_any_ignore_ascii!(value; "json") => {
            Some(SessionPartitionCommand {
                mode: None,
                format: OutputFormat::Json,
            })
        }
        (Some(value), None) => Some(SessionPartitionCommand {
            mode: Some(parse_mode(value)?),
            format: OutputFormat::Dashboard,
        }),
        (Some(value), Some(fmt)) if eq_any_ignore_ascii!(fmt; "json") => {
            Some(SessionPartitionCommand {
                mode: Some(parse_mode(value)?),
                format: OutputFormat::Json,
            })
        }
        _ => None,
    }
}

pub(crate) fn is_reset_context_command(input: &str) -> bool {
    let normalized = normalize_command_input(input);
    eq_any_ignore_ascii!(normalized; "reset", "clear")
}

pub(crate) fn parse_resume_context_command(input: &str) -> Option<ResumeCommand> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let cmd = parts.next()?;
    if !eq_any_ignore_ascii!(cmd; "resume") {
        return None;
    }
    match (parts.next(), parts.next()) {
        (None, None) => Some(ResumeCommand::Restore),
        (Some(sub), None) if eq_any_ignore_ascii!(sub; "status", "stats", "info") => {
            Some(ResumeCommand::Status)
        }
        (Some(sub), None) if eq_any_ignore_ascii!(sub; "drop", "discard") => {
            Some(ResumeCommand::Drop)
        }
        _ => None,
    }
}

fn parse_session_context_command(input: &str) -> Option<SessionContextCommand> {
    let normalized = normalize_command_input(input);
    let mut parts = normalized.split_whitespace();
    let command = parts.next()?;
    if !is_session_family_command(command) {
        return None;
    }

    let sub = parts.next();
    let maybe_json = parts.next();
    if parts.next().is_some() {
        return None;
    }

    match (sub, maybe_json) {
        (None, None) => Some(SessionContextCommand {
            kind: SessionContextCommandKind::Status,
            format: OutputFormat::Dashboard,
        }),
        (Some(value), None) if eq_any_ignore_ascii!(value; "json") => Some(SessionContextCommand {
            kind: SessionContextCommandKind::Status,
            format: OutputFormat::Json,
        }),
        (Some(value), None) if is_status_alias(value) => Some(SessionContextCommand {
            kind: SessionContextCommandKind::Status,
            format: OutputFormat::Dashboard,
        }),
        (Some(value), None) if eq_any_ignore_ascii!(value; "budget") => {
            Some(SessionContextCommand {
                kind: SessionContextCommandKind::Budget,
                format: OutputFormat::Dashboard,
            })
        }
        (Some(value), None) if is_memory_alias(value) => Some(SessionContextCommand {
            kind: SessionContextCommandKind::Memory,
            format: OutputFormat::Dashboard,
        }),
        (Some(value), Some(fmt)) if eq_any_ignore_ascii!(fmt; "json") => {
            if is_status_alias(value) {
                return Some(SessionContextCommand {
                    kind: SessionContextCommandKind::Status,
                    format: OutputFormat::Json,
                });
            }
            if eq_any_ignore_ascii!(value; "budget") {
                return Some(SessionContextCommand {
                    kind: SessionContextCommandKind::Budget,
                    format: OutputFormat::Json,
                });
            }
            if is_memory_alias(value) {
                return Some(SessionContextCommand {
                    kind: SessionContextCommandKind::Memory,
                    format: OutputFormat::Json,
                });
            }
            None
        }
        _ => None,
    }
}

fn is_session_family_command(command: &str) -> bool {
    eq_any_ignore_ascii!(command; "session", "window", "context")
}

fn is_status_alias(token: &str) -> bool {
    eq_any_ignore_ascii!(token; "status", "stats", "info")
}

fn is_memory_alias(token: &str) -> bool {
    eq_any_ignore_ascii!(token; "memory", "recall")
}

fn parse_feedback_direction(raw: &str) -> Option<FeedbackDirection> {
    if eq_any_ignore_ascii!(raw; "up", "success", "positive", "good") || raw == "+" {
        return Some(FeedbackDirection::Up);
    }
    if eq_any_ignore_ascii!(raw; "down", "failure", "negative", "bad", "fail") || raw == "-" {
        return Some(FeedbackDirection::Down);
    }
    None
}
