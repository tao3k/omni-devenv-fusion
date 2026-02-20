use std::sync::Arc;

use anyhow::Result;

use super::super::console::{print_foreground_config, print_managed_commands_help};
use super::super::dispatch::start_telegram_runtime;
use super::channel_listener;
use super::loop_control;
use crate::agent::Agent;
use crate::channels::telegram::TelegramControlCommandPolicy;
use crate::channels::telegram::runtime_config::TelegramRuntimeConfig;

/// Run Telegram channel via long polling.
pub async fn run_telegram(
    agent: Arc<Agent>,
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    admin_users: Vec<String>,
    control_command_allow_from: Option<Vec<String>>,
    admin_command_rule_specs: Vec<String>,
) -> Result<()> {
    run_telegram_with_control_command_policy(
        agent,
        bot_token,
        allowed_users,
        allowed_groups,
        TelegramControlCommandPolicy::new(
            admin_users,
            control_command_allow_from,
            admin_command_rule_specs,
        ),
    )
    .await
}

/// Run Telegram channel via long polling with structured control-command policy.
pub async fn run_telegram_with_control_command_policy(
    agent: Arc<Agent>,
    bot_token: String,
    allowed_users: Vec<String>,
    allowed_groups: Vec<String>,
    control_command_policy: TelegramControlCommandPolicy,
) -> Result<()> {
    let runtime_config = TelegramRuntimeConfig::from_env();
    let (channel, channel_for_send, mut inbound_rx, listener) =
        channel_listener::start_polling_listener(
            bot_token,
            allowed_users,
            allowed_groups,
            control_command_policy,
            runtime_config.inbound_queue_capacity,
        )?;

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

    println!("Telegram channel listening... (polling, Ctrl+C to stop)");
    println!(
        "Session partition: {}",
        channel.session_partition().to_string()
    );
    print_foreground_config(&runtime_config, &session_gate_backend);
    print_managed_commands_help();

    loop_control::run_polling_event_loop(
        &mut inbound_rx,
        &mut completion_rx,
        &channel_for_send,
        &foreground_tx,
        &job_manager,
        &agent,
    )
    .await;

    drop(foreground_tx);
    foreground_dispatcher.abort();
    listener.abort();
    Ok(())
}
