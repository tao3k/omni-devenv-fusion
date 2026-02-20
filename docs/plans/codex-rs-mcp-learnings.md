# Codex-RS MCP Implementation: Learnings

> Reference: `.cache/researcher/openai/codex/codex-rs` (OpenAI Codex CLI, Rust). We use this as a reference for building our **omni-rust agent** MCP client and config model.

## 1. Codex-RS Layout (Relevant Parts)

| Crate           | Role                                                                                                                                                                                                                                   |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **rmcp-client** | MCP **client** built on official `rmcp` SDK. Creates `RmcpClient` from **stdio** (child process) or **Streamable HTTP** (URL + optional OAuth). Exposes `initialize`, `list_tools`, `call_tool`, `list_resources`, etc.                |
| **mcp-server**  | MCP **server** (experimental): `codex mcp-server` so other MCP clients can use Codex as a tool.                                                                                                                                        |
| **core**        | Business logic. **McpConnectionManager** owns one `RmcpClient` per configured server (keyed by server name); aggregates tools from all servers with qualified names `mcp__<server>__<tool>`; routes `call_tool` to the correct client. |
| **config**      | `McpServerConfig` and `McpServerTransportConfig` (Stdio vs StreamableHttp); loaded from `config.toml`.                                                                                                                                 |

## 2. Transport: Stdio vs Streamable HTTP

- **Stdio**: `RmcpClient::new_stdio_client(program, args, env, env_vars, cwd)` — spawns subprocess, uses `rmcp::transport::child_process::TokioChildProcess` (stdin/stdout). Kill on drop; optional process-group guard on Unix.
- **Streamable HTTP**: `RmcpClient::new_streamable_http_client(server_name, url, bearer_token, http_headers, env_http_headers, store_mode)` — uses `rmcp::transport::StreamableHttpClientTransport` with `reqwest::Client`. Optional OAuth (AuthClient, token refresh, persist).

Both paths produce a **transport** that is then passed to `service::serve_client(client_handler, transport)` to complete the MCP handshake and get a `RunningService<RoleClient, Handler>`.

## 3. Config Shape (codex-rs)

```toml
# Stdio: command + optional args, env, env_vars, cwd
[transport]
command = "npx"
args = ["-y", "@modelcontextprotocol/server-everything"]

# Streamable HTTP: url + optional bearer_token_env_var, http_headers, env_http_headers
[transport]
url = "https://mcp.example.com/sse"
bearer_token_env_var = "MCP_TOKEN"
```

`McpServerTransportConfig` is an enum: `Stdio { command, args, env, env_vars, cwd }` | `StreamableHttp { url, bearer_token_env_var, http_headers, env_http_headers }`. Per-server options: `enabled`, `required`, `startup_timeout_sec`, `tool_timeout_sec`, `enabled_tools`, `disabled_tools`.

## 4. Client Lifecycle

1. **Build transport** (stdio or HTTP) → `RmcpClient { state: Connecting { transport } }`.
2. **initialize(params, timeout, send_elicitation)** → `serve_client(handler, transport)` runs handshake; on success store `RunningService` in state (Ready). Returns `InitializeResult`.
3. **list_tools(params, timeout)** → `service.list_tools(params)`.
4. **call_tool(name, arguments, timeout)** → `service.call_tool(CallToolRequestParams { name, arguments, ... })`.

Timeouts are applied per call (`run_with_timeout`). OAuth: refresh_if_needed before requests; persist_if_needed after.

## 5. Multi-Server (McpConnectionManager)

- Config: `HashMap<String, McpServerConfig>` (server name → config).
- For each enabled server: `make_rmcp_client(server_name, transport, store_mode)` → then initialize and list_tools. Store as `ManagedClient { client, tools, tool_timeout, tool_filter, ... }`.
- **Qualified tool names**: `mcp__<server_name>__<tool_name>` (sanitized for Responses API: `^[a-zA-Z0-9_-]+$`, max length 64).
- **call_tool**: Parse qualified name to get server + tool name; look up client; call `client.call_tool(tool_name, arguments)`.

## 6. MCP Protocol Flow We Implement (Same as Codex)

The client **must** follow the MCP lifecycle; we use `rmcp::serve_client(handler, transport)` which does:

1. **Send `initialize` request** (JSON-RPC) with `protocolVersion`, `capabilities`, `clientInfo`.
2. **Receive** server response: 200 + JSON `InitializeResult`; server should send `Mcp-Session-Id` header.
3. **Send `notifications/initialized`** (notification, no `id`). Server **must** respond with **202 Accepted** (or 204), not 200 + body (Streamable HTTP spec).
4. Then the client can call `list_tools`, `call_tool`, etc. on the `RunningService`.

**Protocol version**: Our Python MCP server supports `2024-11-05`. rmcp’s default is `LATEST` (e.g. 2025-03-26). We use `init_params_omni_server()` which sets `ProtocolVersion::V_2024_11_05` so the server accepts the handshake.

## 7. What We Reuse for omni-agent

- **rmcp** crate (official Rust MCP SDK): same as Codex. Features: `client`, `transport-streamable-http-client-reqwest`, `transport-child-process` (for stdio).
- **Config pattern**: List of MCP servers; each entry is either Stdio (command + args) or StreamableHttp (url + optional auth/headers). We can start with a minimal config (e.g. single URL or single stdio command).
- **Client API**: After connect + initialize, use `list_tools` and `call_tool`. We do not need OAuth or elicitation for the first version; we can add later.
- **Multi-server**: Optional: aggregate tools from multiple MCP servers with a delimiter (e.g. `server__tool`); route call_tool to the right client. Phase A can be single-server; Phase D can add multiple.

## 8. References (Paths in codex-rs)

- `rmcp-client/src/rmcp_client.rs` — RmcpClient, new_stdio_client, new_streamable_http_client, initialize, list_tools, call_tool.
- `core/src/mcp_connection_manager.rs` — make_rmcp_client, list_tools_for_client, qualified tool names, routing.
- `core/src/config/types.rs` — McpServerConfig, McpServerTransportConfig (Stdio / StreamableHttp).
