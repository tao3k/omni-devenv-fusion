//! MCP client: full protocol handshake and tool calls.
//!
//! **Protocol (MCP spec, same as codex-rs):**
//! 1. Build transport (Streamable HTTP or stdio via `rmcp`).
//! 2. `serve_client(init_params, transport)` runs the handshake:
//!    - Client sends `initialize` request (JSON-RPC) with protocolVersion, capabilities, clientInfo.
//!    - Server responds with 200 + JSON `InitializeResult` and `Mcp-Session-Id` header.
//!    - Client sends `notifications/initialized` (no id); server must respond **202 Accepted**.
//! 3. After handshake, use `list_tools` and `call_tool` on the running service.
//!
//! Reference: [MCP Streamable HTTP](https://spec.modelcontextprotocol.io/specification/2024-11-05/server/streamableHTTP/),
//! codex-rs `rmcp-client` (`serve_client` + `RunningService`).

use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use rmcp::model::{
    CallToolRequestParams, ClientCapabilities, InitializeRequestParams, PaginatedRequestParams,
    ProtocolVersion,
};
use rmcp::service::{RoleClient, serve_client};
use rmcp::transport::StreamableHttpClientTransport;
use rmcp::transport::child_process::TokioChildProcess;
use rmcp::transport::streamable_http_client::StreamableHttpClientTransportConfig;
use tokio::process::Command;
use tokio::sync::Mutex;

use crate::config::McpServerTransportConfig;

/// Build init params for the omni Python MCP server (protocol 2024-11-05).
/// Use this when connecting to `omni mcp --transport sse` so protocol version matches server support.
#[must_use]
pub fn init_params_omni_server() -> InitializeRequestParams {
    InitializeRequestParams {
        meta: None,
        protocol_version: ProtocolVersion::V_2024_11_05,
        capabilities: ClientCapabilities::default(),
        client_info: rmcp::model::Implementation::from_build_env(),
    }
}

/// State after connect: either still connecting or ready with running service.
enum ClientState {
    Connecting,
    Ready {
        service: Arc<rmcp::service::RunningService<RoleClient, InitializeRequestParams>>,
    },
}

/// MCP client: one server. Initialize once, then `list_tools` / `call_tool`.
pub struct OmniMcpClient {
    state: Mutex<ClientState>,
}

impl OmniMcpClient {
    /// Create client from transport config. Call `initialize` before `list_tools`/`call_tool`.
    #[must_use]
    pub fn from_config(_transport: &McpServerTransportConfig) -> Self {
        // Build transport in `connect_*`; for now constructors return an uninitialized client.
        Self {
            state: Mutex::new(ClientState::Connecting),
        }
    }

    /// Connect via Streamable HTTP (e.g. `http://127.0.0.1:3000` for our Python MCP SSE).
    ///
    /// # Errors
    /// Returns an error if the HTTP client cannot be built, the MCP handshake times out,
    /// or the server rejects initialization.
    pub async fn connect_streamable_http(
        url: &str,
        init_params: InitializeRequestParams,
        timeout: Option<Duration>,
    ) -> Result<Self> {
        let http_config = StreamableHttpClientTransportConfig::with_uri(url.to_string());
        let http_client = reqwest::Client::builder()
            .build()
            .map_err(|e| anyhow::anyhow!("reqwest client: {e}"))?;
        let transport = StreamableHttpClientTransport::with_client(http_client, http_config);
        let service = match timeout {
            Some(d) => tokio::time::timeout(d, serve_client(init_params, transport))
                .await
                .map_err(|_| anyhow::anyhow!("MCP handshake timeout"))?
                .map_err(|e| anyhow::anyhow!("MCP handshake: {e}"))?,
            None => serve_client(init_params, transport)
                .await
                .map_err(|e| anyhow::anyhow!("MCP handshake: {e}"))?,
        };
        Ok(Self {
            state: Mutex::new(ClientState::Ready {
                service: Arc::new(service),
            }),
        })
    }

    /// Connect via stdio: spawn command, stdin/stdout = MCP.
    ///
    /// # Errors
    /// Returns an error if spawning the MCP subprocess fails, the handshake times out,
    /// or the server rejects initialization.
    pub async fn connect_stdio(
        command: &str,
        args: &[String],
        init_params: InitializeRequestParams,
        timeout: Option<Duration>,
    ) -> Result<Self> {
        let mut cmd = Command::new(command);
        cmd.args(args)
            .stdin(std::process::Stdio::piped())
            .stdout(std::process::Stdio::piped());
        let (transport, _stderr) = TokioChildProcess::builder(cmd)
            .spawn()
            .map_err(|e| anyhow::anyhow!("spawn MCP process: {e}"))?;
        let service = match timeout {
            Some(d) => tokio::time::timeout(d, serve_client(init_params, transport))
                .await
                .map_err(|_| anyhow::anyhow!("MCP handshake timeout"))?
                .map_err(|e| anyhow::anyhow!("MCP handshake: {e}"))?,
            None => serve_client(init_params, transport)
                .await
                .map_err(|e| anyhow::anyhow!("MCP handshake: {e}"))?,
        };
        Ok(Self {
            state: Mutex::new(ClientState::Ready {
                service: Arc::new(service),
            }),
        })
    }

    /// List tools from the MCP server.
    ///
    /// # Errors
    /// Returns an error if the client has not connected yet or if the server fails `tools/list`.
    pub async fn list_tools(
        &self,
        params: Option<PaginatedRequestParams>,
    ) -> Result<rmcp::model::ListToolsResult> {
        let service = {
            let guard = self.state.lock().await;
            match &*guard {
                ClientState::Ready { service } => Arc::clone(service),
                ClientState::Connecting => {
                    return Err(anyhow::anyhow!("MCP client not initialized"));
                }
            }
        };
        service
            .list_tools(params)
            .await
            .map_err(|e| anyhow::anyhow!("tools/list: {e}"))
    }

    /// Call a tool by name with optional arguments.
    ///
    /// # Errors
    /// Returns an error if the client has not connected yet or if the server fails `tools/call`.
    pub async fn call_tool(
        &self,
        name: String,
        arguments: Option<serde_json::Value>,
    ) -> Result<rmcp::model::CallToolResult> {
        let service = {
            let guard = self.state.lock().await;
            match &*guard {
                ClientState::Ready { service } => Arc::clone(service),
                ClientState::Connecting => {
                    return Err(anyhow::anyhow!("MCP client not initialized"));
                }
            }
        };
        let args = arguments.and_then(|v| v.as_object().cloned());
        let params = CallToolRequestParams {
            meta: None,
            name: name.into(),
            arguments: args,
            task: None,
        };
        service
            .call_tool(params)
            .await
            .map_err(|e| anyhow::anyhow!("tools/call: {e}"))
    }
}
