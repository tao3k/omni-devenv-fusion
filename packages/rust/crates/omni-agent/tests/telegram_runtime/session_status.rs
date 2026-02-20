use std::sync::Arc;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::channels::traits::{Channel, ChannelMessage};

use super::{MockChannel, build_agent, build_job_manager, handle_inbound_message, inbound};

#[tokio::test]
async fn runtime_handle_inbound_session_status_reports_active_and_saved_snapshot() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .append_turn_for_session(session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(session_id, "u2", "a2")
        .await?;

    assert!(
        handle_inbound_message(
            inbound("/session status"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/reset"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/session"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );

    assert!(
        foreground_rx.try_recv().is_err(),
        "session commands should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 3);
    assert!(sent[0].0.contains("session-context dashboard"));
    assert!(sent[0].0.contains("Overview:"));
    assert!(sent[0].0.contains("Active:"));
    assert!(sent[0].0.contains("Saved Snapshot:"));
    assert!(sent[0].0.contains("logical_session_id=telegram:-200:888"));
    assert!(sent[0].0.contains("partition_key=-200:888"));
    assert!(sent[0].0.contains("partition_mode=unknown"));
    assert!(sent[0].0.contains("mode=unbounded"));
    assert!(sent[0].0.contains("messages=4"));
    assert!(sent[0].0.contains("status=none"));
    assert!(sent[1].0.contains("Session context reset."));
    assert!(sent[2].0.contains("session-context dashboard"));
    assert!(sent[2].0.contains("Overview:"));
    assert!(sent[2].0.contains("Active:"));
    assert!(sent[2].0.contains("Saved Snapshot:"));
    assert!(sent[2].0.contains("logical_session_id=telegram:-200:888"));
    assert!(sent[2].0.contains("partition_key=-200:888"));
    assert!(sent[2].0.contains("partition_mode=unknown"));
    assert!(sent[2].0.contains("mode=unbounded"));
    assert!(sent[2].0.contains("messages=0"));
    assert!(sent[2].0.contains("status=available"));
    assert!(sent[2].0.contains("saved_messages=4"));
    assert!(sent[2].0.contains("restore_hint=/resume"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_status_reports_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .append_turn_for_session(session_id, "u1", "a1")
        .await?;

    assert!(
        handle_inbound_message(
            inbound("/session json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session json command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_context");
    assert_eq!(payload["logical_session_id"], "telegram:-200:888");
    assert_eq!(payload["partition_key"], "-200:888");
    assert_eq!(payload["mode"], "unbounded");
    assert_eq!(payload["active"]["messages"], 2);
    assert_eq!(payload["saved_snapshot"]["status"], "none");
    Ok(())
}
