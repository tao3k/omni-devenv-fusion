//! Tool name qualification for multiple MCP servers: `mcp__{server}__{tool}`.

/// Format: `mcp__{server}__{tool}` so the agent can route tool calls to the right MCP server.
pub fn qualify_tool_name(server: &str, tool: &str) -> String {
    format!("mcp__{server}__{tool}")
}

/// Parse a qualified name; returns `Some((server, tool))` or `None` if invalid.
pub fn parse_qualified_tool_name(qualified: &str) -> Option<(String, String)> {
    let rest = qualified.strip_prefix("mcp__")?;
    let (server, tool) = rest.split_once("__")?;
    if server.is_empty() || tool.is_empty() {
        return None;
    }
    Some((server.to_string(), tool.to_string()))
}
