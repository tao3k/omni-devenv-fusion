#![allow(missing_docs)]

use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;

use anyhow::Result;
use axum::{Json, Router, extract::State, routing::post};
use omni_agent::{Channel, TelegramChannel};

#[derive(Clone, Copy)]
enum PollScenario {
    Unauthorized,
    ConflictThenMessage,
    RateLimitedThenMessage,
}

#[derive(Clone)]
struct PollMockState {
    scenario: PollScenario,
    get_updates_calls: Arc<AtomicUsize>,
}

async fn handle_get_updates(State(state): State<PollMockState>) -> Json<serde_json::Value> {
    let call_index = state.get_updates_calls.fetch_add(1, Ordering::SeqCst);

    match state.scenario {
        PollScenario::Unauthorized => Json(serde_json::json!({
            "ok": false,
            "error_code": 401,
            "description": "Unauthorized"
        })),
        PollScenario::ConflictThenMessage => {
            if call_index == 0 {
                Json(serde_json::json!({
                    "ok": false,
                    "error_code": 409,
                    "description": "Conflict: terminated by other getUpdates request"
                }))
            } else {
                Json(serde_json::json!({
                    "ok": true,
                    "result": [{
                        "update_id": 10001,
                        "message": {
                            "message_id": 77,
                            "text": "hello",
                            "chat": {"id": 123456},
                            "from": {"id": 888, "username": "alice"}
                        }
                    }]
                }))
            }
        }
        PollScenario::RateLimitedThenMessage => {
            if call_index == 0 {
                Json(serde_json::json!({
                    "ok": false,
                    "error_code": 429,
                    "description": "Too Many Requests: retry later",
                    "parameters": {
                        "retry_after": 1
                    }
                }))
            } else {
                Json(serde_json::json!({
                    "ok": true,
                    "result": [{
                        "update_id": 10002,
                        "message": {
                            "message_id": 78,
                            "text": "hello after rate limit",
                            "chat": {"id": 123456},
                            "from": {"id": 888, "username": "alice"}
                        }
                    }]
                }))
            }
        }
    }
}

async fn handle_send_chat_action() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "ok": true,
        "result": true
    }))
}

async fn spawn_polling_mock_telegram_api(
    scenario: PollScenario,
) -> Result<Option<(String, PollMockState, tokio::task::JoinHandle<()>)>> {
    let state = PollMockState {
        scenario,
        get_updates_calls: Arc::new(AtomicUsize::new(0)),
    };

    let app = Router::new()
        .route("/botfake-token/getUpdates", post(handle_get_updates))
        .route(
            "/botfake-token/sendChatAction",
            post(handle_send_chat_action),
        )
        .with_state(state.clone());
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping telegram polling tests: local socket bind is not permitted");
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

#[tokio::test]
async fn telegram_listen_fails_fast_on_unauthorized_get_updates() -> Result<()> {
    let Some((api_base, _state, handle)) =
        spawn_polling_mock_telegram_api(PollScenario::Unauthorized).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let (tx, _rx) = tokio::sync::mpsc::channel(1);

    let result = tokio::time::timeout(Duration::from_secs(2), channel.listen(tx))
        .await
        .expect("listen should complete");
    let error = result.expect_err("unauthorized getUpdates should fail fast");
    assert!(error.to_string().contains("401"));

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_listen_recovers_from_conflict_and_keeps_processing() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_polling_mock_telegram_api(PollScenario::ConflictThenMessage).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let (tx, rx) = tokio::sync::mpsc::channel(1);
    drop(rx);

    let result = tokio::time::timeout(Duration::from_secs(4), channel.listen(tx))
        .await
        .expect("listen should complete");
    assert!(result.is_ok());
    assert!(
        state.get_updates_calls.load(Ordering::SeqCst) >= 2,
        "listener should keep polling after 409 conflict"
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_listen_respects_retry_after_on_rate_limit() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_polling_mock_telegram_api(PollScenario::RateLimitedThenMessage).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );
    let (tx, rx) = tokio::sync::mpsc::channel(1);
    drop(rx);

    let start = std::time::Instant::now();
    let result = tokio::time::timeout(Duration::from_secs(5), channel.listen(tx))
        .await
        .expect("listen should complete");
    assert!(result.is_ok());
    assert!(
        start.elapsed() >= Duration::from_secs(1),
        "listener should honor retry_after for 429 responses"
    );
    assert!(
        state.get_updates_calls.load(Ordering::SeqCst) >= 2,
        "listener should continue polling after 429"
    );

    handle.abort();
    Ok(())
}
