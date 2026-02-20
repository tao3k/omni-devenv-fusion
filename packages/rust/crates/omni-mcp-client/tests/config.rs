//! Tests for `McpServerTransportConfig` (de)serialization.

use omni_mcp_client::McpServerTransportConfig;
use serde_json;

#[test]
fn config_roundtrip_streamable_http() {
    // Untagged enum: JSON is the variant's fields at top level.
    let json = r#"{"url":"http://127.0.0.1:3000"}"#;
    let config: McpServerTransportConfig = serde_json::from_str(json).expect("deserialize");
    match &config {
        McpServerTransportConfig::StreamableHttp {
            url,
            bearer_token_env_var,
        } => {
            assert_eq!(url, "http://127.0.0.1:3000");
            assert!(bearer_token_env_var.is_none());
        }
        _ => panic!("expected StreamableHttp"),
    }
    let out = serde_json::to_string(&config).expect("serialize");
    let again: McpServerTransportConfig = serde_json::from_str(&out).expect("deserialize again");
    match &again {
        McpServerTransportConfig::StreamableHttp { url, .. } => {
            assert_eq!(url, "http://127.0.0.1:3000");
        }
        _ => panic!("expected StreamableHttp"),
    }
}

#[test]
fn config_roundtrip_streamable_http_with_bearer() {
    let json = r#"{"url":"http://127.0.0.1:3000","bearer_token_env_var":"MCP_TOKEN"}"#;
    let config: McpServerTransportConfig = serde_json::from_str(json).expect("deserialize");
    match &config {
        McpServerTransportConfig::StreamableHttp {
            url,
            bearer_token_env_var,
        } => {
            assert_eq!(url, "http://127.0.0.1:3000");
            assert_eq!(bearer_token_env_var.as_deref(), Some("MCP_TOKEN"));
        }
        _ => panic!("expected StreamableHttp"),
    }
}

#[test]
fn config_roundtrip_stdio() {
    let json = r#"{"command":"uv","args":["run","omni","mcp","--transport","stdio"]}"#;
    let config: McpServerTransportConfig = serde_json::from_str(json).expect("deserialize");
    match &config {
        McpServerTransportConfig::Stdio { command, args } => {
            assert_eq!(command, "uv");
            assert_eq!(args, &["run", "omni", "mcp", "--transport", "stdio"]);
        }
        _ => panic!("expected Stdio"),
    }
    let out = serde_json::to_string(&config).expect("serialize");
    let again: McpServerTransportConfig = serde_json::from_str(&out).expect("deserialize again");
    match &again {
        McpServerTransportConfig::Stdio { command, args } => {
            assert_eq!(command, "uv");
            assert_eq!(args.len(), 5);
        }
        _ => panic!("expected Stdio"),
    }
}

#[test]
fn config_stdio_default_args() {
    let json = r#"{"command":"npx"}"#;
    let config: McpServerTransportConfig = serde_json::from_str(json).expect("deserialize");
    match &config {
        McpServerTransportConfig::Stdio { command, args } => {
            assert_eq!(command, "npx");
            assert!(args.is_empty());
        }
        _ => panic!("expected Stdio"),
    }
}
