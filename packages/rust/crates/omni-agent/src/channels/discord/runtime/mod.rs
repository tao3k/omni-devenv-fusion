//! Discord runtime wiring (ingress + foreground turn execution).

mod config;
mod dispatch;
mod ingress;
mod managed;
mod run;
#[cfg(test)]
#[path = "../../../../tests/discord_runtime/mod.rs"]
mod tests;

pub use config::DiscordRuntimeConfig;
pub use ingress::{
    DiscordIngressApp, build_discord_ingress_app,
    build_discord_ingress_app_with_control_command_policy,
    build_discord_ingress_app_with_partition_and_control_command_policy,
};
pub use run::run_discord_ingress;
