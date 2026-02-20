use std::sync::Arc;

use anyhow::Result;
use tokio::net::TcpListener;
use tokio::sync::mpsc;

use super::super::channel::DiscordControlCommandPolicy;
use super::DiscordRuntimeConfig;
use super::dispatch::process_discord_message;
use super::ingress::{
    DiscordIngressApp, build_discord_ingress_app_with_partition_and_control_command_policy,
};
use super::managed::push_background_completion;
use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::jobs::{JobManager, JobManagerConfig, TurnRunner};

/// Run Discord channel via HTTP ingress endpoint.
pub async fn run_discord_ingress(
    agent: Arc<Agent>,
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_guilds: Vec<String>,
    control_command_policy: DiscordControlCommandPolicy,
    bind_addr: &str,
    ingress_path: &str,
    secret_token: Option<String>,
    runtime_config: DiscordRuntimeConfig,
) -> Result<()> {
    let inbound_queue_capacity = runtime_config.inbound_queue_capacity;
    let turn_timeout_secs = runtime_config.turn_timeout_secs;

    let (tx, mut inbound_rx) = mpsc::channel::<ChannelMessage>(inbound_queue_capacity);
    let runner: Arc<dyn TurnRunner> = agent.clone();
    let (job_manager, mut completion_rx) = JobManager::start(runner, JobManagerConfig::default());
    let ingress = build_discord_ingress_app_with_partition_and_control_command_policy(
        bot_token,
        allowed_users,
        allowed_guilds,
        control_command_policy,
        ingress_path,
        secret_token,
        runtime_config.session_partition,
        tx,
    )?;
    let DiscordIngressApp { app, channel, path } = ingress;
    let channel_for_send: Arc<dyn Channel> = channel.clone();
    let listener = TcpListener::bind(bind_addr).await?;

    let (shutdown_tx, shutdown_rx) = tokio::sync::oneshot::channel::<()>();
    let mut ingress_server = tokio::spawn(async move {
        axum::serve(listener, app)
            .with_graceful_shutdown(async {
                let _ = shutdown_rx.await;
            })
            .await
    });

    println!(
        "Discord ingress listening on {}{} (Ctrl+C to stop)",
        bind_addr, path
    );
    println!("Discord session partition: {}", channel.session_partition());
    println!(
        "Discord foreground config: inbound_queue={} timeout={}s",
        inbound_queue_capacity, turn_timeout_secs
    );
    println!("Background commands: /bg <prompt>, /job <id> [json], /jobs [json]");
    println!(
        "Session commands: /help [json], /session [json], /session budget [json], /session memory [json], /session feedback up|down [json], /session partition [mode|on|off] [json], /feedback up|down [json], /reset, /clear, /resume, /resume drop"
    );

    loop {
        tokio::select! {
            maybe_msg = inbound_rx.recv() => {
                let Some(msg) = maybe_msg else {
                    break;
                };
                process_discord_message(
                    Arc::clone(&agent),
                    Arc::clone(&channel_for_send),
                    msg,
                    &job_manager,
                    turn_timeout_secs,
                ).await;
            }
            maybe_completion = completion_rx.recv() => {
                let Some(completion) = maybe_completion else {
                    continue;
                };
                push_background_completion(&channel_for_send, completion).await;
            }
            _ = tokio::signal::ctrl_c() => {
                println!("Shutting down...");
                break;
            }
            result = &mut ingress_server => {
                match result {
                    Ok(Ok(())) => tracing::warn!("discord ingress server exited"),
                    Ok(Err(error)) => tracing::error!("discord ingress server failed: {error}"),
                    Err(error) => tracing::error!("discord ingress task join error: {error}"),
                }
                break;
            }
        }
    }

    let _ = shutdown_tx.send(());
    Ok(())
}
