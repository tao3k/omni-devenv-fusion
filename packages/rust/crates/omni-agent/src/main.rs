//! omni-agent CLI: gateway, stdio, or repl mode.
//!
//! MCP servers from mcp.json only (default `.mcp.json`). Override with `--mcp-config <path>`.
//!
//! Logging: set `RUST_LOG=omni_agent=info` (or `warn`, `debug`) to see agent logs on stderr.

mod agent_builder;
mod cli;
mod nodes;
mod resolve;

use clap::Parser;
use tracing_subscriber::EnvFilter;

use omni_agent::{load_runtime_settings, set_config_home_override};

use crate::cli::{Cli, Command};
use crate::nodes::{
    ChannelCommandRequest, run_channel_command, run_gateway_mode, run_repl_mode, run_schedule_mode,
    run_stdio_mode,
};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    if let Some(conf_dir) = cli.conf.clone() {
        set_config_home_override(conf_dir);
    }
    let runtime_settings = load_runtime_settings();

    // Initialize tracing: RUST_LOG overrides; --verbose on channel => debug; else info
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| {
        let verbose = matches!(&cli.command, Command::Channel { verbose: true, .. });
        EnvFilter::new(if verbose {
            "omni_agent=debug"
        } else {
            "omni_agent=info"
        })
    });
    let _ = tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_writer(std::io::stderr)
        .try_init();

    match cli.command {
        Command::Gateway {
            bind,
            turn_timeout,
            max_concurrent,
            mcp_config,
        } => {
            run_gateway_mode(
                bind,
                turn_timeout,
                max_concurrent,
                mcp_config,
                &runtime_settings,
            )
            .await
        }
        Command::Stdio {
            session_id,
            mcp_config,
        } => run_stdio_mode(session_id, mcp_config, &runtime_settings).await,
        Command::Repl {
            query,
            session_id,
            mcp_config,
        } => run_repl_mode(query, session_id, mcp_config, &runtime_settings).await,
        Command::Schedule {
            prompt,
            interval_secs,
            max_runs,
            schedule_id,
            session_prefix,
            recipient,
            wait_for_completion_secs,
            mcp_config,
        } => {
            run_schedule_mode(
                prompt,
                interval_secs,
                max_runs,
                schedule_id,
                session_prefix,
                recipient,
                wait_for_completion_secs,
                mcp_config,
                &runtime_settings,
            )
            .await
        }
        Command::Channel {
            provider,
            bot_token,
            allowed_users,
            allowed_groups,
            allowed_guilds,
            admin_users,
            control_command_allow_from,
            admin_command_rules,
            slash_command_allow_from,
            slash_session_status_allow_from,
            slash_session_budget_allow_from,
            slash_session_memory_allow_from,
            slash_session_feedback_allow_from,
            slash_job_allow_from,
            slash_jobs_allow_from,
            slash_bg_allow_from,
            mcp_config,
            mode,
            webhook_bind,
            webhook_path,
            webhook_secret_token,
            ingress_bind,
            ingress_path,
            ingress_secret_token,
            session_partition,
            inbound_queue_capacity,
            turn_timeout_secs,
            webhook_dedup_backend,
            valkey_url,
            webhook_dedup_ttl_secs,
            webhook_dedup_key_prefix,
            verbose: _,
        } => {
            run_channel_command(
                ChannelCommandRequest {
                    provider,
                    bot_token,
                    allowed_users,
                    allowed_groups,
                    allowed_guilds,
                    admin_users,
                    control_command_allow_from,
                    admin_command_rules,
                    slash_command_allow_from,
                    slash_session_status_allow_from,
                    slash_session_budget_allow_from,
                    slash_session_memory_allow_from,
                    slash_session_feedback_allow_from,
                    slash_job_allow_from,
                    slash_jobs_allow_from,
                    slash_bg_allow_from,
                    mcp_config,
                    mode,
                    webhook_bind,
                    webhook_path,
                    webhook_secret_token,
                    ingress_bind,
                    ingress_path,
                    ingress_secret_token,
                    session_partition,
                    inbound_queue_capacity,
                    turn_timeout_secs,
                    webhook_dedup_backend,
                    valkey_url,
                    webhook_dedup_ttl_secs,
                    webhook_dedup_key_prefix,
                },
                &runtime_settings,
            )
            .await
        }
    }
}
