use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use anyhow::Result;
use async_trait::async_trait;
use axum::body::Body;
use axum::extract::State;
use axum::http::{Request, StatusCode};
use axum::routing::post;
use axum::{Json, Router};
use tokio::sync::{Mutex, mpsc};
use tower::util::ServiceExt;

use crate::agent::Agent;
use crate::channels::telegram::TelegramChannel;
use crate::channels::telegram::TelegramSessionPartition;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::config::AgentConfig;
use crate::jobs::{JobManager, JobManagerConfig};

use super::jobs::handle_inbound_message;
use super::webhook::build_telegram_webhook_app;

mod jobs_logging;
mod partition_modes;
mod session_admin;
mod session_budget;
mod session_control_admin;
mod session_feedback;
mod session_help;
mod session_injection;
mod session_jobs;
mod session_memory;
mod session_partition;
mod session_reset;
mod session_resume_flow;
mod session_slash_acl;
mod session_status;
mod transport_command_flow;
mod webhook_security;

#[derive(Default)]
struct MockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl MockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for MockChannel {
    fn name(&self) -> &str {
        "mock"
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

static NEXT_ID: AtomicU64 = AtomicU64::new(1);

fn next_message_id() -> String {
    let id = NEXT_ID.fetch_add(1, Ordering::Relaxed);
    format!("test-message-{id}")
}

fn next_numeric_id() -> i64 {
    NEXT_ID.fetch_add(1, Ordering::Relaxed) as i64
}

fn inbound(content: &str) -> ChannelMessage {
    ChannelMessage {
        id: next_message_id(),
        sender: "888".to_string(),
        recipient: "-200".to_string(),
        session_key: "-200:888".to_string(),
        content: content.to_string(),
        channel: "telegram".to_string(),
        timestamp: 0,
    }
}

fn sample_update(update_id: i64, text: &str) -> serde_json::Value {
    serde_json::json!({
        "update_id": update_id,
        "message": {
            "message_id": 77,
            "text": text,
            "chat": {"id": -200},
            "from": {"id": 888, "username": "alice"}
        }
    })
}

#[derive(Clone, Copy)]
struct SessionIdentity {
    chat_id: i64,
    user_id: i64,
    thread_id: Option<i64>,
}

fn partitioned_inbound_message(
    partition: TelegramSessionPartition,
    identity: SessionIdentity,
    text: &str,
) -> Result<ChannelMessage> {
    let channel = TelegramChannel::new_with_partition(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        partition,
    );
    let mut update = serde_json::json!({
        "update_id": next_numeric_id(),
        "message": {
            "message_id": next_numeric_id(),
            "text": text,
            "chat": {"id": identity.chat_id},
            "from": {"id": identity.user_id, "username": format!("u{}", identity.user_id)}
        }
    });
    if let Some(thread_id) = identity.thread_id {
        update["message"]["message_thread_id"] = serde_json::json!(thread_id);
    }
    channel
        .parse_update_message(&update)
        .ok_or_else(|| anyhow::anyhow!("failed to parse partitioned telegram update"))
}

#[derive(Clone)]
struct PollCommandMockState {
    get_updates_calls: Arc<std::sync::atomic::AtomicUsize>,
}

async fn handle_poll_get_updates(
    State(state): State<PollCommandMockState>,
) -> Json<serde_json::Value> {
    let call_index = state
        .get_updates_calls
        .fetch_add(1, std::sync::atomic::Ordering::SeqCst);

    if call_index == 0 {
        return Json(serde_json::json!({
            "ok": true,
            "result": [
                {
                    "update_id": 92001,
                    "message": {
                        "message_id": 701,
                        "text": "/reset",
                        "chat": {"id": -200},
                        "from": {"id": 888, "username": "alice"}
                    }
                },
                {
                    "update_id": 92002,
                    "message": {
                        "message_id": 702,
                        "text": "/resume status",
                        "chat": {"id": -200},
                        "from": {"id": 888, "username": "alice"}
                    }
                }
            ]
        }));
    }

    Json(serde_json::json!({
        "ok": true,
        "result": []
    }))
}

async fn handle_poll_send_chat_action() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "ok": true,
        "result": true
    }))
}

