#![allow(missing_docs)]

use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use axum::{
    Json, Router,
    extract::{Path, State},
    http::StatusCode,
    routing::post,
};
use omni_agent::{Channel, DISCORD_MAX_MESSAGE_LENGTH, DiscordChannel, split_message_for_discord};
use tokio::sync::Mutex;

#[derive(Clone, Default)]
struct MockDiscordState {
    sent: Arc<Mutex<Vec<(String, String)>>>,
    typing: Arc<Mutex<Vec<String>>>,
}

async fn handle_send_message(
    State(state): State<MockDiscordState>,
    Path(channel_id): Path<String>,
    Json(payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    let content = payload
        .get("content")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default()
        .to_string();
    state.sent.lock().await.push((channel_id, content));
    (
        StatusCode::OK,
        Json(serde_json::json!({"id": "message-1", "ok": true})),
    )
}

async fn handle_typing(
    State(state): State<MockDiscordState>,
    Path(channel_id): Path<String>,
) -> StatusCode {
    state.typing.lock().await.push(channel_id);
    StatusCode::NO_CONTENT
}

async fn spawn_mock_discord_api()
-> Result<Option<(String, MockDiscordState, tokio::task::JoinHandle<()>)>> {
    let state = MockDiscordState::default();
    let app = Router::new()
        .route("/channels/{channel_id}/messages", post(handle_send_message))
        .route("/channels/{channel_id}/typing", post(handle_typing))
        .with_state(state.clone());

    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping discord send tests: local socket bind is not permitted");
            return Ok(None);
        }
        Err(err) => return Err(err.into()),
    };
    let addr = listener.local_addr()?;
    let handle = tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });

    tokio::time::sleep(Duration::from_millis(40)).await;
    Ok(Some((format!("http://{addr}"), state, handle)))
}

#[tokio::test]
async fn discord_send_posts_single_message() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_discord_api().await? else {
        return Ok(());
    };

    let channel = DiscordChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    channel.send("hello", "2001").await?;

    let sent = state.sent.lock().await.clone();
    assert_eq!(sent.len(), 1);
    assert_eq!(sent[0], ("2001".to_string(), "hello".to_string()));

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn discord_send_splits_long_message_without_loss() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_discord_api().await? else {
        return Ok(());
    };

    let channel = DiscordChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let long_text = format!(
        "{}{}{}",
        "头".repeat(DISCORD_MAX_MESSAGE_LENGTH - 1),
        "尾",
        "emoji🙂".repeat(20)
    );
    channel.send(&long_text, "2001").await?;

    let sent = state.sent.lock().await.clone();
    assert!(sent.len() >= 2);
    let reconstructed = sent
        .iter()
        .map(|(_, content)| content.as_str())
        .collect::<String>();
    assert_eq!(reconstructed, long_text);
    assert!(
        sent.iter()
            .all(|(_, content)| content.chars().count() <= DISCORD_MAX_MESSAGE_LENGTH)
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn discord_start_typing_calls_typing_endpoint() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_discord_api().await? else {
        return Ok(());
    };

    let channel = DiscordChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    channel.start_typing("2001").await?;

    let typing = state.typing.lock().await.clone();
    assert_eq!(typing, vec!["2001".to_string()]);

    handle.abort();
    Ok(())
}

#[test]
fn split_message_for_discord_handles_zero_limit() {
    assert!(split_message_for_discord("abc", 0).is_empty());
}
