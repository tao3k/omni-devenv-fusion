# Nanobot / ZeroClaw Alignment and Optimizations

> **Nanobot** and **ZeroClaw** are our **primary reference projects**. We must study their architecture, code, and logic—understand _how_ they implement features—before deciding _how_ we implement. This is the first priority.
>
> **Core goal**: A conversational assistant—users talk to it (e.g. via Telegram), and it calls skills/tools + LLM to accomplish complex tasks. Users only chat; the assistant does the rest. This is what Nanobot and ZeroClaw achieve.
>
> **Primary goal**: Implement the feature set of Nanobot and ZeroClaw so that omni-agent delivers parity.  
> **Secondary goal**: Optimize better than they do, based on our framework—differentiators without reimplementing their stack.

---

## 1. Alignment Priorities

| Priority           | Meaning                                                                                                                                                                                   |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Feature parity** | Session, memory/consolidation, gateway, agent loop, and recall-in-context match or exceed what Nanobot and ZeroClaw offer.                                                                |
| **Then optimize**  | Use our stack (omni-memory two-phase recall, omni-window, single MCP surface) to do the same job better: faster hot path, richer memory, one tool surface for agent and external clients. |

Reference methodology: [reference-nanobot-zeroclaw-review.md](./reference-nanobot-zeroclaw-review.md) — adopt strengths, avoid pitfalls, update when we touch each area.

---

## 2. Feature Parity Checklist

What the references provide and what we implement.

### 2.1 Session and history

| Capability             | Nanobot / ZeroClaw               | Omni (omni-agent)                            | Status |
| ---------------------- | -------------------------------- | -------------------------------------------- | ------ |
| Session by id          | SessionManager / channel:chat_id | `session_id` in run_turn, gateway, stdio     | Done   |
| Bounded history        | History cap, overflow handling   | `window_max_turns` → omni-window ring buffer | Done   |
| Recent context for LLM | Last N turns / tokens            | `get_recent_messages(session_id, limit)`     | Done   |
| No unbounded list      | Avoid OOM on long chats          | Ring buffer drops oldest when full           | Done   |

**Avoid**: Unbounded message list; consolidating without outcome feedback.

### 2.2 Memory and consolidation

| Capability                 | Nanobot / ZeroClaw             | Omni (omni-agent)                                                 | Status |
| -------------------------- | ------------------------------ | ----------------------------------------------------------------- | ------ |
| Episodic memory            | MEMORY.md / SQLite + vector    | omni-memory EpisodeStore                                          | Done   |
| Recall into context        | Memory window / hybrid search  | `two_phase_recall(intent)` → system message before LLM            | Done   |
| Store after turn / segment | store_episode, consolidation   | Per-window consolidation: drain oldest → store Episode + update_q | Done   |
| Utility feedback           | Success/failure signal         | update_q(episode_id, reward) 1.0 / 0.0                            | Done   |
| Consolidation trigger      | When history exceeds threshold | `consolidation_threshold_turns` + `consolidation_take_turns`      | Done   |

**Avoid**: Consolidating without summarising intent/outcome; skipping utility feedback.

### 2.3 Gateway and transport

| Capability                 | Nanobot / ZeroClaw           | Omni (omni-agent)                                   | Status |
| -------------------------- | ---------------------------- | --------------------------------------------------- | ------ |
| One loop for all modes     | MessageBus, single process   | gateway / stdio / repl share one agent loop         | Done   |
| HTTP gateway               | POST /message → reply        | axum POST /message, configurable bind               | Done   |
| Stdio / CLI                | Read line → run turn → print | `omni-agent stdio`, `repl` (interactive or --query) | Done   |
| No new process per request | Single daemon                | One agent process; MCP can be separate              | Done   |

**Avoid**: Starting a new process per request; duplicating tool surface.

### 2.4 Agent loop (LLM + tools)

| Capability                 | Nanobot / ZeroClaw          | Omni (omni-agent)                                            | Status |
| -------------------------- | --------------------------- | ------------------------------------------------------------ | ------ |
| Context = history + memory | history + memory window     | messages = recall (system) + window/history + current user   | Done   |
| Tool loop                  | Tool trait / MCP            | MCP tools/list, tools/call; qualified names for multi-server | Done   |
| Max tool rounds            | Cap to avoid infinite loops | `max_tool_rounds`                                            | Done   |
| Append turn on success     | Persist to session          | append_turn (window or SessionStore)                         | Done   |

**Avoid**: Unbounded tool rounds; skipping session append on success.

---

## 3. Where We Optimize Better

Built on our framework; we do not reimplement their stacks.

| Area              | Reference typical approach                    | Our optimization                                                                                                          |
| ----------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Memory recall** | Vector search or hybrid (FTS + vector)        | **Two-phase recall**: semantic (k1) → Q-value rerank (k2, λ). Utility feedback (update_q) improves future recall.         |
| **Session**       | Fixed cap or token limit                      | **omni-window**: ring buffer, O(1) append, configurable `window_max_turns`; consolidation drains oldest into omni-memory. |
| **Tools**         | Native implementations or adapters per client | **Single MCP surface**: omni-agent and Codex/Gemini use same MCP server; no duplicate tool implementations.               |
| **LLM**           | One or few backends in agent binary           | **LiteLLM (or bridge)**: one HTTP endpoint, 100+ providers; no provider logic in Rust.                                    |
| **Hot path**      | Mixed language / process hops                 | **Rust-only hot path**: loop, session, memory, gateway, MCP client in Rust; only LLM and tool execution are external.     |