async fn spawn_polling_command_mock_telegram_api()
-> Result<Option<(String, PollCommandMockState, tokio::task::JoinHandle<()>)>> {
    let state = PollCommandMockState {
        get_updates_calls: Arc::new(std::sync::atomic::AtomicUsize::new(0)),
    };

    let app = Router::new()
        .route("/botfake-token/getUpdates", post(handle_poll_get_updates))
        .route(
            "/botfake-token/sendChatAction",
            post(handle_poll_send_chat_action),
        )
        .with_state(state.clone());
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping polling command runtime tests: local socket bind is not permitted");
            return Ok(None);
        }
        Err(err) => return Err(err.into()),
    };
    let addr = listener.local_addr()?;
    let handle = tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });

    Ok(Some((format!("http://{addr}"), state, handle)))
}

async fn post_webhook_update(
    app: axum::Router,
    path: &str,
    payload: serde_json::Value,
) -> Result<StatusCode> {
    let request = Request::builder()
        .method("POST")
        .uri(path)
        .header("content-type", "application/json")
        .body(Body::from(payload.to_string()))?;
    let response = app.oneshot(request).await?;
    Ok(response.status())
}

async fn build_agent() -> Result<Arc<Agent>> {
    let config = AgentConfig {
        inference_url: "https://api.openai.com/v1/chat/completions".to_string(),
        model: "gpt-4o-mini".to_string(),
        api_key: None,
        max_tool_rounds: 1,
        ..AgentConfig::default()
    };
    Ok(Arc::new(Agent::from_config(config).await?))
}

async fn build_agent_with_context_budget() -> Result<Arc<Agent>> {
    let config = AgentConfig {
        inference_url: "http://127.0.0.1:1/v1/chat/completions".to_string(),
        model: "gpt-4o-mini".to_string(),
        api_key: None,
        max_tool_rounds: 1,
        context_budget_tokens: Some(80),
        context_budget_reserve_tokens: 16,
        ..AgentConfig::default()
    };
    Ok(Arc::new(Agent::from_config(config).await?))
}

fn build_job_manager(runner: Arc<dyn crate::jobs::TurnRunner>) -> Arc<JobManager> {
    let (manager, _completion_rx) = JobManager::start(runner, JobManagerConfig::default());
    manager
}

async fn run_partition_reset_status_flow(
    partition: TelegramSessionPartition,
    reset_identity: SessionIdentity,
    status_identity: SessionIdentity,
    expect_shared_snapshot: bool,
) -> Result<()> {
    let reset_message = partitioned_inbound_message(partition, reset_identity, "/reset")?;
    let status_message = partitioned_inbound_message(partition, status_identity, "/resume status")?;

    let reset_session_id = format!("{}:{}", reset_message.channel, reset_message.session_key);
    let status_session_id = format!("{}:{}", status_message.channel, status_message.session_key);
    if expect_shared_snapshot {
        assert_eq!(
            reset_session_id, status_session_id,
            "expected shared partition to map into same logical session key"
        );
    } else {
        assert_ne!(
            reset_session_id, status_session_id,
            "expected isolated partition to map into different logical session keys"
        );
    }

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    agent
        .append_turn_for_session(&reset_session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&reset_session_id, "u2", "a2")
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
        "session commands should not enter foreground queue"
    );
    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(sent[0].0.contains("Session context reset."));
    assert!(sent[0].0.contains("messages_cleared=4"));
    if expect_shared_snapshot {
        assert!(sent[1].0.contains("Saved session context snapshot:"));
        assert!(sent[1].0.contains("messages=4"));
    } else {
        assert!(
            sent[1]
                .0
                .contains("No saved session context snapshot found.")
        );
    }
    Ok(())
}
