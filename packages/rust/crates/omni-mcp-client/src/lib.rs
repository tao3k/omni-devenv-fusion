//! MCP client for omni-agent.
//!
//! Follows the [MCP protocol](https://spec.modelcontextprotocol.io/) and the same client pattern
//! as [codex-rs](https://github.com/openai/codex) rmcp-client: `serve_client(handler, transport)`
//! for the handshake, then `list_tools` / `call_tool` on the running service.

mod client;
mod config;

pub use client::{OmniMcpClient, init_params_omni_server};
pub use config::McpServerTransportConfig;
