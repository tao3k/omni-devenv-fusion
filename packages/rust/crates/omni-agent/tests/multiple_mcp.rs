//! Unit tests for multiple-MCP tool name qualification and parsing (no network).

use omni_agent::{parse_qualified_tool_name, qualify_tool_name};

#[test]
fn qualify_tool_name_format() {
    assert_eq!(
        qualify_tool_name("omniAgent", "run_terminal_cmd"),
        "mcp__omniAgent__run_terminal_cmd"
    );
    assert_eq!(qualify_tool_name("s1", "tool_a"), "mcp__s1__tool_a");
}

#[test]
fn parse_qualified_tool_name_valid() {
    assert_eq!(
        parse_qualified_tool_name("mcp__omniAgent__run_terminal_cmd"),
        Some(("omniAgent".to_string(), "run_terminal_cmd".to_string()))
    );
    assert_eq!(
        parse_qualified_tool_name("mcp__s1__tool_a"),
        Some(("s1".to_string(), "tool_a".to_string()))
    );
}

#[test]
fn parse_qualified_tool_name_invalid_returns_none() {
    assert!(parse_qualified_tool_name("run_terminal_cmd").is_none());
    assert!(parse_qualified_tool_name("mcp__").is_none());
    assert!(parse_qualified_tool_name("mcp__server_only").is_none());
    assert!(parse_qualified_tool_name("").is_none());
}

#[test]
fn qualify_and_parse_roundtrip() {
    let server = "myServer";
    let tool = "my_tool";
    let qualified = qualify_tool_name(server, tool);
    let parsed = parse_qualified_tool_name(&qualified).unwrap();
    assert_eq!(parsed.0, server);
    assert_eq!(parsed.1, tool);
}
