# Next Steps: Rust Core and MCP — Audit and Roadmap

> **Purpose**: After agreeing on **Rust as core** and **Python as tool/script runtime** (with skills extensions for performance), this document audits the current state and lists the next steps so the team can see the direction clearly.

**Terminology**: **MCP** is the protocol; the **MCP server** is the component that _serves_ it (tools/list, tools/call, resources, prompts). It is a **pure MCP service**—no agent loop. The **agent** is the component that _uses_ MCP as a **client** (session, LLM, memory, gateway). Our current `omni mcp` is a **pure MCP server** implemented in Python. A “pure Rust MCP server” means reimplementing **that server** in Rust; the agent stays the client.

**Execution order**: We **start with the Rust agent**. Implement a **usable agent** (gateway, memory in loop, multi-MCP, CLI) that talks to the **current MCP server (Python)**. **Only after** we have that usable agent do we consider and start the migration to a **pure Rust MCP server**. So: Phase 1 first; Phase 2 and Phase 3 (Rust MCP server) follow once the agent is in place.

**Current priority (Feb 2026)**: Phase 1 is done. The **Python MCP server** (`omni mcp`) is fully functional. We **defer Phase 2–4** (Rust MCP server replacement) **indefinitely**.

**Core goal**: A conversational assistant—users talk to it (e.g. via Telegram), and it calls skills/tools + LLM to accomplish complex tasks. Users only chat; the assistant does the rest. This is what Nanobot/ZeroClaw achieve with Telegram. We will implement and stabilize this flow first; only then consider Rust MCP replacement. For now: complete and refine the Python MCP path.

---

## 1. Agreed Plan (Recap)

| Principle                   | Decision                                                                                                                                                                                                                                                                 |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Rust**                    | Core: MCP (server and/or client), transport, session, **memory (omni-memory: self-evolution, paper-based)** , executor (orchestration).                                                                                                                                  |
| **Python**                  | First-class **tool and script runtime**. No plan to migrate scripts to Rust; LangGraph, Prefect, and the Python ecosystem remain the default for skills.                                                                                                                 |
| **Skills extensions**       | When a script needs **high performance or robustness**, implement a **Rust (or other) extension** under `assets/skills/<skill>/extensions/`. Extensions are the extension point; not limited to Rust.                                                                    |
| **How Rust invokes Python** | **Option A** (short-term): Rust MCP server as front, tools/call forwarded to a **Python “tool runner”** service. **Option B**: Rust executor spawns Python scripts. **Option C**: PyO3 embeds Python in the Rust binary. Choice is spawn vs embed, not “replace Python.” |
| **Rust crates ecosystem**   | **Maximize use** of existing crates (`packages/rust/crates/`). Key driver for a **pure Rust MCP server**: the MCP server (tools/list, tools/call, resources) and the **agent** (memory, session, loop) can both use these crates directly.                               |

**Memory**: **omni-memory** (two_phase_recall, store_episode) is a **core** capability—our self-evolution feature based on the papers; it is not optional in the Rust agent loop.

**References**: [Pure Rust MCP Server Audit](./pure-rust-mcp-server-audit.md), [Omni Rust Agent Implementation](./omni-rust-agent-implementation.md).

---

## 2. Current State (Snapshot)

| Area                          | Status      | Notes                                                                                                                                                                      |
| ----------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Agent (Rust)**              | Done        | `omni-agent`: MCP **client**, session store, LLM client, one-turn loop; connects to MCP server(s) from config.                                                             |
| **Rust MCP client**           | Done        | `omni-mcp-client`: used by agent; Streamable HTTP + stdio; `list_tools`, `call_tool`; connects to MCP server.                                                              |
| **MCP server (Python)**       | Current     | `omni mcp`: **pure MCP server** (stdio/SSE). tools/list, tools/call via kernel, resources, prompts. No agent logic.                                                        |
| **MCP server (Rust)**         | Not started | Pure Rust MCP server not implemented yet; audit and options (A/B/C) documented.                                                                                            |
| **Tool list source for Rust** | Partial     | Rust can get tools via MCP (from Python). For a **Rust MCP server**, Rust would need to read a manifest or skill index (e.g. omni-vector) or call Python “list tools” API. |
| **Python tool runner API**    | Not started | Would be needed for Option A (Rust MCP front calling Python for tools/call).                                                                                               |
| **Skills extensions**         | Exists      | `SkillExtensionLoader`, FixtureManager; per-skill `extensions/` (e.g. git/rust_bridge, memory/rust_bridge). No formal “extension contract” doc yet.                        |
| **Rust gateway**              | Done        | omni-agent: HTTP POST /message, stdio, repl; graceful shutdown (SIGINT/SIGTERM); validation, timeout, concurrency limit.                                                   |

