use std::sync::Arc;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::channels::traits::{Channel, ChannelMessage};

use super::{MockChannel, build_agent, build_job_manager, handle_inbound_message, inbound};

#[tokio::test]
async fn runtime_handle_inbound_session_injection_set_and_status_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session inject <qa><q>backend</q><a>valkey only</a></qa>"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/session inject status json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session inject command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(
        sent[0]
            .0
            .contains("Session system prompt injection updated.")
    );

    let payload: serde_json::Value = serde_json::from_str(&sent[1].0)?;
    assert_eq!(payload["kind"], "session_injection");
    assert_eq!(payload["configured"], true);
    assert_eq!(payload["qa_count"], 1);
    let xml = payload["xml"]
        .as_str()
        .expect("status xml should be present");
    assert!(xml.contains("<system_prompt_injection>"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_injection_clear_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session inject <qa><q>q</q><a>a</a></qa>"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/session inject clear json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/session inject status json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 3);
    let clear_payload: serde_json::Value = serde_json::from_str(&sent[1].0)?;
    assert_eq!(clear_payload["kind"], "session_injection");
    assert_eq!(clear_payload["cleared"], true);

    let status_payload: serde_json::Value = serde_json::from_str(&sent[2].0)?;
    assert_eq!(status_payload["kind"], "session_injection");
    assert_eq!(status_payload["configured"], false);
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_injection_invalid_payload() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session inject <qa><q>question_only</q></qa>"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("Invalid system prompt injection payload")
    );
    Ok(())
}
