use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use axum::http::StatusCode;
use tokio::sync::mpsc;

use crate::channels::telegram::TelegramChannel;
use crate::channels::telegram::idempotency::{WebhookDedupBackend, WebhookDedupConfig};
use crate::channels::traits::{Channel, ChannelMessage};

use super::{
    MockChannel, build_agent, build_job_manager, build_telegram_webhook_app,
    handle_inbound_message, post_webhook_update, sample_update,
    spawn_polling_command_mock_telegram_api,
};

#[tokio::test]
async fn runtime_webhook_update_drives_session_command_flow() -> Result<()> {
    let (inbound_tx, mut inbound_rx) = mpsc::channel::<ChannelMessage>(8);
    let webhook = build_telegram_webhook_app(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "/telegram/webhook",
        None,
        WebhookDedupConfig {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        },
        inbound_tx,
    )?;

    let reset_status = post_webhook_update(
        webhook.app.clone(),
        &webhook.path,
        sample_update(91001, "/reset"),
    )
    .await?;
    assert_eq!(reset_status, StatusCode::OK);

    let reset_message = tokio::time::timeout(Duration::from_millis(200), inbound_rx.recv())
        .await?
        .ok_or_else(|| anyhow::anyhow!("expected reset message from webhook queue"))?;
    assert_eq!(reset_message.content, "/reset");

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let session_id = format!("{}:{}", reset_message.channel, reset_message.session_key);
    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;

    assert!(
        handle_inbound_message(
            reset_message,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session command from webhook should not enter foreground queue"
    );

    let resume_status = post_webhook_update(
        webhook.app.clone(),
        &webhook.path,
        sample_update(91002, "/resume status"),
    )
    .await?;
    assert_eq!(resume_status, StatusCode::OK);

    let status_message = tokio::time::timeout(Duration::from_millis(200), inbound_rx.recv())
        .await?
        .ok_or_else(|| anyhow::anyhow!("expected resume status message from webhook queue"))?;
    assert_eq!(status_message.content, "/resume status");
    assert!(
        handle_inbound_message(
            status_message,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(sent[0].0.contains("Session context reset."));
    assert!(sent[0].0.contains("messages_cleared=4"));
    assert!(sent[1].0.contains("Saved session context snapshot:"));
    assert!(sent[1].0.contains("saved_age_secs="));
    Ok(())
}

#[tokio::test]
async fn runtime_polling_update_drives_session_command_flow() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_polling_command_mock_telegram_api().await? else {
        return Ok(());
    };

    let poll_channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let (poll_tx, mut poll_rx) = mpsc::channel::<ChannelMessage>(8);
    let listener = tokio::spawn(async move { poll_channel.listen(poll_tx).await });

    let reset_message = tokio::time::timeout(Duration::from_millis(400), poll_rx.recv())
        .await?
        .ok_or_else(|| anyhow::anyhow!("expected /reset from polling channel"))?;
    let status_message = tokio::time::timeout(Duration::from_millis(400), poll_rx.recv())
        .await?
        .ok_or_else(|| anyhow::anyhow!("expected /resume status from polling channel"))?;

    assert_eq!(reset_message.content, "/reset");
    assert_eq!(status_message.content, "/resume status");
    assert!(
        state
            .get_updates_calls
            .load(std::sync::atomic::Ordering::SeqCst)
            >= 1,
        "polling mock should receive getUpdates requests"
    );

    listener.abort();
    handle.abort();

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let session_id = format!("{}:{}", reset_message.channel, reset_message.session_key);
    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;

    assert!(
        handle_inbound_message(
            reset_message,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            status_message,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session commands from polling should not enter foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(sent[0].0.contains("Session context reset."));
    assert!(sent[0].0.contains("messages_cleared=4"));
    assert!(sent[1].0.contains("Saved session context snapshot:"));
    assert!(sent[1].0.contains("saved_age_secs="));
    Ok(())
}
