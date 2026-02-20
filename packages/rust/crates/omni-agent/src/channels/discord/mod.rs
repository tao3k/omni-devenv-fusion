//! Discord channel integration (skeleton).

mod channel;
mod client;
mod constants;
mod parsing;
mod runtime;
mod send;
mod session_partition;

pub use channel::{DiscordChannel, DiscordControlCommandPolicy, DiscordSlashCommandPolicy};
pub use constants::DISCORD_MAX_MESSAGE_LENGTH;
pub use runtime::{
    DiscordIngressApp, DiscordRuntimeConfig, build_discord_ingress_app,
    build_discord_ingress_app_with_control_command_policy,
    build_discord_ingress_app_with_partition_and_control_command_policy, run_discord_ingress,
};
pub use send::split_message_for_discord;
pub use session_partition::DiscordSessionPartition;
