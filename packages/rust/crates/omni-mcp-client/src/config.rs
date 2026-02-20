//! MCP server config: transport (Streamable HTTP or stdio).
//!
//! Minimal shape aligned with codex-rs `McpServerTransportConfig`.

use serde::{Deserialize, Serialize};

/// Transport for one MCP server (Streamable HTTP or stdio).
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(untagged, rename_all = "snake_case")]
pub enum McpServerTransportConfig {
    /// Streamable HTTP: connect to URL (e.g. our Python `omni mcp` SSE endpoint).
    StreamableHttp {
        /// MCP server URL (e.g. `http://127.0.0.1:3000`).
        url: String,
        /// Optional env var name for bearer token.
        #[serde(default, skip_serializing_if = "Option::is_none")]
        bearer_token_env_var: Option<String>,
    },
    /// Stdio: spawn command; stdin/stdout speak MCP.
    Stdio {
        /// Executable name or path.
        command: String,
        /// Arguments (e.g. `["-y", "@modelcontextprotocol/server-everything"]`).
        #[serde(default)]
        args: Vec<String>,
    },
}
