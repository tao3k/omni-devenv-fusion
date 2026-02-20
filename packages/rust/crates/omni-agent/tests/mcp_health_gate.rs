//! MCP health readiness gate behavior.

use std::time::{Duration, Instant};

use axum::routing::get;
use axum::{Json, Router};
use omni_agent::{Agent, AgentConfig, McpServerEntry};
use serde_json::json;

fn config_for(base_url: &str, retries: u32) -> AgentConfig {
    AgentConfig {
        mcp_servers: vec![McpServerEntry {
            name: "mock-mcp".to_string(),
            url: Some(format!("{base_url}/sse")),
            command: None,
            args: None,
        }],
        mcp_pool_size: 1,
        mcp_handshake_timeout_secs: 1,
        mcp_connect_retries: retries,
        mcp_connect_retry_backoff_ms: 10,
        ..Default::default()
    }
}

async fn spawn_server(app: Router) -> (String, tokio::task::JoinHandle<()>) {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind test listener");
    let addr = listener.local_addr().expect("read test listener addr");
    let handle = tokio::spawn(async move {
        let _ = axum::serve(listener, app).await;
    });
    (format!("http://{addr}"), handle)
}

#[tokio::test]
async fn startup_fails_when_structured_health_never_becomes_ready() {
    let app = Router::new().route(
        "/health",
        get(|| async {
            Json(json!({
                "status": "ok",
                "ready": false,
                "initializing": true,
                "active_sessions": 0,
            }))
        }),
    );
    let (base_url, server_task) = spawn_server(app).await;

    let started = Instant::now();
    let error = match Agent::from_config(config_for(&base_url, 2)).await {
        Ok(_) => panic!("startup should fail when MCP health is never ready"),
        Err(error) => error,
    };
    server_task.abort();

    let message = format!("{error:#}");
    assert!(
        message.contains("MCP health ready wait timed out"),
        "unexpected error message: {message}"
    );
    assert!(
        started.elapsed() >= Duration::from_millis(900),
        "health readiness gate should wait before failing"
    );
}

#[tokio::test]
async fn startup_keeps_legacy_handshake_path_when_health_is_not_structured() {
    let app = Router::new().route("/health", get(|| async { "ok" }));
    let (base_url, server_task) = spawn_server(app).await;

    let error = match Agent::from_config(config_for(&base_url, 1)).await {
        Ok(_) => panic!("startup should fail because /sse is not an MCP endpoint"),
        Err(error) => error,
    };
    server_task.abort();

    let message = format!("{error:#}");
    assert!(
        !message.contains("MCP health ready wait timed out"),
        "health gate should be skipped for non-structured health endpoints: {message}"
    );
    assert!(
        message.contains("MCP connect failed after 1 attempts"),
        "unexpected error message: {message}"
    );
}
