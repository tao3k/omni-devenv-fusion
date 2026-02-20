# Reference Review: Nanobot and ZeroClaw

> **Nanobot** and **ZeroClaw** are our **primary reference projects**. Before implementing any feature they have, we must (1) inspect their architecture and code, (2) understand how they implement it, (3) decide how we implement—adopting strengths and avoiding pitfalls.
>
> **Purpose**: Record **strengths to adopt** and **pitfalls to avoid** from their source. Use this doc when implementing features that parallel theirs so our code is robust and high-quality.

**How to use**: When touching an area (session, memory, gateway, loop, channels, etc.), (1) inspect the relevant paths in their repos, (2) add or update rows below, (3) apply “adopt” in our design and “avoid” in our implementation. **Alignment**: [nanobot-zeroclaw-alignment.md](./nanobot-zeroclaw-alignment.md) — feature parity first, then optimize.

---

## 1. Session and history

| Source       | Strengths to adopt                                                                                              | Pitfalls to avoid                                                                                                              |
| ------------ | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Nanobot**  | SessionManager; session by channel:chat_id; history cap for context; one loop for CLI and gateway (MessageBus). | Unbounded message list; no backpressure on overflow.                                                                           |
| **ZeroClaw** | Trait-based session/state; clear boundary between transport and agent; gateway/daemon as modes of same runtime. | Coupling if session and memory share one store without limits.                                                                 |
| **Omni**     | Bounded context via omni-window (ring buffer); get_recent_for_context; configurable max_turns.                  | Do not keep full message list in memory for long sessions; do not consolidate without outcome feedback (mark_success/failure). |

---

## 2. Memory and consolidation

| Source       | Strengths to adopt                                                                                                                                                                                                                                                                                | Pitfalls to avoid                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Nanobot**  | Memory window injected into context; consolidation when history exceeds threshold; MEMORY.md / HISTORY.md for design.                                                                                                                                                                             | Loss of context if consolidation too aggressive; no utility signal (success/failure) for recall.       |
| **ZeroClaw** | SQLite + FTS + vector; hybrid search for recall; persistent memory store.                                                                                                                                                                                                                         | No two-phase rerank (semantic only or single score); single store for all state.                       |
| **Omni**     | Two-phase recall (semantic → Q-value rerank); store_episode + update_q(reward); consolidation when window ≥ `consolidation_threshold_turns`: drain oldest turns, summarise (intent/experience/outcome), store Episode, update_q(1.0/0.0). Implemented: Step 8 in rust-agent-implementation-steps. | Do not consolidate without summarising intent/outcome; do not skip utility feedback (we use update_q). |

---

## 3. Gateway and transport

| Source       | Strengths to adopt                                                                                     | Pitfalls to avoid                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **Nanobot**  | One loop for CLI and gateway; MessageBus.consume_inbound / publish_outbound.                           | Error paths and graceful shutdown; backpressure when overloaded.       |
| **ZeroClaw** | Trait-based transport; gateway/daemon/service as modes of same runtime.                                | Connection handling, timeouts, and graceful shutdown on SIGTERM.       |
| **Omni**     | omni-agent: gateway, stdio, repl share one loop; MCP from config; gateway graceful shutdown on Ctrl+C. | Do not start a new process per request; do not duplicate tool surface. |

---

## 4. Agent loop (LLM + tools)

| Source       | Strengths to adopt                                                                                                                | Pitfalls to avoid                                                          |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **Nanobot**  | Single AgentLoop; session by channel:chat_id; context = history + memory window.                                                  | Tool failure handling; max rounds to avoid infinite loops.                 |
| **ZeroClaw** | Trait-based Provider/Tool; clear separation of concerns.                                                                          | Error propagation and timeouts for tool calls.                             |
| **Omni**     | run_turn: two_phase_recall → messages → LLM → tool_calls → MCP → repeat; max_tool_rounds; per-turn store_episode + consolidation. | Do not allow unbounded tool rounds; do not skip session append on success. |

---

## 5. Where to look in their repos

- **Nanobot**: [github.com/HKUDS/nanobot](https://github.com/HKUDS/nanobot) — Python; `agent/` (loop, context, memory, skills), `channels/` (Telegram, Discord, WhatsApp, etc.), `bus/` (MessageBus), `session/`, `skills/`, MCP in `tools.mcpServers`.
- **ZeroClaw**: [github.com/zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw) — Rust; `src/channels/` (Telegram, Discord, Slack, etc.), `src/providers/`, `src/tools/`, `src/memory/`, `src/` traits (Provider, Channel, Tool, Memory).

---

## 6. Chat channels (Telegram, Discord, etc.)

| Source       | Strengths to adopt                                                                                                                      | Pitfalls to avoid                                       |
| ------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| **Nanobot**  | `channels/` — Telegram, Discord, WhatsApp, Feishu, Slack, Email, QQ, DingTalk, Mochat; `nanobot gateway` runs all; allowFrom whitelist. | Polling vs webhook; QR for WhatsApp.                    |
| **ZeroClaw** | `Channel` trait; CLI, Telegram, Discord, Slack, iMessage, Matrix, WhatsApp, Webhook; pairing + allowlists.                              | Empty allowlist = deny all (secure default).            |
| **Omni**     | —                                                                                                                                       | Todo: study their channel architecture, then implement. |

---

## 7. Changelog

- Added chat channels section; clarified Nanobot/ZeroClaw as primary reference.
- Filled Nanobot/ZeroClaw rows (session, memory, gateway, loop) from alignment doc; added Omni gateway graceful shutdown and per-turn store.
- Initial template: reference methodology and structure for adopt/avoid per area.
