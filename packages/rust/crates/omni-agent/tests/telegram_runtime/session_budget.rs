use std::sync::Arc;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::channels::traits::{Channel, ChannelMessage};

use super::{
    MockChannel, build_agent, build_agent_with_context_budget, build_job_manager,
    handle_inbound_message, inbound,
};

#[tokio::test]
async fn runtime_handle_inbound_session_budget_without_snapshot() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session budget"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session budget command should not forward to foreground queue"
    );
    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("No context budget snapshot found for this session yet.")
    );
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_budget_without_snapshot_reports_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session budget json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session budget json command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_budget");
    assert_eq!(payload["available"], false);
    assert_eq!(payload["status"], "not_found");
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_budget_reports_latest_snapshot() -> Result<()> {
    let agent = build_agent_with_context_budget().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .append_turn_for_session(
            session_id,
            &"older user context ".repeat(60),
            "older assistant",
        )
        .await?;
    let _ = agent.run_turn(session_id, "latest request").await;

    assert!(
        handle_inbound_message(
            inbound("/session budget"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session budget command should not forward to foreground queue"
    );
    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("session-budget dashboard"));
    assert!(sent[0].0.contains("Overview:"));
    assert!(sent[0].0.contains("Classes:"));
    assert!(sent[0].0.contains("strategy=recent_first"));
    assert!(sent[0].0.contains("effective="));
    assert!(sent[0].0.contains("non_system"));
    assert!(sent[0].0.contains("summary_system"));
    assert!(sent[0].0.contains("Bottlenecks:"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_budget_reports_latest_snapshot_json() -> Result<()> {
    let agent = build_agent_with_context_budget().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .append_turn_for_session(
            session_id,
            &"older user context ".repeat(60),
            "older assistant",
        )
        .await?;
    let _ = agent.run_turn(session_id, "latest request").await;

    assert!(
        handle_inbound_message(
            inbound("/session budget json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session budget json command should not forward to foreground queue"
    );
    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_budget");
    assert_eq!(payload["available"], true);
    assert_eq!(payload["strategy"], "recent_first");
    assert!(payload["effective_budget_tokens"].as_u64().unwrap_or(0) > 0);
    assert!(
        payload["classes"]["non_system"]["input_tokens"]
            .as_u64()
            .is_some()
    );
    Ok(())
}
