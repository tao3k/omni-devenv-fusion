use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::Mutex;
use tokio::sync::mpsc;

use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::config::{AgentConfig, MemoryConfig};

use super::{MockChannel, build_agent, build_job_manager, handle_inbound_message, inbound};

static NEXT_FEEDBACK_TEST_ID: AtomicU64 = AtomicU64::new(1);

#[derive(Clone)]
struct FeedbackTestSession {
    sender: String,
    recipient: String,
    session_key: String,
}

fn next_feedback_test_session() -> FeedbackTestSession {
    let id = NEXT_FEEDBACK_TEST_ID.fetch_add(1, Ordering::Relaxed);
    let sender = (900_000_000u64 + id).to_string();
    let recipient = format!("-{}", 800_000_000u64 + id);
    let session_key = format!("{recipient}:{sender}");
    FeedbackTestSession {
        sender,
        recipient,
        session_key,
    }
}

fn feedback_inbound(content: &str, session: &FeedbackTestSession) -> ChannelMessage {
    let message_id = NEXT_FEEDBACK_TEST_ID.fetch_add(1, Ordering::Relaxed);
    ChannelMessage {
        id: format!("feedback-test-message-{message_id}"),
        sender: session.sender.clone(),
        recipient: session.recipient.clone(),
        session_key: session.session_key.clone(),
        content: content.to_string(),
        channel: "telegram".to_string(),
        timestamp: 0,
    }
}

#[derive(Default)]
struct TelegramNamedMockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl TelegramNamedMockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for TelegramNamedMockChannel {
    fn name(&self) -> &str {
        "telegram"
    }

    fn is_admin_user(&self, _identity: &str) -> bool {
        true
    }

    async fn send(&self, message: &str, recipient: &str) -> Result<()> {
        self.sent
            .lock()
            .await
            .push((message.to_string(), recipient.to_string()));
        Ok(())
    }

    async fn listen(&self, _tx: mpsc::Sender<ChannelMessage>) -> Result<()> {
        Ok(())
    }
}

async fn build_memory_enabled_agent() -> Result<Arc<Agent>> {
    let temp_dir = tempfile::tempdir()?;
    let memory_path = temp_dir.path().join("memory");
    let config = AgentConfig {
        inference_url: "http://127.0.0.1:1/v1/chat/completions".to_string(),
        model: "gpt-4o-mini".to_string(),
        api_key: None,
        max_tool_rounds: 1,
        memory: Some(MemoryConfig {
            path: memory_path.to_string_lossy().to_string(),
            persistence_backend: "local".to_string(),
            ..MemoryConfig::default()
        }),
        ..AgentConfig::default()
    };
    Ok(Arc::new(Agent::from_config(config).await?))
}

#[tokio::test]
async fn runtime_handle_inbound_session_feedback_rejects_when_memory_disabled() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session feedback up"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session feedback command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("Session recall feedback is unavailable because memory is disabled."),
    );
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_feedback_updates_bias() -> Result<()> {
    let agent = build_memory_enabled_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session = next_feedback_test_session();

    assert!(
        handle_inbound_message(
            feedback_inbound("/session feedback up", &session),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            feedback_inbound("/feedback down", &session),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session feedback commands should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(sent[0].0.contains("Session recall feedback updated."));
    assert!(sent[0].0.contains("direction=up"));
    assert!(sent[0].0.contains("previous_bias=0.000"));
    assert!(sent[0].0.contains("updated_bias=0.150"));
    assert!(sent[1].0.contains("direction=down"));
    assert!(sent[1].0.contains("previous_bias=0.150"));
    assert!(sent[1].0.contains("updated_bias=-0.022"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_feedback_json() -> Result<()> {
    let agent = build_memory_enabled_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session = next_feedback_test_session();

    assert!(
        handle_inbound_message(
            feedback_inbound("/session feedback up json", &session),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session feedback json command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_feedback");
    assert_eq!(payload["applied"], true);
    assert_eq!(payload["direction"], "up");
    assert_eq!(payload["previous_bias"], 0.0);
    let updated = payload["updated_bias"]
        .as_f64()
        .expect("updated_bias should be numeric");
    assert!((updated - 0.15).abs() < 1e-6);
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_feedback_json_renders_markdown_code_block_for_telegram()
-> Result<()> {
    let agent = build_memory_enabled_agent().await?;
    let channel = Arc::new(TelegramNamedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session = next_feedback_test_session();

    assert!(
        handle_inbound_message(
            feedback_inbound("/session feedback up json", &session),
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
    assert!(sent[0].0.starts_with("```json\n"));
    assert!(sent[0].0.ends_with("\n```"));
    let payload = sent[0]
        .0
        .trim_start_matches("```json\n")
        .trim_end_matches("\n```");
    let parsed: serde_json::Value = serde_json::from_str(payload)?;
    assert_eq!(parsed["kind"], "session_feedback");
    assert_eq!(parsed["direction"], "up");
    Ok(())
}
