# Omni Run: Roadmap Aligned with Nanobot, OpenClaw, and ZeroClaw

> The current `omni run` design does not match the intended product: a **gateway-first, one-loop** assistant that can run as a daemon and serve users via CLI or channels (like Nanobot and OpenClaw/ZeroClaw). This document provides a **concrete roadmap** to redesign and implement `omni run` (and related commands) so it can deliver that experience, using existing MCP + skills and the planned Rust window + omni-memory.

## Principle: Long-Term Target Is the Baseline

**The current `omni run` implementation is wrong.** All design and implementation work must be guided by the **long-term target**, not by preserving the existing behaviour:

- **Target**: One agent loop (kernel + router + OmniLoop) that serves both CLI and gateway; session-aware; MCP as the single tool surface; optional Rust window and omni-memory for scale and self-evolution; optional channels. See §3 Target Shape and §4 Phased Roadmap.
- **Implication**: Any change to `omni run` (or new `omni agent` / `omni gateway`) should move toward this target. Do not add features that lock in the old “one-shot MCP client” or “no session, no gateway” model. Prefer refactors that make Phase 2 (gateway) and Phase 3 (session window) natural next steps.

### Product Goal: Same Capabilities as Nanobot and ZeroClaw

We aim for **functional parity** with Nanobot and ZeroClaw (and OpenClaw where relevant): one agent loop, gateway/daemon mode, session per conversation, MCP as the tool surface, optional channels and onboarding. The phased roadmap and target shape above are the concrete plan to get there; every phase should deliver capabilities that users of Nanobot or ZeroClaw would recognise.

### How We Get There: Leverage Our Stack, Don’t Rebuild

We reach that parity **by extending and reusing the current omni framework**, not by reimplementing their designs from scratch. Our advantages to build on:

- **Skills + MCP (our model, not theirs)**: Our skills management and MCP integration are **different** from Nanobot and ZeroClaw: metadata-driven skill index, discovery by intent, JIT install, single `@omni("skill.command")` surface, MCP server that exposes skills as tools. We keep and evolve this design—no need to adopt their tool registry or channel wiring.
- **Kernel + router**: In-process agent loop, Cortex, query normalisation, route-to-tool. Gateway = same loop with a different transport.
- **Omni-memory**: Two-phase recall, consolidation, vector + graph. Use it for session context and long-horizon runs instead of adding a separate memory system.
- **Rust bindings**: omni-vector, tokenizer, future omni-window. Use for performance-critical path (e.g. session window at 1k–10k steps) rather than rewriting in Python.
- **Config and SSOT**: `PRJ_*`, `get_setting()`, skill/config layout. Align gateway and session with existing project structure.

So: **same product shape as Nanobot/ZeroClaw, but implemented by evolving our stack.** Reuse router, skills, MCP, omni-memory, and Rust where they fit; add only gateway, session, and (later) channels as new layers on top.

### Reference methodology: review source, adopt strengths, avoid pitfalls

Both reference projects have **fixed, inspectable source code**. We must proceed with **active review and reference** of their implementations, not only high-level descriptions:

