use std::sync::Arc;

use anyhow::Result;

use super::super::console::{print_foreground_config, print_managed_commands_help};
use super::super::dispatch::start_telegram_runtime;
use super::super::webhook::build_telegram_webhook_app_with_control_command_policy;
use super::loop_control;
use super::secret;
use super::server;
use crate::agent::Agent;
use crate::channels::telegram::TelegramControlCommandPolicy;
use crate::channels::telegram::idempotency::WebhookDedupConfig;
use crate::channels::telegram::runtime_config::TelegramRuntimeConfig;
use crate::channels::traits::Channel;

/// Run Telegram channel via webhook (recommended for multi-instance deployments).
pub async fn run_telegram_webhook(
    agent: Arc<Agent>,
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    admin_users: Vec<String>,
    control_command_allow_from: Option<Vec<String>>,
    admin_command_rule_specs: Vec<String>,
    bind_addr: &str,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
) -> Result<()> {
    run_telegram_webhook_with_control_command_policy(
        agent,
        bot_token,
        allowed_users,
        allowed_groups,
        TelegramControlCommandPolicy::new(
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
        ),
        bind_addr,
        webhook_path,
        secret_token,
        dedup_config,
    )
    .await
}

/// Run Telegram channel via webhook with structured control-command policy.
pub async fn run_telegram_webhook_with_control_command_policy(
    agent: Arc<Agent>,
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    control_command_policy: TelegramControlCommandPolicy,
    bind_addr: &str,
    webhook_path: &str,
    secret_token: Option<String>,
    dedup_config: WebhookDedupConfig,
) -> Result<()> {
    let secret_token = secret::normalize_secret_token(secret_token)?;
    let runtime_config = TelegramRuntimeConfig::from_env();
    let (tx, mut inbound_rx) = tokio::sync::mpsc::channel(runtime_config.inbound_queue_capacity);
    let webhook = build_telegram_webhook_app_with_control_command_policy(
        bot_token,
        allowed_users,
        allowed_groups,
        control_command_policy,
        webhook_path,
        Some(secret_token),
        dedup_config,
        tx,
    )?;
    let channel_for_send: Arc<dyn Channel> = webhook.channel.clone();
    let session_partition = webhook.channel.session_partition();
    let path = webhook.path;
    let dedup_config = webhook.dedup_config;
    let app = webhook.app;

    let mut webhook_server = server::start_webhook_server(bind_addr, app).await?;

    let (
        session_gate_backend,
        foreground_tx,
        foreground_dispatcher,
        job_manager,
        mut completion_rx,
    ) = start_telegram_runtime(
        Arc::clone(&agent),
        Arc::clone(&channel_for_send),
        runtime_config,
    )?;

    println!(
        "Telegram webhook listening on {}{} (Ctrl+C to stop)",
        bind_addr, path
    );
    println!(
        "Webhook dedup backend: {} (ttl={}s)",
        dedup_config.backend_name(),
        dedup_config.ttl_secs
    );
    println!("Session partition: {}", session_partition.to_string());
    print_foreground_config(&runtime_config, &session_gate_backend);
    print_managed_commands_help();

    loop_control::run_webhook_event_loop(
        &mut inbound_rx,
        &mut completion_rx,
        &channel_for_send,
        &foreground_tx,
        &job_manager,
        &agent,
        &mut webhook_server.task,
    )
    .await;

    server::stop_webhook_server(webhook_server).await;
    drop(foreground_tx);
    foreground_dispatcher.abort();
    Ok(())
}
