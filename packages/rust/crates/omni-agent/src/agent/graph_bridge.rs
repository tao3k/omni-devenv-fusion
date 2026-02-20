use anyhow::{Result, bail};
use serde::{Deserialize, Serialize};

use super::Agent;

/// Generic MCP bridge request for graph workflows implemented outside Rust.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GraphBridgeRequest {
    /// MCP tool name (for example `researcher.run_research_graph`).
    pub tool_name: String,
    /// Tool arguments forwarded as-is to MCP `tools/call`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub arguments: Option<serde_json::Value>,
}

/// Graph bridge execution result returned by Rust runtime.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GraphBridgeResult {
    pub tool_name: String,
    pub output: String,
    pub is_error: bool,
}

/// Validate graph bridge request shape before issuing MCP tool call.
pub fn validate_graph_bridge_request(request: &GraphBridgeRequest) -> Result<()> {
    let tool_name = request.tool_name.trim();
    if tool_name.is_empty() {
        bail!("graph bridge tool_name must not be empty");
    }
    if let Some(arguments) = request.arguments.as_ref()
        && !arguments.is_object()
    {
        bail!("graph bridge arguments must be a JSON object when provided");
    }
    Ok(())
}

impl Agent {
    /// Execute a graph workflow via MCP bridge.
    ///
    /// Rust runtime remains orchestration-only; graph planning/execution can stay in
    /// Python LangGraph (or any MCP-compatible backend).
    pub async fn execute_graph_bridge(
        &self,
        request: GraphBridgeRequest,
    ) -> Result<GraphBridgeResult> {
        validate_graph_bridge_request(&request)?;
        let tool_name = request.tool_name.trim().to_string();
        let output = self
            .call_mcp_tool_with_diagnostics(&tool_name, request.arguments.clone())
            .await?;
        Ok(GraphBridgeResult {
            tool_name,
            output: output.text,
            is_error: output.is_error,
        })
    }
}