- **Review and reference**: Before implementing a feature that parallels theirs (e.g. session window, consolidation, gateway loop), inspect the relevant paths in their repos (Nanobot: [HKUDS/nanobot](https://github.com/HKUDS/nanobot); ZeroClaw: [zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw) or local `.cache/researcher/zeroclaw-labs/zeroclaw/`).
- **Adopt strengths**: Document and adopt patterns that improve correctness, performance, or maintainability (e.g. one loop for CLI and gateway, trait-based extensibility, bounded session).
- **Avoid pitfalls**: Explicitly identify weaknesses or disadvantages in their code (e.g. unbounded growth, missing error handling, tight coupling) and **design our implementation to avoid them** so our code is more robust and higher quality.
- **Living checklist**: Maintain [reference-nanobot-zeroclaw-review.md](./reference-nanobot-zeroclaw-review.md) with “strengths to adopt” and “pitfalls to avoid” per area (session, memory, gateway, loop). Update it when we review their source; use it when implementing Steps 7–8 and beyond.

---

## 1. Reference Implementations

### 1.1 Nanobot ([HKUDS/nanobot](https://github.com/HKUDS/nanobot))

- **Stack**: Python, ~4k LOC.
- **Entry points**: `nanobot agent` (interactive chat), `nanobot agent -m "..."` (one-shot), `nanobot gateway` (long-running, connects channels).
- **Loop**: Single `AgentLoop`; `run()` blocks on `MessageBus.consume_inbound()`; each message → session (by `channel:chat_id`) → context (history + memory window) → LLM + tools → `publish_outbound()`. CLI uses `process_direct()` so **one loop serves both CLI and gateway**.
- **Tools**: Built-in (file, shell, web, message, spawn, cron) + **MCP** (lazy connect, same registry).
- **Session**: `SessionManager` per key; history capped; overflow → async memory consolidation (MEMORY.md / HISTORY.md).
- **Takeaway**: One process, one loop, one tool registry; gateway = same loop + channel adapters.

### 1.2 OpenClaw ([openclaw/openclaw](https://github.com/openclaw/openclaw))

- **Stack**: TypeScript/Node, Gateway WebSocket control plane.
- **Entry points**: `openclaw agent` (CLI), `openclaw agent -m "..."`, `openclaw gateway` (WS server); clients (macOS app, WebChat, CLI) connect to the same Gateway.
- **Loop**: Pi agent in RPC mode; serialized **per session**; intake → context assembly → model → tools → streaming → persistence. See [Agent Loop](https://docs.openclaw.ai/concepts/agent-loop).
- **Session**: Session model (main, groups, activation modes, queue modes); session write lock; bootstrap/context files + skills injected.
- **Channels**: WhatsApp, Telegram, Slack, Discord, Google Chat, Signal, iMessage, BlueBubbles, Teams, Matrix, Zalo, WebChat.
- **Takeaway**: Gateway = control plane; agent loop is the single authoritative path; CLI and channels are clients of the same loop.

### 1.3 ZeroClaw ([zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw))

- **Stack**: **Rust**, single binary (~3.4MB), &lt;10ms startup, &lt;5MB RAM.
- **Entry points**: `zeroclaw agent -m "..."`, `zeroclaw agent` (interactive), `zeroclaw gateway` (webhook server), `zeroclaw daemon` (full autonomous runtime), `zeroclaw service install` (background service).
- **Architecture**: **Trait-based** — Provider, Channel, Memory, Tool, RuntimeAdapter, SecurityPolicy, IdentityConfig, Tunnel. All swappable via config.
- **Memory**: SQLite + FTS5 + vector cosine similarity (hybrid); no Pinecone/Elasticsearch.
- **Security**: Pairing (6-digit code → bearer token), workspace-only by default, allowlists, tunnel for public exposure.
- **CLI**: `onboard` (wizard), `doctor`, `status`, `channel doctor`, `integrations info <channel>`.
- **Takeaway**: One binary, one agent loop; gateway/daemon/service are **modes** of the same runtime; traits keep core clean and extensible.

**Local reference**: If you have a researcher harvest or clone of ZeroClaw at `.cache/researcher/zeroclaw-labs/zeroclaw/`, use it for deep-dive on trait layout, gateway API, and memory/skills loading.

---

## 2. Where Omni Run Is Today vs Where It Should Be

| Dimension               | Nanobot / OpenClaw / ZeroClaw                                                           | Current omni run                                                            |
| ----------------------- | --------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Default single task** | One process runs the **full agent** (load skills, route, LLM, tools).                   | Default was MCP HTTP client only (fixed recently to use kernel in-process). |
| **Interactive chat**    | `agent` with no args = REPL using **same** loop as gateway.                             | `omni run --repl` = separate MCP client loop; not same as kernel loop.      |
| **Gateway / daemon**    | One long-lived process; accepts messages from CLI or channels; **one loop** serves all. | No gateway; no daemon; every `omni run` starts and stops kernel.            |
| **Session**             | Per conversation (e.g. channel:chat_id); history + optional consolidation.              | No persistent session; one-off run.                                         |
| **Onboarding**          | `onboard` (wizard) or config file; `doctor` for diagnostics.                            | No onboard; config scattered.                                               |
| **Performance**         | ZeroClaw: &lt;10ms startup. Nanobot: lightweight. OpenClaw: heavier but single gateway. | Full kernel + Cortex each run; cold start heavy; no reuse.                  |

So: **omni run** today is neither a proper “agent CLI” (one-loop, same path as gateway) nor a gateway-first product. The roadmap below corrects that.

---

## 3. Target Shape (What We Build Toward)

- **One loop**: A single agent loop (kernel + router + OmniLoop, or equivalent) that can serve:
  - **CLI**: `omni run "task"` (one-shot) and `omni run` or `omni agent` (interactive) using that loop.
  - **Gateway**: Long-lived process (`omni gateway` or `omni mcp` in gateway mode) that accepts messages (stdio first, then webhook/SSE) and runs the **same** loop per message.
- **Session**: Per conversation (e.g. `stdio:default` or `channel:telegram:123`); bounded history; optional consolidation into omni-memory.
- **MCP as tool surface**: All skills exposed via MCP; gateway and CLI both use the same kernel/MCP server so there is no “second tool layer”.
- **Rust window + omni-memory**: For long runs (1k–10k tool calls), use Rust session window + CheckpointStore + omni-memory (two-phase recall, consolidation) as in [omni-run-react-gateway-design.md](./omni-run-react-gateway-design.md).
- **Optional later**: Onboard wizard, `omni doctor`, channel adapters (Telegram, webhook), pairing/tunnel (inspired by ZeroClaw/OpenClaw).

---

## 4. Phased Roadmap

### Phase 0: Correct Default Path (Done)

- **Done**: Default `omni run "task"` calls `execute_task_via_kernel()` so one command runs the in-process agent. `--fast` tries MCP first, then falls back to kernel.
- **Doc**: [omni-run-rewrite-plan.md](./omni-run-rewrite-plan.md).

### Rust agent: Gateway parity (Phase 2 in practice)

The **omni-agent** binary delivers Phase 2 “gateway / one loop” in practice, aligned with Nanobot and ZeroClaw:

- **Entry points**: `omni-agent gateway` (HTTP POST /message), `omni-agent stdio`, `omni-agent repl` (interactive or `--query` one-shot). One loop serves all.
- **MCP**: Loads from **mcp.json** only; inference URL inferred from first HTTP server when not set (same port = no API key in Rust process).
- **Session**: In-memory per `session_id`; optional omni-memory (recall + store_episode) when `config.memory` is set.
- **Doc**: [rust-agent-implementation-steps.md](./rust-agent-implementation-steps.md), [omni-agent README](../../packages/rust/crates/omni-agent/README.md).

**Next (Phase 3 alignment)**: Replace or back the in-memory session with **omni-window** (ring buffer, `get_recent_for_context`) and add **consolidation** (when window full → store_episode + mark_success/failure into omni-memory). See Step 7–8 in [rust-agent-implementation-steps.md](./rust-agent-implementation-steps.md).

### Phase 1: Thin CLI + Extract Graph (Short Term)

- **1.1** Extract LangGraph Robust Workflow from `run.py` into a dedicated module (e.g. `omni.agent.workflows.robust_task.runner`). `run.py` only: `if graph: run_async_blocking(run_graph_workflow(task)); return`.
- **1.2** Shrink `run.py` to parsing + delegation; no 400-line inline graph.
- **1.3** (Optional) REPL: either keep MCP-client REPL with clear docs, or add an in-process REPL that calls `execute_task_via_kernel` per user message (same loop as single task).

**Outcome**: Single-task and graph paths are correct and maintainable; CLI is thin.

### Phase 2: Gateway / Daemon Mode (Core for “Like Nanobot / ZeroClaw”)

- **2.1** Define **gateway mode**: one long-lived process that (a) starts kernel once, (b) enters a message loop (stdio or socket/HTTP), (c) for each message: resolve session_id → load session context (from Rust window or simple in-memory buffer) → call `execute_task_via_kernel` (or router fast path + OmniLoop) → return response → optionally persist session.
- **2.2** **CLI surface**: `omni gateway` (or `omni run --gateway`) to start that process. Optional: `omni agent` as alias for interactive chat (if gateway is running, connect to it; else run in-process once per session). **Rust path**: `omni-agent gateway` / `stdio` / `repl` already provide this (one loop, MCP client, session per id).
- **2.3** **MCP**: Reuse existing MCP server: either (a) gateway process embeds the same MCP server (kernel already up, tools/list and tools/call served from it), or (b) gateway is an MCP client that calls an already-running `omni mcp`. Prefer (a) so one process = gateway + MCP. **Rust agent** uses (b): run `omni mcp --transport sse --port 3002`, point mcp.json at that URL; inference from same port (no API key in Rust).
- **Outcome**: User can run `omni gateway` and then talk to the same agent via stdio (or later webhook); no “run MCP in another terminal” for normal use. **Rust**: `omni-agent gateway` (or stdio/repl) + `omni mcp` in another process achieves this today.

### Phase 3: Session Window (Rust) + omni-memory

- **3.1** Implement **omni-window** (or equivalent): Rust-backed session window (ring buffer of turn metadata, refs to CheckpointStore), `append_turn`, `get_recent_for_context`, `get_stats`. Python binding.
- **3.2** Integrate with run_entry: when in “session mode” or gateway, create/reuse session window per session_id; after each turn append; when building context use window + CheckpointStore; when threshold exceeded, consolidate into omni-memory (store_episode + mark_success/failure) per [omni-run-react-gateway-design.md](./omni-run-react-gateway-design.md) §8.6.
- **3.3** Gateway uses session window so long conversations (and 1k–10k tool calls) don’t blow context.
- **Outcome**: One loop + session window + omni-memory; scalable and self-evolving.

### Phase 4: Channels and Transport (Optional)

- **4.1** **Stdio**: Gateway already reads from stdin, writes to stdout (like Nanobot CLI chat).
- **4.2** **Webhook/SSE**: Add HTTP endpoint(s) so external clients (e.g. Telegram bot, custom UI) can send a message and get a response; same loop, session_id from header or body.
- **4.3** **Channel adapters**: Optional adapters for Telegram, Discord, Slack (each pushes to the same message queue and gets replies); session_id = channel:chat_id.
- **Outcome**: Same behaviour as Nanobot/OpenClaw: one gateway, many channels; one loop.

### Phase 5: Onboarding and Ops (Optional)

- **5.1** **onboard**: Wizard or minimal `omni onboard` that writes config (API keys, model, workspace, optional tunnel).
- **5.2** **doctor**: `omni doctor` for config check, kernel/cortex health, MCP connectivity.
- **5.3** **service**: Optional `omni service install` to run gateway as a user-level service (launchd/systemd), like ZeroClaw.

---

## 5. Implementation Order Summary

| Phase | Focus                        | Deliverable                                                                                          |
| ----- | ---------------------------- | ---------------------------------------------------------------------------------------------------- |
| **0** | Fix default path             | ✅ `omni run "task"` uses kernel in-process                                                          |
| **1** | Thin CLI + graph extraction  | run.py &lt; 200 lines; graph in workflow module                                                      |
| **2** | Gateway / daemon             | `omni gateway` (or `omni run --gateway`); one process, one loop, stdio (and optionally MCP embedded) |
| **3** | Session window + omni-memory | Rust window + consolidation into omni-memory; gateway uses it                                        |
| **4** | Channels                     | Webhook/SSE; optional Telegram/Discord/Slack adapters                                                |
| **5** | Onboard / doctor / service   | Optional wizard, diagnostics, background service                                                     |

---

## 6. How This Matches Nanobot / OpenClaw / ZeroClaw

- **Nanobot**: One loop (AgentLoop), gateway + CLI share it, session per channel:chat_id, memory consolidation. We get there with Phase 2 (gateway, one loop) + Phase 3 (session window + consolidation).
- **OpenClaw**: Gateway as control plane, Pi agent loop serialized per session, many channels. We get there with Phase 2 + Phase 4 (channels); OpenClaw’s RPC/streaming can be a later refinement.
- **ZeroClaw**: Trait-based, one binary, gateway + daemon + service, onboard/doctor. We get there conceptually with Phase 2 (gateway/daemon), Phase 5 (onboard/doctor/service); our “traits” are Python interfaces + MCP + optional Rust window.

---

## 7. References

- **Nanobot**: [github.com/HKUDS/nanobot](https://github.com/HKUDS/nanobot) — agent loop, gateway, session, MCP.
- **OpenClaw**: [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw), [docs.openclaw.ai](https://docs.openclaw.ai) — Agent Loop, Gateway, session model, channels.
- **ZeroClaw**: [github.com/zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw) — traits, gateway API, onboard, doctor, memory, security.
- **Local ZeroClaw** (if present): `.cache/researcher/zeroclaw-labs/zeroclaw/` — use for deep-dive on source layout (e.g. `src/` for providers, channels, tools, memory).
- **Omni design**: [omni-run-react-gateway-design.md](./omni-run-react-gateway-design.md) — session window, MCP-first, omni-memory, Rust window.
- **Omni rewrite**: [omni-run-rewrite-plan.md](./omni-run-rewrite-plan.md) — current bugs and immediate fixes.
- **Design and implementation (consolidated)**: [omni-run-design-and-implementation.md](./omni-run-design-and-implementation.md) — naming (run / agent / gateway), leveraging omni-memory and Rust+Python, refactor plan.

This roadmap is the basis for implementing an `omni run` (and `omni agent` / `omni gateway`) that aligns with your intent and with Nanobot and OpenClaw/ZeroClaw-style behaviour.
