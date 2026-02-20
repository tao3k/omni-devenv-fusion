#![allow(missing_docs)]

use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use axum::{Json, Router, extract::State, http::StatusCode, routing::post};
use omni_agent::{Channel, TelegramChannel};
use tokio::sync::Mutex;

#[test]
fn telegram_send_rate_limit_valkey_constructor_rejects_invalid_url() {
    let result = TelegramChannel::new_with_base_url_and_send_rate_limit_valkey_for_test(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        "http://127.0.0.1:18080".to_string(),
        "http://127.0.0.1:6379/0".to_string(),
        "omni-agent:test:send-gate:invalid-url".to_string(),
    );
    assert!(
        result.is_err(),
        "invalid redis url should fail fast for valkey send gate constructor"
    );
}

#[derive(Clone)]
struct TimedTelegramRequest {
    payload: serde_json::Value,
    received_at: Instant,
}

#[derive(Clone)]
struct RateLimitState {
    requests: Arc<Mutex<Vec<TimedTelegramRequest>>>,
    first_rate_limit_emitted: Arc<Mutex<bool>>,
}

async fn handle_send_message_rate_limit_once(
    State(state): State<RateLimitState>,
    Json(payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.requests.lock().await.push(TimedTelegramRequest {
        payload: payload.clone(),
        received_at: Instant::now(),
    });

    let text = payload
        .get("text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default();
    let mut emitted = state.first_rate_limit_emitted.lock().await;
    if text == "firstgatecheck" && !*emitted {
        *emitted = true;
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(serde_json::json!({
                "ok": false,
                "error_code": 429,
                "description": "Too Many Requests: retry later",
                "parameters": {
                    "retry_after": 1
                }
            })),
        );
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}

async fn spawn_mock_telegram_api()
-> Result<Option<(String, RateLimitState, tokio::task::JoinHandle<()>)>> {
    let state = RateLimitState {
        requests: Arc::new(Mutex::new(Vec::new())),
        first_rate_limit_emitted: Arc::new(Mutex::new(false)),
    };
    let app = Router::new()
        .route(
            "/botfake-token/sendMessage",
            post(handle_send_message_rate_limit_once),
        )
        .with_state(state.clone());
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping telegram send gate tests: local socket bind is not permitted");
            return Ok(None);
        }
        Err(err) => return Err(err.into()),
    };
    let addr = listener.local_addr()?;
    let handle = tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    wait_for_listener(addr).await;

    Ok(Some((format!("http://{addr}"), state, handle)))
}

async fn wait_for_listener(addr: std::net::SocketAddr) {
    for _ in 0..20 {
        if tokio::net::TcpStream::connect(addr).await.is_ok() {
            return;
        }
        tokio::time::sleep(Duration::from_millis(5)).await;
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
#[ignore = "requires live valkey server"]
async fn telegram_send_gate_valkey_enforces_cross_instance_rate_limit_window() -> Result<()> {
    let Some(valkey_url) = std::env::var("VALKEY_URL")
        .ok()
        .filter(|value| !value.trim().is_empty())
    else {
        eprintln!("skip: set VALKEY_URL for live telegram send gate test");
        return Ok(());
    };
    let key_prefix = format!(
        "omni-agent:test:telegram:send-gate:{}",
        SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros()
    );

    let Some((api_base, state, handle)) = spawn_mock_telegram_api().await? else {
        return Ok(());
    };

    let channel_a = TelegramChannel::new_with_base_url_and_send_rate_limit_valkey_for_test(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base.clone(),
        valkey_url.clone(),
        key_prefix.clone(),
    )?;
    let channel_b = TelegramChannel::new_with_base_url_and_send_rate_limit_valkey_for_test(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
        valkey_url,
        key_prefix,
    )?;

    let first_send = tokio::spawn(async move { channel_a.send("firstgatecheck", "123456").await });

    for _ in 0..50 {
        if *state.first_rate_limit_emitted.lock().await {
            break;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }

    let second_started_at = Instant::now();
    let second_send =
        tokio::spawn(async move { channel_b.send("crossinstancecheck", "123456").await });

    first_send.await??;
    second_send.await??;

    let requests = state.requests.lock().await;
    let second_request_at = requests
        .iter()
        .find_map(|request| {
            (request
                .payload
                .get("text")
                .and_then(serde_json::Value::as_str)
                == Some("crossinstancecheck"))
            .then_some(request.received_at)
        })
        .expect("cross-instance request should be recorded");
    let wait_duration = second_request_at.duration_since(second_started_at);
    assert!(
        wait_duration >= Duration::from_millis(850),
        "cross-instance send should respect distributed rate-limit window, got {}ms",
        wait_duration.as_millis()
    );

    handle.abort();
    Ok(())
}
