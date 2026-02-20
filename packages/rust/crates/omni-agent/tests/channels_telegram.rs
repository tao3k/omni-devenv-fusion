#![allow(missing_docs)]

use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::Result;
use axum::{Json, Router, extract::State, http::StatusCode, routing::post};
use omni_agent::{
    Channel, TELEGRAM_MAX_MESSAGE_LENGTH, TelegramChannel, TelegramSessionPartition,
    decorate_chunk_for_telegram, split_message_for_telegram,
};
use tokio::sync::Mutex;

#[test]
fn telegram_channel_name() {
    let ch = TelegramChannel::new("fake-token".into(), vec!["*".into()], vec![]);
    assert_eq!(ch.name(), "telegram");
}

#[derive(Clone, Default)]
struct MockTelegramState {
    requests: Arc<Mutex<Vec<serde_json::Value>>>,
    first_markdown_error: Arc<Mutex<Option<String>>>,
}

async fn handle_send_message(
    State(state): State<MockTelegramState>,
    Json(payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.requests.lock().await.push(payload.clone());
    let parse_mode = payload
        .get("parse_mode")
        .and_then(serde_json::Value::as_str);
    if parse_mode == Some("MarkdownV2") {
        let mut first_markdown_error = state.first_markdown_error.lock().await;
        if let Some(description) = first_markdown_error.take() {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({
                    "ok": false,
                    "description": description
                })),
            );
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}

async fn spawn_mock_telegram_api(
    first_markdown_error: Option<&str>,
) -> Result<Option<(String, MockTelegramState, tokio::task::JoinHandle<()>)>> {
    let state = MockTelegramState {
        requests: Arc::new(Mutex::new(Vec::new())),
        first_markdown_error: Arc::new(Mutex::new(
            first_markdown_error.map(std::string::ToString::to_string),
        )),
    };

    let app = Router::new()
        .route("/botfake-token/sendMessage", post(handle_send_message))
        .with_state(state.clone());
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping telegram mock api tests: local socket bind is not permitted");
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

#[derive(Clone, Default)]
struct MockTelegramApiLevelErrorState {
    requests: Arc<Mutex<Vec<serde_json::Value>>>,
    first_markdown_error: Arc<Mutex<Option<String>>>,
}

async fn handle_send_message_api_level_error(
    State(state): State<MockTelegramApiLevelErrorState>,
    Json(payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.requests.lock().await.push(payload.clone());
    let parse_mode = payload
        .get("parse_mode")
        .and_then(serde_json::Value::as_str);

    if parse_mode == Some("MarkdownV2") {
        let mut first_markdown_error = state.first_markdown_error.lock().await;
        if let Some(description) = first_markdown_error.take() {
            return (
                StatusCode::OK,
                Json(serde_json::json!({
                    "ok": false,
                    "error_code": 400,
                    "description": description
                })),
            );
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}

async fn spawn_mock_telegram_api_level_error(
    first_markdown_error: Option<&str>,
) -> Result<
    Option<(
        String,
        MockTelegramApiLevelErrorState,
        tokio::task::JoinHandle<()>,
    )>,
> {
    let state = MockTelegramApiLevelErrorState {
        requests: Arc::new(Mutex::new(Vec::new())),
        first_markdown_error: Arc::new(Mutex::new(
            first_markdown_error.map(std::string::ToString::to_string),
        )),
    };

    let app = Router::new()
        .route(
            "/botfake-token/sendMessage",
            post(handle_send_message_api_level_error),
        )
        .with_state(state.clone());
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping telegram mock api tests: local socket bind is not permitted");
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

#[derive(Clone)]
struct DelayedSendState {
    delay: Duration,
}

async fn handle_delayed_send_message(
    State(state): State<DelayedSendState>,
    Json(_payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    tokio::time::sleep(state.delay).await;
    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}

async fn spawn_delayed_send_mock_telegram_api(
    delay: Duration,
) -> Result<Option<(String, tokio::task::JoinHandle<()>)>> {
    let app = Router::new()
        .route(
            "/botfake-token/sendMessage",
            post(handle_delayed_send_message),
        )
        .with_state(DelayedSendState { delay });
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping telegram mock api tests: local socket bind is not permitted");
            return Ok(None);
        }
        Err(err) => return Err(err.into()),
    };
    let addr = listener.local_addr()?;
    let handle = tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    wait_for_listener(addr).await;

    Ok(Some((format!("http://{addr}"), handle)))
}

#[derive(Clone)]
struct RetryThenSuccessState {
    requests: Arc<Mutex<Vec<serde_json::Value>>>,
    remaining_failures: Arc<Mutex<usize>>,
}

async fn handle_send_message_retry_then_success(
    State(state): State<RetryThenSuccessState>,
    Json(payload): Json<serde_json::Value>,
) -> (StatusCode, Json<serde_json::Value>) {
    state.requests.lock().await.push(payload);

    let mut remaining = state.remaining_failures.lock().await;
    if *remaining > 0 {
        *remaining -= 1;
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(serde_json::json!({
                "ok": false,
                "error_code": 429,
                "description": "Too Many Requests: retry later",
                "parameters": {
                    "retry_after": 0
                }
            })),
        );
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({"ok": true, "result": {"message_id": 1}})),
    )
}

async fn spawn_retry_then_success_mock_telegram_api(
    failures_before_success: usize,
) -> Result<Option<(String, RetryThenSuccessState, tokio::task::JoinHandle<()>)>> {
    let state = RetryThenSuccessState {
        requests: Arc::new(Mutex::new(Vec::new())),
        remaining_failures: Arc::new(Mutex::new(failures_before_success)),
    };
    let app = Router::new()
        .route(
            "/botfake-token/sendMessage",
            post(handle_send_message_retry_then_success),
        )
        .with_state(state.clone());
    let listener = match tokio::net::TcpListener::bind("127.0.0.1:0").await {
        Ok(listener) => listener,
        Err(err) if err.kind() == std::io::ErrorKind::PermissionDenied => {
            eprintln!("skipping telegram mock api tests: local socket bind is not permitted");
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

#[derive(Clone)]
struct TimedTelegramRequest {
    payload: serde_json::Value,
    received_at: Instant,
}

#[derive(Clone)]
struct RateLimitGateState {
    requests: Arc<Mutex<Vec<TimedTelegramRequest>>>,
    first_rate_limit_emitted: Arc<Mutex<bool>>,
}

async fn handle_send_message_rate_limit_once(
    State(state): State<RateLimitGateState>,
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

async fn spawn_rate_limit_gate_mock_telegram_api()
-> Result<Option<(String, RateLimitGateState, tokio::task::JoinHandle<()>)>> {
    let state = RateLimitGateState {
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
            eprintln!("skipping telegram mock api tests: local socket bind is not permitted");
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

#[test]
fn telegram_parse_update_builds_group_chat_session_key_by_default() {
    let ch = TelegramChannel::new("t".into(), vec!["*".into()], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.recipient, "-200123");
    assert_eq!(msg.sender, "888");
    assert_eq!(msg.session_key, "-200123");
    assert_eq!(msg.content, "hello");
}

#[test]
fn telegram_parse_update_rejects_unauthorized_user() {
    let ch = TelegramChannel::new("t".into(), vec!["999".into()], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    assert!(ch.parse_update_message(&update).is_none());
}

#[test]
fn telegram_parse_update_rejects_all_when_allowlist_empty() {
    let ch = TelegramChannel::new("t".into(), vec![], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    assert!(ch.parse_update_message(&update).is_none());
}

#[test]
fn telegram_parse_update_allows_numeric_user_id_in_allowlist() {
    let ch = TelegramChannel::new("t".into(), vec!["888".into()], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.sender, "888");
}

#[test]
fn telegram_parse_update_allows_prefixed_numeric_user_id_in_allowlist() {
    let ch = TelegramChannel::new("t".into(), vec!["telegram:888".into()], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.sender, "888");
}

#[test]
fn telegram_parse_update_rejects_username_allowlist_entries() {
    let ch = TelegramChannel::new("t".into(), vec!["@alice".into()], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    assert!(ch.parse_update_message(&update).is_none());
}

#[test]
fn telegram_parse_update_ignores_invalid_allowlist_entries_and_keeps_numeric_entries() {
    let ch = TelegramChannel::new("t".into(), vec!["@alice".into(), "888".into()], vec![]);
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.sender, "888");
}

#[test]
fn telegram_parse_update_trims_allowlist_entries() {
    let ch = TelegramChannel::new(
        "t".into(),
        vec!["  tg:888  ".into(), " 888 ".into()],
        vec![],
    );
    let update = serde_json::json!({
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "text": "hello",
            "chat": {"id": -200123},
            "from": {"id": 888, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.sender, "888");
}

#[test]
fn telegram_parse_update_allows_message_from_allowed_group() {
    let ch = TelegramChannel::new("t".into(), vec![], vec!["-200123".into()]);
    let update = serde_json::json!({
        "update_id": 10002,
        "message": {
            "message_id": 78,
            "text": "hi from group",
            "chat": {"id": -200123},
            "from": {"id": 999, "username": "bob"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.recipient, "-200123");
    assert_eq!(msg.sender, "999");
    assert_eq!(msg.session_key, "-200123");
}

#[test]
fn telegram_parse_update_allows_message_from_allowed_group_with_chat_title() {
    let ch = TelegramChannel::new("t".into(), vec![], vec!["-200123".into()]);
    let update = serde_json::json!({
        "update_id": 10002,
        "message": {
            "message_id": 78,
            "text": "hi from group",
            "chat": {"id": -200123, "title": "Test1", "type": "group"},
            "from": {"id": 999, "username": "bob"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.recipient, "-200123");
    assert_eq!(msg.sender, "999");
    assert_eq!(msg.session_key, "-200123");
}

#[test]
fn telegram_parse_update_partition_chat_only() {
    let ch = TelegramChannel::new_with_partition(
        "t".into(),
        vec!["*".into()],
        vec![],
        TelegramSessionPartition::ChatOnly,
    );
    let update = serde_json::json!({
        "update_id": 10003,
        "message": {
            "message_id": 79,
            "text": "chat scope",
            "chat": {"id": -200123},
            "from": {"id": 1001, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.session_key, "-200123");
}

#[test]
fn telegram_parse_update_partition_chat_only_isolates_different_chats() {
    let ch = TelegramChannel::new_with_partition(
        "t".into(),
        vec!["*".into()],
        vec![],
        TelegramSessionPartition::ChatOnly,
    );
    let update_a = serde_json::json!({
        "update_id": 10008,
        "message": {
            "message_id": 84,
            "text": "chat scope A",
            "chat": {"id": -200111},
            "from": {"id": 1001, "username": "alice"}
        }
    });
    let update_b = serde_json::json!({
        "update_id": 10009,
        "message": {
            "message_id": 85,
            "text": "chat scope B",
            "chat": {"id": -200222},
            "from": {"id": 1001, "username": "alice"}
        }
    });

    let msg_a = ch.parse_update_message(&update_a).expect("message A");
    let msg_b = ch.parse_update_message(&update_b).expect("message B");
    assert_eq!(msg_a.session_key, "-200111");
    assert_eq!(msg_b.session_key, "-200222");
    assert_ne!(msg_a.session_key, msg_b.session_key);
}

#[test]
fn telegram_parse_update_partition_user_only() {
    let ch = TelegramChannel::new_with_partition(
        "t".into(),
        vec!["*".into()],
        vec![],
        TelegramSessionPartition::UserOnly,
    );
    let update = serde_json::json!({
        "update_id": 10004,
        "message": {
            "message_id": 80,
            "text": "user scope",
            "chat": {"id": -200999},
            "from": {"id": 1001, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.session_key, "1001");
}

#[test]
fn telegram_parse_update_partition_chat_thread_user() {
    let ch = TelegramChannel::new_with_partition(
        "t".into(),
        vec!["*".into()],
        vec![],
        TelegramSessionPartition::ChatThreadUser,
    );
    let update = serde_json::json!({
        "update_id": 10005,
        "message": {
            "message_id": 81,
            "message_thread_id": 42,
            "text": "thread scope",
            "chat": {"id": -200123},
            "from": {"id": 1001, "username": "alice"}
        }
    });

    let msg = ch.parse_update_message(&update).expect("message");
    assert_eq!(msg.session_key, "-200123:42:1001");
    assert_eq!(msg.recipient, "-200123:42");
}

#[test]
fn telegram_parse_update_partition_runtime_toggle_changes_session_key_strategy() {
    let ch = TelegramChannel::new_with_partition(
        "t".into(),
        vec!["*".into()],
        vec![],
        TelegramSessionPartition::ChatUser,
    );
    let update_a = serde_json::json!({
        "update_id": 10006,
        "message": {
            "message_id": 82,
            "text": "hello",
            "chat": {"id": -200111},
            "from": {"id": 1001, "username": "alice"}
        }
    });
    let update_b = serde_json::json!({
        "update_id": 10007,
        "message": {
            "message_id": 83,
            "text": "hello",
            "chat": {"id": -200111},
            "from": {"id": 1002, "username": "bob"}
        }
    });

    let msg_a = ch.parse_update_message(&update_a).expect("message A");
    let msg_b = ch.parse_update_message(&update_b).expect("message B");
    assert_ne!(msg_a.session_key, msg_b.session_key);

    ch.set_session_partition(TelegramSessionPartition::ChatOnly);

    let msg_a_shared = ch
        .parse_update_message(&update_a)
        .expect("message A shared");
    let msg_b_shared = ch
        .parse_update_message(&update_b)
        .expect("message B shared");
    assert_eq!(msg_a_shared.session_key, "-200111");
    assert_eq!(msg_a_shared.session_key, msg_b_shared.session_key);
}

#[test]
fn telegram_session_partition_parse_aliases() {
    assert_eq!(
        "chat_user".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::ChatUser)
    );
    assert_eq!(
        "chat".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::ChatOnly)
    );
    assert_eq!(
        "user".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::UserOnly)
    );
    assert_eq!(
        "topic-user".parse::<TelegramSessionPartition>().ok(),
        Some(TelegramSessionPartition::ChatThreadUser)
    );
    assert!("invalid".parse::<TelegramSessionPartition>().is_err());
}

#[tokio::test]
async fn telegram_send_uses_markdown_v2_parse_mode_with_rendering() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_api(None).await? else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel
        .send(
            "**bold** [link](https://example.com) `code` <raw>",
            "123456",
        )
        .await?;

    let requests = state.requests.lock().await;
    assert_eq!(requests.len(), 1);
    let request = &requests[0];
    assert_eq!(
        request
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    let rendered_text = request
        .get("text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default();
    assert!(rendered_text.contains("*bold*"));
    assert!(rendered_text.contains("[link](https://example.com)"));
    assert!(rendered_text.contains("`code`"));
    assert!(
        rendered_text.contains("<raw\\>") || rendered_text.contains("\\<raw\\>"),
        "expected escaped raw marker in MarkdownV2 payload, got: {rendered_text}"
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_includes_message_thread_id_when_recipient_has_topic_suffix() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_api(None).await? else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel.send("topic hello", "123456:42").await?;

    let requests = state.requests.lock().await;
    assert_eq!(requests.len(), 1);
    let request = &requests[0];
    assert_eq!(
        request.get("chat_id").and_then(serde_json::Value::as_str),
        Some("123456")
    );
    assert_eq!(
        request
            .get("message_thread_id")
            .and_then(serde_json::Value::as_str),
        Some("42")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_falls_back_to_html_after_markdown_parse_error() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_api(Some("Bad Request: can't parse entities")).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel.send("fallback check", "123456").await?;

    let requests = state.requests.lock().await;
    assert_eq!(requests.len(), 2);
    assert_eq!(
        requests[0]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert!(
        requests[1]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str)
            == Some("HTML"),
        "fallback request should use HTML parse_mode"
    );
    assert_eq!(
        requests[1].get("text").and_then(serde_json::Value::as_str),
        Some("fallback check")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_chunk_markers_are_plain_text() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_api(None).await? else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let message = "a".repeat(4300);
    channel.send(&message, "123456").await?;

    let requests = state.requests.lock().await;
    assert!(requests.len() >= 2, "long messages should be split");
    let first = requests[0]
        .get("text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default();
    let second = requests[1]
        .get("text")
        .and_then(serde_json::Value::as_str)
        .unwrap_or_default();
    assert!(first.contains("\\(continues\\.\\.\\.\\)"));
    assert!(second.contains("\\(continued\\)"));
    assert!(!first.contains("_(continues...)_"));
    assert!(!second.contains("_(continued)_"));

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_falls_back_to_html_on_generic_markdown_bad_request() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_api(Some("Bad Request: markdown rejected")).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel.send("fallback check", "123456").await?;

    let requests = state.requests.lock().await;
    assert_eq!(requests.len(), 2);
    assert_eq!(
        requests[0]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert!(
        requests[1]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str)
            == Some("HTML"),
        "fallback request should use HTML parse_mode"
    );
    assert_eq!(
        requests[1].get("text").and_then(serde_json::Value::as_str),
        Some("fallback check")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_falls_back_to_html_on_markdown_api_error_with_http_200() -> Result<()> {
    let Some((api_base, state, handle)) =
        spawn_mock_telegram_api_level_error(Some("Bad Request: markdown rejected")).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel.send("fallback check", "123456").await?;

    let requests = state.requests.lock().await;
    assert_eq!(requests.len(), 2);
    assert_eq!(
        requests[0]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert!(
        requests[1]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str)
            == Some("HTML"),
        "fallback request should use HTML parse_mode"
    );
    assert_eq!(
        requests[1].get("text").and_then(serde_json::Value::as_str),
        Some("fallback check")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_preserves_full_text_when_markdown_escaping_would_overflow() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_mock_telegram_api(None).await? else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    let message = ".".repeat(9000);
    channel.send(&message, "123456").await?;

    let requests = state.requests.lock().await;
    let chunks = split_message_for_telegram(&message);
    assert_eq!(requests.len(), chunks.len());

    for (index, request) in requests.iter().enumerate() {
        assert!(
            request.get("parse_mode").is_none(),
            "overflow-prone markdown chunks should be sent as plain text"
        );
        let text = request
            .get("text")
            .and_then(serde_json::Value::as_str)
            .unwrap_or_default();
        let expected = decorate_chunk_for_telegram(&chunks[index], index, chunks.len());
        assert_eq!(text, expected);
        assert!(text.chars().count() <= TELEGRAM_MAX_MESSAGE_LENGTH);
    }

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_retries_on_rate_limit_and_succeeds() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_retry_then_success_mock_telegram_api(1).await?
    else {
        return Ok(());
    };
    let channel = TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    );

    channel.send("retry check", "123456").await?;

    let requests = state.requests.lock().await;
    assert_eq!(
        requests.len(),
        2,
        "should retry once after transient 429 and then succeed"
    );
    assert_eq!(
        requests[0]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );
    assert_eq!(
        requests[1]
            .get("parse_mode")
            .and_then(serde_json::Value::as_str),
        Some("MarkdownV2")
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_global_rate_limit_gate_delays_parallel_send() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_rate_limit_gate_mock_telegram_api().await? else {
        return Ok(());
    };
    let channel = Arc::new(TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    ));

    let first_channel = Arc::clone(&channel);
    let first_send =
        tokio::spawn(async move { first_channel.send("firstgatecheck", "123456").await });

    for _ in 0..50 {
        if *state.first_rate_limit_emitted.lock().await {
            break;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }

    let second_channel = Arc::clone(&channel);
    let second_started_at = Instant::now();
    let second_send =
        tokio::spawn(async move { second_channel.send("secondgatecheck", "123456").await });

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
                == Some("secondgatecheck"))
            .then_some(request.received_at)
        })
        .expect("second send request should be captured");
    let wait_before_second_request = second_request_at.duration_since(second_started_at);
    assert!(
        wait_before_second_request >= Duration::from_millis(850),
        "expected second send to wait for global retry window, got {}ms",
        wait_before_second_request.as_millis()
    );

    let first_request_count = requests
        .iter()
        .filter(|request| {
            request
                .payload
                .get("text")
                .and_then(serde_json::Value::as_str)
                == Some("firstgatecheck")
        })
        .count();
    assert_eq!(
        first_request_count, 2,
        "first send should retry once after the injected rate limit"
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_global_rate_limit_gate_spreads_parallel_followup_requests() -> Result<()> {
    let Some((api_base, state, handle)) = spawn_rate_limit_gate_mock_telegram_api().await? else {
        return Ok(());
    };
    let channel = Arc::new(TelegramChannel::new_with_base_url(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
    ));

    let first_channel = Arc::clone(&channel);
    let first_send =
        tokio::spawn(async move { first_channel.send("firstgatecheck", "123456").await });

    for _ in 0..50 {
        if *state.first_rate_limit_emitted.lock().await {
            break;
        }
        tokio::time::sleep(Duration::from_millis(10)).await;
    }

    let second_channel = Arc::clone(&channel);
    let second_send =
        tokio::spawn(async move { second_channel.send("secondspreadcheck", "123456").await });

    let third_channel = Arc::clone(&channel);
    let third_send =
        tokio::spawn(async move { third_channel.send("thirdspreadcheck", "123456").await });

    first_send.await??;
    second_send.await??;
    third_send.await??;

    let requests = state.requests.lock().await;
    let mut followup_times = requests
        .iter()
        .filter_map(|request| {
            let text = request
                .payload
                .get("text")
                .and_then(serde_json::Value::as_str)
                .unwrap_or_default();
            match text {
                "secondspreadcheck" | "thirdspreadcheck" => Some(request.received_at),
                _ => None,
            }
        })
        .collect::<Vec<_>>();
    assert_eq!(
        followup_times.len(),
        2,
        "expected exactly two parallel follow-up requests"
    );
    followup_times.sort_unstable();
    let spread_gap = followup_times[1].duration_since(followup_times[0]);
    assert!(
        spread_gap >= Duration::from_millis(30),
        "expected staggered follow-up requests after rate limit gate, gap={}ms",
        spread_gap.as_millis()
    );

    handle.abort();
    Ok(())
}

#[tokio::test]
async fn telegram_send_returns_timeout_error_for_slow_http_response() -> Result<()> {
    let Some((api_base, handle)) =
        spawn_delayed_send_mock_telegram_api(Duration::from_millis(250)).await?
    else {
        return Ok(());
    };

    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_millis(50))
        .timeout(Duration::from_millis(50))
        .build()?;
    let channel = TelegramChannel::new_with_base_url_and_partition_and_client(
        "fake-token".to_string(),
        vec!["*".to_string()],
        vec![],
        api_base,
        vec!["*".to_string()],
        TelegramSessionPartition::ChatUser,
        client,
    );

    let started_at = Instant::now();
    let error = channel
        .send("timeout check", "123456")
        .await
        .expect_err("send should time out with a very short client timeout");
    assert!(
        started_at.elapsed() < Duration::from_secs(2),
        "send should fail quickly when request timeout is configured"
    );
    let error_message = error.to_string().to_lowercase();
    assert!(
        error_message.contains("timed out") || error_message.contains("deadline has elapsed"),
        "expected timeout error, got: {}",
        error
    );

    handle.abort();
    Ok(())
}
