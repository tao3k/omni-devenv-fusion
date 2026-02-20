use std::sync::Arc;

use anyhow::Result;

use crate::channels::traits::Channel;

use super::support::{
    MockChannel, build_agent, inbound, process_discord_message, start_job_manager,
};

#[tokio::test]
async fn process_discord_message_handles_help_json_without_llm_turn() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(agent, channel_dyn, inbound("/help json"), &job_manager, 10).await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("\"kind\":\"slash_help\""));
    Ok(())
}

#[tokio::test]
async fn process_discord_message_handles_partition_command_and_updates_mode() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session partition channel"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("Session partition updated."));
    assert_eq!(channel.partition_mode().await, "channel");
    Ok(())
}

#[tokio::test]
async fn process_discord_message_partition_toggle_aliases_use_expected_modes() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent.clone(),
        channel_dyn.clone(),
        inbound("/session partition on"),
        &job_manager,
        10,
    )
    .await;
    assert_eq!(channel.partition_mode().await, "channel");

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session partition off"),
        &job_manager,
        10,
    )
    .await;
    assert_eq!(channel.partition_mode().await, "guild_channel_user");

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(
        sent.iter()
            .all(|(body, _)| body.contains("Session partition updated."))
    );
    Ok(())
}

#[tokio::test]
async fn process_discord_message_partition_chat_aliases_map_to_expected_modes() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent.clone(),
        channel_dyn.clone(),
        inbound("/session partition chat"),
        &job_manager,
        10,
    )
    .await;
    assert_eq!(channel.partition_mode().await, "channel");

    process_discord_message(
        agent.clone(),
        channel_dyn.clone(),
        inbound("/session partition chat_user"),
        &job_manager,
        10,
    )
    .await;
    assert_eq!(channel.partition_mode().await, "guild_channel_user");

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session partition topic_user"),
        &job_manager,
        10,
    )
    .await;
    assert_eq!(channel.partition_mode().await, "guild_channel_user");

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 3);
    assert!(
        sent.iter()
            .all(|(body, _)| body.contains("Session partition updated."))
    );
    Ok(())
}

#[tokio::test]
async fn process_discord_message_partition_status_json_reports_supported_modes() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session partition json"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_partition");
    assert_eq!(payload["updated"], false);
    assert_eq!(payload["current_mode"], "guild_channel_user");
    assert_eq!(
        payload["supported_modes"],
        serde_json::json!(["guild_channel_user", "channel", "user", "guild_user"])
    );
    assert_eq!(payload["quick_toggle"], "/session partition on|off");
    Ok(())
}

#[tokio::test]
async fn process_discord_message_resume_status_is_allowed_for_non_admin() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(false, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/resume status"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("No saved session context snapshot found.")
    );
    assert!(!sent[0].0.contains("Permission Denied"));
    Ok(())
}

#[tokio::test]
async fn process_discord_message_handles_background_submit_ack() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/bg collect incident summary"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("Queued background job `job-"));
    assert!(sent[0].0.contains("Use `/job "));
    Ok(())
}

#[tokio::test]
async fn process_discord_message_session_memory_includes_gate_policy_in_text() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session memory"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("`gate_promote_threshold=-`"));
    assert!(sent[0].0.contains("`gate_obsolete_threshold=-`"));
    Ok(())
}

#[tokio::test]
async fn process_discord_message_session_memory_json_includes_gate_policy_fields() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session memory json"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_memory");
    assert!(payload["runtime"]["gate_promote_threshold"].is_null());
    assert!(payload["runtime"]["gate_obsolete_threshold"].is_null());
    assert!(payload["runtime"]["gate_promote_min_usage"].is_null());
    assert!(payload["runtime"]["gate_obsolete_min_usage"].is_null());
    Ok(())
}
