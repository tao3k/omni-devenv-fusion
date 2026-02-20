//! Startup MCP connect behavior.

use omni_agent::{Agent, AgentConfig, McpServerEntry};

#[tokio::test]
async fn agent_startup_mcp_connect_retries_are_applied() {
    let config = AgentConfig {
        mcp_servers: vec![McpServerEntry {
            name: "local-unreachable".to_string(),
            url: Some("http://127.0.0.1:1/sse".to_string()),
            command: None,
            args: None,
        }],
        mcp_pool_size: 1,
        mcp_handshake_timeout_secs: 1,
        mcp_connect_retries: 2,
        mcp_connect_retry_backoff_ms: 10,
        ..Default::default()
    };

    let error = match Agent::from_config(config).await {
        Ok(_) => panic!("startup should fail for unreachable MCP endpoint"),
        Err(error) => error,
    };
    let message = format!("{error:#}");
    assert!(
        message.contains("MCP connect failed after 2 attempts"),
        "unexpected error message: {message}"
    );
    assert!(
        message.contains("http://127.0.0.1:1/sse"),
        "unexpected error message: {message}"
    );
}
