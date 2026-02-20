//! Discord session partition strategy for multi-guild/channel isolation.

use std::fmt::{Display, Formatter};
use std::str::FromStr;

/// How incoming Discord messages are mapped to a logical conversation session.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum DiscordSessionPartition {
    /// Isolate by `guild_or_dm:channel_id:user_id` (safe default for multi-channel usage).
    #[default]
    GuildChannelUser,
    /// Share one session per channel (`guild_or_dm:channel_id`).
    ChannelOnly,
    /// Share one session per user across all guilds/channels (`user_id`).
    UserOnly,
    /// Share one session per user within one guild/DM scope (`guild_or_dm:user_id`).
    GuildUser,
}

impl DiscordSessionPartition {
    /// Resolve partition mode from environment.
    ///
    /// Accepted values:
    /// - `guild_channel_user` (default)
    /// - `channel`
    /// - `user`
    /// - `guild_user`
    pub fn from_env() -> Self {
        let Some(raw) = std::env::var("OMNI_AGENT_DISCORD_SESSION_PARTITION").ok() else {
            return Self::default();
        };
        match raw.parse() {
            Ok(mode) => mode,
            Err(_) => {
                tracing::warn!(
                    value = %raw,
                    "invalid OMNI_AGENT_DISCORD_SESSION_PARTITION; using guild_channel_user"
                );
                Self::default()
            }
        }
    }

    /// Build a session key from Discord identifiers.
    pub fn build_session_key(self, scope: &str, channel_id: &str, user_identity: &str) -> String {
        match self {
            Self::GuildChannelUser => format!("{scope}:{channel_id}:{user_identity}"),
            Self::ChannelOnly => format!("{scope}:{channel_id}"),
            Self::UserOnly => user_identity.to_string(),
            Self::GuildUser => format!("{scope}:{user_identity}"),
        }
    }
}

impl Display for DiscordSessionPartition {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let value = match self {
            Self::GuildChannelUser => "guild_channel_user",
            Self::ChannelOnly => "channel",
            Self::UserOnly => "user",
            Self::GuildUser => "guild_user",
        };
        write!(f, "{value}")
    }
}

impl FromStr for DiscordSessionPartition {
    type Err = &'static str;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        match value.trim().to_ascii_lowercase().as_str() {
            "guild_channel_user" | "guild-channel-user" | "guildchanneluser" | "channel_user"
            | "channel-user" | "channeluser" => Ok(Self::GuildChannelUser),
            "channel" | "channel_only" | "channel-only" | "channelonly" => Ok(Self::ChannelOnly),
            "user" | "user_only" | "user-only" | "useronly" => Ok(Self::UserOnly),
            "guild_user" | "guild-user" | "guilduser" => Ok(Self::GuildUser),
            _ => Err("invalid discord session partition"),
        }
    }
}