**Rust crates to leverage**: When implementing the **agent** (gateway, loop, memory) and the **MCP server** (tools/list, tools/call, resources), we should **maximize use** of existing crates. See [Pure Rust MCP Server Audit §2.1](./pure-rust-mcp-server-audit.md#21-why-pure-rust-mcp-maximize-our-rust-crate-ecosystem) for the full table. Key ones: **omni-memory** (loop), **omni-vector** / **xiuxian-wendao** (index, resources), **omni-scanner** (tools/list source), **omni-executor** / **omni-sandbox** (tools/call if Option B), **omni-window** (session), **omni-mcp-client** / **omni-agent** (client path).

---

## 3. Next Steps (Ordered)

### Phase 1 — Rust agent path (use current Python MCP)

**Goal**: Rust **agent** as a usable gateway that talks to the **existing MCP server** (Python). No change to the MCP server yet.

| Step    | What                            | Outcome                                                                                                                                                                    | Deps         |
| ------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ |
| **1.1** | **Rust gateway (HTTP + stdio)** | HTTP server (e.g. axum): POST /message with session_id + message; run agent loop; return reply. Optional stdio mode. Config: MCP server list (e.g. SSE URL of `omni mcp`). | Phase B done |
| **1.2** | **Multiple MCP servers**        | Config allows multiple MCP entries; agent merges tools from all; tools/call routed to correct server.                                                                      | 1.1          |
| **1.3** | **omni-memory in loop**         | Hook two_phase_recall / store_episode into Rust agent loop (Rust omni-memory). **Core**: memory is our self-evolution / paper-based heavyweight feature, not optional.     | 1.1          |
| **1.4** | **CLI and docs**                | e.g. `omni agent --rust` or `omni-rust agent`; doc: “Start `omni mcp --transport sse`, then start Rust agent with MCP URL.”                                                | 1.1          |

**Outcome**: Production-ready **Rust agent** (MCP client + loop + memory + gateway). The **MCP server** stays the current one (Python). No Rust MCP server yet.

**Implementation steps (for audit)**: [Rust Agent: Implementation Steps](./rust-agent-implementation-steps.md) — ordered list (HTTP gateway, stdio, config, multiple MCP, omni-memory, CLI/docs). Approve there, then we start.

---

### Phase 2 — Prepare for Rust MCP server (Option A) — _Deferred_

**Goal**: Enable a future **Rust MCP server** that uses **Python as tool runner** (Option A). Minimal change to current Python; add contract and one API.

**Status**: Deferred indefinitely. Reference projects (Nanobot, ZeroClaw) have many features we lack (e.g. Telegram). Implement and stabilize those first; revisit Rust MCP replacement only after feature parity.

| Step    | What                          | Outcome                                                                                                                                                                                                                                                                            | Deps          |
| ------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| **2.1** | **Tool list source for Rust** | Define and implement: (a) **manifest** (e.g. JSON) generated at `omni sync` / build from skill index that Rust can read, or (b) **read from omni-vector** skill table if Rust already has access. So “Rust MCP server” can implement tools/list without calling Python.            | None          |
| **2.2** | **Python “tool runner” API**  | Add a small HTTP (or IPC) API to the Python side: e.g. `POST /run_tool` with `{ "command", "arguments" }`; handler calls `kernel.execute_tool`, returns result. Same process as `omni mcp` or a dedicated “tool runner” service. Document contract (timeout, heartbeat if needed). | Kernel exists |
| **2.3** | **Contract doc**              | One-page: “Tool runner API contract” (request/response, errors, timeout). So a Rust MCP server can be implemented against it later.                                                                                                                                                | 2.2           |

**Outcome**: When we implement the Rust MCP server, we can do tools/list from Rust (manifest or index) and tools/call by calling the Python tool runner API. No Rust MCP server implementation in this phase.

---

### Phase 3 — Pure Rust MCP server (Option A) — _Deferred_

**Goal**: Implement the **Rust MCP server** as front: protocol + transport in Rust; tools/list from Rust; tools/call forwarded to Python tool runner.

**Status**: Deferred indefinitely. Same as Phase 2: implement reference-project features first, then consider replacement.

| Step    | What                       | Outcome                                                                                                                                                                                                                   | Deps          |
| ------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- |
| **3.1** | **Rust MCP server crate**  | New crate (e.g. `omni-mcp-server` or under existing structure): rmcp server (StreamableHttpService + stdio). Handlers: initialize, tools/list (from manifest or Rust registry), tools/call → HTTP to Python tool runner.  | Phase 2, rmcp |
| **3.2** | **resources/prompts**      | Either: (1) Rust MCP calls Python for resources/prompts (add endpoints to tool runner or existing server), or (2) stub in Rust for v1 (e.g. empty or file-based prompts only).                                            | 3.1           |
| **3.3** | **Integration and switch** | Integration test: Rust MCP server + Python tool runner; client (Rust agent or Codex) connects to Rust MCP. Document how to run “Rust MCP + Python runner” and optionally deprecate or keep Python MCP server as fallback. | 3.1, 3.2      |

**Outcome**: **Pure Rust MCP server** in front; Python is the tool runner backend. Same tool surface for Codex/Gemini and Rust agent.

---

### Phase 4 — Optional: Option B or C, and extensions

**Goal**: If we want **one Rust process** (Option B) or **one binary** (Option C), or to formalize extensions.

| Step    | What                         | Outcome                                                                                                                                                                                                                                                                   | Deps                                                     |
| ------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| **4.1** | **Option B — Rust executor** | Rust MCP server calls a **Rust executor** instead of Python tool runner: executor has run-spec per tool, spawns e.g. `python -m omni.skills.run …`. Timeout/heartbeat in Rust. Python = script payload only for MCP path.                                                 | Phase 3, [rust-skill-executor](./rust-skill-executor.md) |
| **4.2** | **Option C — PyO3 embed**    | Rust MCP server embeds Python (PyO3), loads kernel once, calls `kernel.execute_tool` in-process. Single binary.                                                                                                                                                           | Phase 3, build/packaging                                 |
| **4.3** | **Extensions contract**      | Document the **extension contract**: how a skill adds an extension (rust_bridge, sniffer, fixtures), what the loader expects, and that extensions can be Rust or other runtimes. Optional: stabilize a small “extension manifest” per skill if needed for Rust tool list. | Current extensions                                       |

**Outcome**: Either (B) Rust-only process + spawn Python, or (C) one binary with embedded Python; plus a clear extension contract for skills.

---

## 4. Summary: What to Do Next

| Order | Focus                               | Status                                                                                                          |
| ----- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **1** | **Rust agent** (usable)             | **Done**. Phase 1 complete: gateway, stdio, repl, memory, CLI. Uses Python MCP server.                          |
| **2** | **Python MCP path** (current focus) | **In progress**. Complete and refine: E2E runs, tests, docs, robustness. Python MCP server is fully functional. |
| **3** | Prepare Rust MCP server             | **Deferred**. Phase 2: Tool list source, Python tool runner API. Revisit after Python path is solid.            |
| **4** | Pure Rust MCP server                | **Deferred**. Phase 3.                                                                                          |
| **5** | Option B/C, extensions              | **Deferred**. Phase 4.                                                                                          |

**Current focus**: Run the full stack (Rust agent + Python MCP) end-to-end, harden it, and polish the experience. Then implement features our reference projects have (e.g. Telegram). **No Rust MCP server replacement** until our feature set matches and flows. Replacement is out of scope for now.

---

## 5. Dependencies at a Glance

```
Phase 1 (Rust agent gateway)  →  no new deps; uses existing Python MCP
Phase 2 (Prepare Rust MCP)     →  none
Phase 3 (Rust MCP server)      →  Phase 2 (tool list + tool runner API)
Phase 4 (B/C, extensions)     →  Phase 3
```

**Backlog**: Align with [docs/backlog.md](../backlog.md) by feature name. These steps can be added as features (e.g. “Rust agent gateway”, “Python tool runner API”, “Pure Rust MCP server”) and tracked there.
