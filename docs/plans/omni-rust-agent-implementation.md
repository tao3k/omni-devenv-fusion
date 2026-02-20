# Omni Rust Agent: Implementation Roadmap

> What we build next: a **pure Rust agent** that loads MCP server(s) by config (like Claude Code / Cursor), with Python remaining the MCP server (tools only). This document is the implementation plan.

**Design basis**: [omni-run-design-and-implementation.md](./omni-run-design-and-implementation.md) (§ Pure Rust agent + MCP; same as Claude Code / Cursor: load MCP by port/config).

**LLM strategy**: Two options—pure Rust (drop LiteLLM, use Rust LLM crates) vs **Rust uses Python bridge** (LLM stays in Python/LiteLLM; Rust only calls the bridge). Recommendation and tradeoffs: [rust-agent-llm-bridge-vs-pure-rust.md](./rust-agent-llm-bridge-vs-pure-rust.md).

**Architecture vs ZeroClaw**: We target ZeroClaw-like experience (fast Rust agent, gateway) but **do not reimplement** tools or LLM. Rust owns loop, session, memory, gateway, MCP client; **skill registry + executor** can be in Rust (Rust executor runs Python/bash/other scripts instead of Python subprocess); LLM via LiteLLM or bridge. Same MCP surface for our agent and for Codex/Gemini CLI. Rationale: [rust-agent-architecture-omni-vs-zeroclaw.md](./rust-agent-architecture-omni-vs-zeroclaw.md). Rust-as-executor design: [rust-skill-executor.md](./rust-skill-executor.md).

---

## 1. Target Shape

| Component                 | Role                                                                                                                                                                                                                                                             |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **omni-rust agent** (new) | Single binary (or Rust crate). **MCP client**: loads one or more MCP servers from config (port/URL/stdio). Runs the agent loop: session, HTTP/stdio, LLM client, ReAct loop; for each tool call, uses MCP (tools/list, tools/call) against configured server(s). |
| **Python**                | **MCP server only.** `omni mcp` (or equivalent) exposes our skills as MCP tools. No agent loop in Python for this path; Python = tool provider.                                                                                                                  |
| **Config**                | List of MCP servers (e.g. SSE URL, stdio command). Same idea as Cursor/Claude Code MCP config.                                                                                                                                                                   |

So: **Rust agent runs → reads config → connects to MCP server(s) → runs loop → calls LLM and MCP tools.** Python is one (or more) of those MCP servers.

---

## 2. Current State vs Next

| Layer                    | Today                                                          | Next (Rust agent path)                                                              |
| ------------------------ | -------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Gateway / session / loop | Python (`omni gateway`, `execute_task_with_session`, OmniLoop) | **Rust**: gateway, session, loop, LLM client                                        |
| Tool execution           | Python kernel + MCP server in same process                     | **Python MCP server** (separate process or same host); Rust agent is **MCP client** |
| Session window           | Rust (omni-window) used from Python                            | Rust agent uses **omni-window** natively                                            |
| Memory / recall          | Rust omni-memory, called from Python                           | Rust agent calls **omni-memory** (existing Rust APIs)                               |
| MCP                      | Python MCP server (tools)                                      | **Unchanged**: Python = MCP server. Rust agent **loads** it by config (port/URL).   |

---

## 3. Implementation Phases (What We Build Next)

### Phase A: MCP client in Rust (foundation) — **Done**

- **A.1** Crate **omni-mcp-client** added: MCP client using `rmcp` (Streamable HTTP + Stdio). `OmniMcpClient::connect_streamable_http` / `connect_stdio`; then `list_tools`, `call_tool`. Config: `McpServerTransportConfig` (see [codex-rs-mcp-learnings.md](./codex-rs-mcp-learnings.md)).
- **A.2** Integration test: Rust client connects to **existing** `omni mcp` (Python) SSE server; mock server test runs without real MCP.

**Outcome**: Rust can talk to our Python MCP server. Foundation for “load MCP servers by config”.

### Phase B: Minimal Rust agent loop (single turn) — **Done**

- **B.1** Crate **omni-agent**: **session store** (in-memory `SessionStore`), **LLM client** (OpenAI-compatible `LlmClient::chat` with optional tools).
- **B.2** **One-turn loop**: `Agent::run_turn(session_id, user_message)` — history + user → optional MCP tools/list → LLM → tool_calls → MCP tools/call → repeat until done. Config: `AgentConfig` (inference URL, model, API key from env or field, MCP server list). Example: `cargo run -p omni-agent --example one_turn -- "message"`.

**Outcome**: Rust crate that (1) loads MCP server from config, (2) runs one user turn with LLM + MCP tools, (3) returns the reply. No gateway yet.

### Phase C: Rust gateway (HTTP + stdio)

- **C.1** **HTTP**: Rust HTTP server (e.g. axum or actix): POST /message with body `{ "session_id", "message" }`; session per session_id (use omni-window in Rust); for each message run the agent loop (B), return JSON `{ "output", "session_id" }`.
- **C.2** **Stdio**: Optional stdio mode (like `omni agent` today): read line from stdin, run loop, print reply; session_id from flag or default.
- **C.3** **Config**: Same MCP server list; optional `--mcp-url` / config file for “which MCP server(s)” so we can point to different MCP servers (e.g. Python skills, or another team’s MCP).

**Outcome**: “omni-rust agent” that can run as gateway (HTTP or stdio) and load MCP by config, like Cursor/Claude Code.

### Phase D: Parity and polish

- **D.1** **Multiple MCP servers**: Config allows multiple entries; Rust agent merges tools from all (tools/list from each server; tools/call routed to the right server by tool name or server id). Same behaviour as Cursor loading several MCP servers.
- **D.2** **omni-memory in Rust**: Hook two_phase_recall / store_episode into the Rust loop (we already have Rust omni-memory); optional consolidation after N turns.
- **D.3** **CLI surface**: e.g. `omni-rust agent` or `omni agent --rust` (if we keep a single `omni` CLI that can dispatch to Rust binary) or a dedicated `omni-rust` binary. Document “run Python MCP server (omni mcp), then run Rust agent with config pointing to that server”.

**Outcome**: Production-ready Rust agent: gateway (HTTP/stdio), session, LLM, MCP client loading one or more MCP servers from config; omni-memory optional; Python remains MCP server only.

---

## 4. What Stays in Python (No Duplication)

- **MCP server** (`omni mcp`): unchanged. Exposes skills as MCP tools (tools/list, tools/call). Can run as SSE on a port; Rust agent connects to that port.
- **Skill implementations**: all stay in Python (assets/skills, kernel, execute_tool). No reimplementation in Rust.
- **Optional**: Python gateway/agent (`omni gateway`, `omni agent` without Rust) remains for users who prefer single-process Python; Rust agent is an **alternative** path that uses MCP to talk to the same Python tools.

---

## 5. Summary: Next Steps in Order

| Step  | Deliverable                                                                                              |
| ----- | -------------------------------------------------------------------------------------------------------- |
| **A** | Rust MCP client (SSE + stdio), config for server URL/command; integration test with `omni mcp` (Python). |
| **B** | Minimal Rust agent loop: one turn, LLM + MCP tools, config (inference + MCP server list).                |
| **C** | Rust gateway: HTTP POST /message + stdio mode, session (omni-window), load MCP from config.              |
| **D** | Multiple MCP servers, omni-memory in loop, CLI surface and docs.                                         |

This is the implementation we do next: **Rust agent as MCP client, loading MCP server(s) by config (like Claude Code / Cursor), with Python as the MCP server.**
