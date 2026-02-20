//! Tests for MCP config loading (mcp.json only, no env fallback).

use omni_agent::load_mcp_config;
use std::io::Write;

#[test]
fn load_mcp_config_missing_file_returns_empty() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("nonexistent.json");
    let servers = load_mcp_config(&path).unwrap();
    assert!(servers.is_empty());
}

#[test]
fn load_mcp_config_http_server_preserves_base_url() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("mcp.json");
    let json = r#"{"mcpServers":{"omniAgent":{"type":"http","url":"http://127.0.0.1:3002"}}}"#;
    std::fs::File::create(&path)
        .unwrap()
        .write_all(json.as_bytes())
        .unwrap();
    let servers = load_mcp_config(&path).unwrap();
    assert_eq!(servers.len(), 1);
    assert_eq!(servers[0].name, "omniAgent");
    assert_eq!(
        servers[0].url.as_deref(),
        Some("http://127.0.0.1:3002"),
        "HTTP URL must be preserved to avoid forcing a legacy MCP route"
    );
    assert!(servers[0].command.is_none());
}

#[test]
fn load_mcp_config_http_server_preserves_existing_sse() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("mcp.json");
    let json = r#"{"mcpServers":{"omniAgent":{"type":"http","url":"http://127.0.0.1:3002/sse"}}}"#;
    std::fs::File::create(&path)
        .unwrap()
        .write_all(json.as_bytes())
        .unwrap();
    let servers = load_mcp_config(&path).unwrap();
    assert_eq!(servers.len(), 1);
    assert_eq!(servers[0].url.as_deref(), Some("http://127.0.0.1:3002/sse"));
}

#[test]
fn load_mcp_config_http_server_trims_messages_trailing_slash() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("mcp.json");
    let json =
        r#"{"mcpServers":{"omniAgent":{"type":"http","url":"http://127.0.0.1:3002/messages/"}}}"#;
    std::fs::File::create(&path)
        .unwrap()
        .write_all(json.as_bytes())
        .unwrap();
    let servers = load_mcp_config(&path).unwrap();
    assert_eq!(servers.len(), 1);
    assert_eq!(
        servers[0].url.as_deref(),
        Some("http://127.0.0.1:3002/messages")
    );
}

#[test]
fn load_mcp_config_stdio_server() {
    let dir = tempfile::tempdir().unwrap();
    let path = dir.path().join("mcp.json");
    let json = r#"{"mcpServers":{"stdioAgent":{"type":"stdio","command":"omni","args":["mcp","--transport","stdio"]}}}"#;
    std::fs::File::create(&path)
        .unwrap()
        .write_all(json.as_bytes())
        .unwrap();
    let servers = load_mcp_config(&path).unwrap();
    assert_eq!(servers.len(), 1);
    assert_eq!(servers[0].name, "stdioAgent");
    assert!(servers[0].url.is_none());
    assert_eq!(servers[0].command.as_deref(), Some("omni"));
    assert_eq!(
        servers[0].args.as_ref().map(|a| a.as_slice()),
        Some(
            &[
                "mcp".to_string(),
                "--transport".to_string(),
                "stdio".to_string()
            ][..]
        )
    );
}
