use super::parsing::{SessionPartitionModeToken, session_partition_mode_name as mode_name};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum SessionPartitionProfile {
    Telegram,
    Discord,
}

const TELEGRAM_SUPPORTED_MODES: &[&str] = &[
    mode_name(SessionPartitionModeToken::Chat),
    mode_name(SessionPartitionModeToken::ChatUser),
    mode_name(SessionPartitionModeToken::User),
    mode_name(SessionPartitionModeToken::ChatThreadUser),
];
const DISCORD_SUPPORTED_MODES: &[&str] = &[
    mode_name(SessionPartitionModeToken::GuildChannelUser),
    mode_name(SessionPartitionModeToken::Channel),
    mode_name(SessionPartitionModeToken::User),
    mode_name(SessionPartitionModeToken::GuildUser),
];
const QUICK_TOGGLE_USAGE: &str = "/session partition on|off";

pub(crate) fn supported_modes(profile: SessionPartitionProfile) -> &'static [&'static str] {
    match profile {
        SessionPartitionProfile::Telegram => TELEGRAM_SUPPORTED_MODES,
        SessionPartitionProfile::Discord => DISCORD_SUPPORTED_MODES,
    }
}

pub(crate) fn supported_modes_csv(profile: SessionPartitionProfile) -> String {
    supported_modes(profile).join(",")
}

pub(crate) fn set_mode_usage(profile: SessionPartitionProfile) -> String {
    format!("/session partition {}", supported_modes(profile).join("|"))
}

pub(crate) const fn quick_toggle_usage() -> &'static str {
    QUICK_TOGGLE_USAGE
}
