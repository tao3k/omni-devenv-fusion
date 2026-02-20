//! HTTP gateway integration tests: validation (400), routing, response shape.
//! Uses a minimal Agent (no MCP) so no external services are required.

use axum::body::Body;
use axum::body::to_bytes;
use axum::http::{Request, StatusCode};
use omni_agent::{Agent, AgentConfig, router};
use serde_json::Value;
use tower::ServiceExt;

fn minimal_agent_config() -> AgentConfig {
    AgentConfig {
        inference_url: "https://api.openai.com/v1/chat/completions".to_string(),
        model: "gpt-4o-mini".to_string(),
        api_key: None,
        max_tool_rounds: 1,
        ..AgentConfig::default()
    }
}

#[tokio::test]
async fn gateway_returns_400_for_empty_session_id() {
    let config = minimal_agent_config();
    let agent = Agent::from_config(config).await.expect("agent");
    let app = router(agent, 300, None);

    let response = app
        .oneshot(
            Request::post("/message")
                .header("content-type", "application/json")
                .body(Body::from(r#"{"session_id":"","message":"hi"}"#))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn gateway_returns_400_for_empty_message() {
    let config = minimal_agent_config();
    let agent = Agent::from_config(config).await.expect("agent");
    let app = router(agent, 300, None);

    let response = app
        .oneshot(
            Request::post("/message")
                .header("content-type", "application/json")
                .body(Body::from(r#"{"session_id":"s1","message":"   "}"#))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn gateway_returns_404_for_unknown_route() {
    let config = minimal_agent_config();
    let agent = Agent::from_config(config).await.expect("agent");
    let app = router(agent, 300, None);

    let response = app
        .oneshot(Request::get("/unknown").body(Body::empty()).unwrap())
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}

#[tokio::test]
async fn gateway_health_returns_structured_summary_without_mcp() {
    let config = minimal_agent_config();
    let agent = Agent::from_config(config).await.expect("agent");
    let app = router(agent, 300, Some(4));

    let response = app
        .oneshot(Request::get("/health").body(Body::empty()).unwrap())
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::OK);
    let bytes = to_bytes(response.into_body(), usize::MAX).await.unwrap();
    let payload: Value = serde_json::from_slice(&bytes).expect("json body");

    assert_eq!(
        payload.get("status").and_then(Value::as_str),
        Some("healthy")
    );
    assert_eq!(
        payload.get("turn_timeout_secs").and_then(Value::as_u64),
        Some(300)
    );
    assert_eq!(
        payload.get("max_concurrent_turns").and_then(Value::as_u64),
        Some(4)
    );
    assert_eq!(
        payload.get("in_flight_turns").and_then(Value::as_u64),
        Some(0)
    );
    assert_eq!(
        payload
            .get("mcp")
            .and_then(|mcp| mcp.get("enabled"))
            .and_then(Value::as_bool),
        Some(false)
    );
    let tools_list_cache = payload
        .get("mcp")
        .and_then(|mcp| mcp.get("tools_list_cache"));
    assert!(
        tools_list_cache.is_none() || tools_list_cache.is_some_and(Value::is_null),
        "tools_list_cache should be omitted or null when MCP is disabled"
    );
}
