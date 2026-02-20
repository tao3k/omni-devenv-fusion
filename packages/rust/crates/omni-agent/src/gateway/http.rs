//! HTTP gateway: POST /message → agent turn → JSON response.
//!
//! Request validation (400 for empty session_id or message), 500 on agent error.
//! Each request is limited by a timeout to avoid stuck connections.

use anyhow::Result;
use axum::{
    Json, Router,
    extract::State,
    http::StatusCode,
    routing::{get, post},
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::Duration;
use tokio::net::TcpListener;
use tokio::sync::Semaphore;

use crate::agent::Agent;
use crate::mcp_pool::McpToolsListCacheStatsSnapshot;

/// Default timeout for one agent turn (LLM + tools); avoids stuck connections.
const TURN_TIMEOUT_SECS: u64 = 300;

/// Request body for POST /message.
#[derive(Debug, Deserialize)]
pub struct MessageRequest {
    /// Conversation session identifier.
    pub session_id: String,
    /// User message to send to the agent.
    pub message: String,
}

/// Response body.
#[derive(Debug, Serialize)]
pub struct MessageResponse {
    /// Agent reply (text output).
    pub output: String,
    /// Session identifier (echo of request).
    pub session_id: String,
}

/// Shared state for the HTTP server: agent + per-turn timeout + optional concurrency limit.
#[derive(Clone)]
pub struct GatewayState {
    pub agent: Arc<Agent>,
    pub turn_timeout_secs: u64,
    /// When Some, limits concurrent agent turns; excess requests wait for a slot.
    pub concurrency_semaphore: Option<Arc<Semaphore>>,
    pub max_concurrent_turns: Option<usize>,
}

/// MCP section in gateway health response.
#[derive(Debug, Serialize)]
pub struct GatewayMcpHealthResponse {
    pub enabled: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tools_list_cache: Option<McpToolsListCacheStatsSnapshot>,
}

/// Response body for gateway health endpoint.
#[derive(Debug, Serialize)]
pub struct GatewayHealthResponse {
    pub status: &'static str,
    pub turn_timeout_secs: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub max_concurrent_turns: Option<usize>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub in_flight_turns: Option<usize>,
    pub mcp: GatewayMcpHealthResponse,
}

/// Validate request body; returns error for empty session_id or message.
pub fn validate_message_request(
    body: &MessageRequest,
) -> Result<(String, String), (StatusCode, String)> {
    let session_id = body.session_id.trim().to_string();
    let message = body.message.trim().to_string();
    if session_id.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "session_id must be non-empty".to_string(),
        ));
    }
    if message.is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "message must be non-empty".to_string(),
        ));
    }
    Ok((session_id, message))
}

async fn handle_message(
    State(state): State<GatewayState>,
    Json(body): Json<MessageRequest>,
) -> Result<Json<MessageResponse>, (StatusCode, String)> {
    let (session_id, message) = validate_message_request(&body)?;
    let _permit = if let Some(ref sem) = state.concurrency_semaphore {
        Some(sem.acquire().await.map_err(|_| {
            (
                StatusCode::SERVICE_UNAVAILABLE,
                "concurrency limit closed".to_string(),
            )
        })?)
    } else {
        None
    };
    let timeout_secs = state.turn_timeout_secs;
    let output = match tokio::time::timeout(
        Duration::from_secs(timeout_secs),
        state.agent.run_turn(&session_id, &message),
    )
    .await
    {
        Ok(Ok(out)) => out,
        Ok(Err(e)) => return Err((StatusCode::INTERNAL_SERVER_ERROR, e.to_string())),
        Err(_) => {
            return Err((
                StatusCode::GATEWAY_TIMEOUT,
                format!("agent turn timed out after {}s", timeout_secs),
            ));
        }
    };
    Ok(Json(MessageResponse { output, session_id }))
}

async fn handle_health(State(state): State<GatewayState>) -> Json<GatewayHealthResponse> {
    let mcp_cache = state.agent.inspect_mcp_tools_list_cache_stats();
    let in_flight_turns = state.max_concurrent_turns.and_then(|max| {
        state
            .concurrency_semaphore
            .as_ref()
            .map(|sem| max.saturating_sub(sem.available_permits()))
    });
    Json(GatewayHealthResponse {
        status: "healthy",
        turn_timeout_secs: state.turn_timeout_secs,
        max_concurrent_turns: state.max_concurrent_turns,
        in_flight_turns,
        mcp: GatewayMcpHealthResponse {
            enabled: mcp_cache.is_some(),
            tools_list_cache: mcp_cache,
        },
    })
}

/// Build the gateway router (POST /message).
pub fn router(agent: Agent, turn_timeout_secs: u64, max_concurrent_turns: Option<usize>) -> Router {
    let concurrency_semaphore = max_concurrent_turns.map(|n| Arc::new(Semaphore::new(n)));
    let state = GatewayState {
        agent: Arc::new(agent),
        turn_timeout_secs,
        concurrency_semaphore,
        max_concurrent_turns,
    };
    Router::new()
        .route("/health", get(handle_health))
        .route("/message", post(handle_message))
        .with_state(state)
}

/// Run the HTTP server; binds to `bind_addr` (e.g. `0.0.0.0:8080`).
/// Graceful shutdown on Ctrl+C (SIGINT) and SIGTERM (Unix); in-flight requests complete before exit.
/// `turn_timeout_secs`: per-turn timeout (default 300 when None).
/// `max_concurrent_turns`: limit concurrent agent turns (None = no limit; Some(4) default from CLI).
pub async fn run_http(
    agent: Agent,
    bind_addr: &str,
    turn_timeout_secs: Option<u64>,
    max_concurrent_turns: Option<usize>,
) -> Result<()> {
    let timeout = turn_timeout_secs.unwrap_or(TURN_TIMEOUT_SECS);
    let app = router(agent, timeout, max_concurrent_turns);
    let listener = TcpListener::bind(bind_addr).await?;
    let max_str = max_concurrent_turns
        .map(|n| n.to_string())
        .unwrap_or_else(|| "unlimited".to_string());
    tracing::info!(
        "gateway listening on {} (turn_timeout={}s, max_concurrent={}, Ctrl+C/SIGTERM to stop)",
        bind_addr,
        timeout,
        max_str
    );
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    tracing::info!("gateway stopped");
    Ok(())
}

async fn shutdown_signal() {
    #[cfg(unix)]
    {
        use tokio::signal::unix::{SignalKind, signal};
        let ctrl_c = tokio::signal::ctrl_c();
        let mut sigterm = signal(SignalKind::terminate()).expect("failed to listen for SIGTERM");
        tokio::select! {
            _ = ctrl_c => {}
            _ = sigterm.recv() => {}
        }
    }
    #[cfg(not(unix))]
    {
        tokio::signal::ctrl_c()
            .await
            .expect("failed to listen for Ctrl+C");
    }
}
