//! Tests for `OmniMcpClient`: from_config, list_tools/call_tool before connect.

use omni_mcp_client::{McpServerTransportConfig, OmniMcpClient};

#[test]
fn from_config_streamable_http_creates_client() {
    let config = McpServerTransportConfig::StreamableHttp {
        url: "http://127.0.0.1:3000".to_string(),
        bearer_token_env_var: None,
    };
    let _client = OmniMcpClient::from_config(&config);
}

#[test]
fn from_config_stdio_creates_client() {
    let config = McpServerTransportConfig::Stdio {
        command: "true".to_string(),
        args: vec![],
    };
    let _client = OmniMcpClient::from_config(&config);
}

#[tokio::test]
async fn list_tools_before_connect_returns_error() {
    let config = McpServerTransportConfig::StreamableHttp {
        url: "http://127.0.0.1:3000".to_string(),
        bearer_token_env_var: None,
    };
    let client = OmniMcpClient::from_config(&config);
    let err = client.list_tools(None).await.unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("not initialized"),
        "expected 'not initialized', got: {}",
        msg
    );
}

#[tokio::test]
async fn call_tool_before_connect_returns_error() {
    let config = McpServerTransportConfig::StreamableHttp {
        url: "http://127.0.0.1:3000".to_string(),
        bearer_token_env_var: None,
    };
    let client = OmniMcpClient::from_config(&config);
    let err = client
        .call_tool(
            "demo.echo".to_string(),
            Some(serde_json::json!({"message": "hi"})),
        )
        .await
        .unwrap_err();
    let msg = err.to_string();
    assert!(
        msg.contains("not initialized"),
        "expected 'not initialized', got: {}",
        msg
    );
}