See [rust-agent-architecture-omni-vs-zeroclaw.md](./rust-agent-architecture-omni-vs-zeroclaw.md) for the full comparison and performance notes.

---

## 4. Implementation Steps (Done vs Next)

From [rust-agent-implementation-steps.md](./rust-agent-implementation-steps.md):

- **Steps 1–8**: Done (gateway, stdio, MCP config, multiple MCP, memory in loop, CLI, session window, consolidation).
- **Recall in loop**: Done — `run_turn` calls `two_phase_recall(user_message, k1, k2, λ)` when `config.memory` is set and injects a system message with relevant past experiences before the conversation.

**Done (this pass)**:

- **Per-turn store_episode**: When memory is enabled, each successful turn is stored as one episode (intent=user message, experience=assistant message, outcome=completed/error); consolidation still drains oldest segment when window is full.
- **Gateway graceful shutdown**: `run_http` uses `axum::serve(...).with_graceful_shutdown(shutdown_signal())`; Ctrl+C (SIGINT) stops the server after in-flight requests complete.
- **Reference review**: Filled Nanobot/ZeroClaw rows in [reference-nanobot-zeroclaw-review.md](./reference-nanobot-zeroclaw-review.md) for session, memory, gateway, and loop (adopt/avoid).

**Done (this pass)**:

- **Gateway request validation**: POST /message returns 400 for empty or whitespace-only `session_id` or `message`; trimmed values are used. Unit tests in `gateway::http::tests`.
- **Gateway timeout**: Each turn limited to 300s (TURN_TIMEOUT_SECS); on timeout returns 504 Gateway Timeout so connections do not hang.
- **Consolidation summarisation tests**: Unit tests for `summarise_drained_turns` (intent = first user, experience = assistant(s), outcome = completed/error) in `agent::tests`.

**Done (this pass)**:

- **SIGTERM support**: On Unix, gateway listens for both Ctrl+C (SIGINT) and SIGTERM; either triggers graceful shutdown. On Windows, Ctrl+C only.
- **Configurable turn timeout**: `run_http(agent, bind_addr, turn_timeout_secs: Option<u64>)`; CLI `omni-agent gateway --turn-timeout 120`; default 300s when None.

**Done (this pass)**:

- **Concurrency limit**: `run_http(..., max_concurrent_turns: Option<usize>)`; when Some(n), a semaphore limits concurrent agent turns; excess requests wait for a slot. CLI `omni-agent gateway --max-concurrent 4`. None = no limit.

**Next (mandatory)**:

- **Study their source**: Before implementing each area, inspect Nanobot and ZeroClaw repos—architecture, code paths, design decisions. Document in [reference-nanobot-zeroclaw-review.md](./reference-nanobot-zeroclaw-review.md).
- **Progress comparison**: Keep [§6 Progress Comparison](#6-progress-comparison) up to date as we implement.

---

## 6. Progress Comparison

**Where we are vs Nanobot vs ZeroClaw.** Update this table as we implement.

| Area                 | Nanobot                                                                 | ZeroClaw                                                      | Omni                                                             | Notes         |
| -------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------- | ---------------------------------------------------------------- | ------------- |
| **Agent loop**       | AgentLoop, context = history + memory                                   | Trait-based Provider/Tool                                     | run_turn, two_phase_recall, MCP                                  | Done          |
| **Session**          | SessionManager, channel:chat_id                                         | Trait-based session/state                                     | session_id, omni-window                                          | Done          |
| **Memory**           | MEMORY.md, consolidation                                                | SQLite + FTS + vector, hybrid                                 | omni-memory, two-phase recall                                    | Done          |
| **Gateway**          | MessageBus, POST /message                                               | Webhook, pairing                                              | axum POST /message                                               | Done          |
| **Stdio/CLI**        | `nanobot agent`                                                         | `zeroclaw agent`                                              | `omni agent`, `omni-agent repl`                                  | Done          |
| **Chat channels**    | Telegram, Discord, WhatsApp, Feishu, Slack, Email, QQ, DingTalk, Mochat | Telegram, Discord, Slack, iMessage, Matrix, WhatsApp, Webhook | Telegram (group+user sessions, polling/webhook, background jobs) | In Progress   |
| **MCP**              | Stdio + HTTP, config in tools.mcpServers                                | —                                                             | Python MCP server (omni mcp)                                     | Done (Python) |
| **Scheduled tasks**  | `nanobot cron`                                                          | heartbeat                                                     | `omni-agent schedule` (interval, max-runs, drain-on-exit)        | In Progress   |
| **Identity/persona** | —                                                                       | OpenClaw (IDENTITY.md), AIEOS                                 | —                                                                | Todo          |
| **Security**         | allowFrom, restrictToWorkspace                                          | Pairing, sandbox, allowlists                                  | Webhook secret + dedup backend; allowlist hardening in progress  | In Progress   |
| **Docker**           | Yes                                                                     | —                                                             | —                                                                | Todo          |

**Repos to study**:

- **Nanobot**: [github.com/HKUDS/nanobot](https://github.com/HKUDS/nanobot) — `agent/`, `channels/`, `bus/`, `session/`, `skills/`
- **ZeroClaw**: [github.com/zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw) — `src/` (traits: Provider, Channel, Tool, Memory)

---

## 7. Changelog

- Initial doc: alignment goals (parity first, then optimize), feature parity checklist, “where we optimize better”, link to implementation steps and reference review.
- Scheduled tasks parity moved to In Progress: `omni-agent schedule` implemented with interval execution, bounded runs, and completion drain handling.
- Channel architecture modularized: Telegram and job-manager internals now use directory modules with `mod.rs` export control; tests moved to `tests/` for complex modules.
