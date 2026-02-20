# Omni Run: ReAct Loop, Context Isolation, and Gateway Design

> Design analysis inspired by [Nanobot](https://github.com/HKUDS/nanobot) for an evolvable `omni run` with context isolation and optional background gateway for user communication and skill invocation.

---

## 1. Nanobot Analysis Summary

### 1.1 Architecture (from README + `agent/loop.py`)

| Layer          | Role                                                                                      | Omni analogue                                                   |
| -------------- | ----------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| **CLI**        | `nanobot agent` (interactive), `nanobot agent -m "..."` (one-shot), `nanobot gateway`     | `omni run "task"`, `omni run --repl`, (no gateway yet)          |
| **Agent loop** | `AgentLoop`: bus → context → LLM → tools → bus                                            | `OmniLoop`: kernel → router → ResilientReAct → tools            |
| **Gateway**    | Long-running process; connects channels (Telegram, Discord, etc.) to the same agent loop  | Not present                                                     |
| **Channels**   | Telegram, Discord, WhatsApp, Feishu, Slack, Email, QQ, Mochat                             | N/A (CLI only)                                                  |
| **Bus**        | `MessageBus`: `consume_inbound()` / `publish_outbound()`; one loop serves all channels    | Could map to a single "user message" queue + response sink      |
| **Session**    | `SessionManager` per `channel:chat_id`; history + memory consolidation                    | `session_id` per run; no cross-run session persistence for chat |
| **Memory**     | `MemoryStore` (MEMORY.md, HISTORY.md); consolidation when `len(messages) > memory_window` | Memory archiver + knowledge/memory skills; different shape      |
| **Tools**      | Built-in (file, shell, web, message, spawn, cron) + **MCP** (lazy connect)                | Skills (MCP-backed) + kernel; no spawn/cron as first-class      |
| **Subagent**   | `SpawnTool` + `SubagentManager`: run background task, reply later via bus                 | No equivalent; researcher chunked is sync                       |

### 1.2 Nanobot Agent Loop (Relevant Bits)

- **Single loop**: `run()` blocks on `bus.consume_inbound()` with timeout; each message → `_process_message()` → `_run_agent_loop()` (LLM + tool execution) → `publish_outbound()`.
- **Session key**: `channel:chat_id` (e.g. `telegram:123`) so history is per-conversation.
- **Context**: `ContextBuilder.build_messages(history, current_message, ...)`; history capped by `memory_window` (e.g. 50); overflow triggers async `_consolidate_memory()` (summarise into MEMORY.md / HISTORY.md).
- **MCP**: Lazy `_connect_mcp()` once; MCP tools registered in `ToolRegistry` alongside built-in tools; LLM sees one unified tool list.
- **Direct use**: `process_direct(content, session_key="cli:direct", ...)` for CLI/cron so the same loop serves both gateway and CLI without a separate code path.

### 1.3 Takeaways for Omni

1. **One loop, many entry points**: Nanobot uses one AgentLoop for both interactive chat and gateway; we could have one “run loop” that accepts tasks from CLI or from a gateway socket/HTTP.
2. **Session = conversation window**: Per-session history + optional memory consolidation to avoid context pollution in long chats.
3. **Background gateway**: `nanobot gateway` runs the loop and connects channels; users talk to the same agent via Telegram/Discord/etc. We could add `omni run --gateway` (or `omni gateway`) to run a long-lived process that accepts user input (e.g. stdio, or one channel like stdio-only first) and runs OmniLoop per message.
4. **Context isolation**: Nanobot isolates by session (history + memory window + consolidation). We need the same idea for “complex task scenarios” so that one long run doesn’t pollute another.

---

## 2. Current Omni Run Behaviour

- **Single task**: `omni run "intent"` → `execute_task_via_kernel()` → router (fast path) or `OmniLoop.run(task)`; one session per process; no persistent chat session.
- **REPL**: `omni run --repl` → `run_repl_mode()`: prompt loop, MCP-only (no kernel), simple tool-call parse; no Cortex, no router.
- **Graph (Robust Task)**: `omni run --graph "request"` → LangGraph with HITL; checkpointer + thread_id; one graph run per invocation.
- **Kernel lifecycle**: Kernel started in `execute_task_via_kernel()`, then shutdown in `finally`; no long-lived kernel for multiple user messages.

So today:

- No persistent “conversation window” across multiple `omni run` invocations.
- No background daemon that keeps kernel + loop alive and accepts messages from the user (or from a channel).
- Context isolation is “one process = one task” (or one REPL session); there is no explicit “session window” abstraction (e.g. by session_id + history cap + consolidation).

---

## 3. MCP-First Strategy and Maximizing Existing Work

Nanobot uses **MCP** to attach tools; the agent loop calls those tools via one registry. We should **maximize existing MCP and skills work** so MCP is the **universal tool interface** (Cursor, other agents, our gateway), and we can offer Nanobot-like behaviour on top of the same MCP surface.

**What we already have:** (1) **MCP server** (`tools/list`, `tools/call`, stdio + SSE) in `AgentMCPServer`; (2) **Tools = skills** — kernel loads skills, HolographicRegistry / kernel feed `list_tools()`, `call_tool` → `kernel.execute_tool()`; (3) **Skills framework** (SkillManager, Rust Cortex, high-performance load/scan); (4) **Run + MCP** — `omni run --fast` / REPL call MCP over HTTP. So **all skill-backed tools are already exposed via MCP** when the server runs.

**MCP as universal interface:** Any MCP client (Claude, Cursor, custom agent) gets the full tool set. The future **gateway** can be the same process as the MCP server: one kernel, one tool list, plus a message loop (stdio or channel) and session window — no duplicate tool layer; tool execution stays `kernel.execute_tool()` (same as MCP `call_tool`).

**Aligning with Nanobot:** One loop, one registry, multiple entry points. We already have one registry (kernel + HolographicRegistry) and MCP as the protocol. Add gateway mode (message loop + session window) to the same process; keep MCP as the single tool surface and maximize the existing skills framework.

---

## 4. Design Goals for an Evolved `omni run`

1. **ReAct loop + self-evolution window**
   - Keep using OmniLoop (ReAct) as the core.
   - Introduce a **session window**: one logical “conversation” with a bounded history (e.g. last N turns or last M tokens), so complex multi-turn tasks don’t grow unbounded and don’t pollute subsequent runs.
   - Optional **self-evolution**: e.g. after each run (or when window is full), optionally run a “reflection/consolidation” step (like Nanobot’s `_consolidate_memory`) that summarises into project memory or knowledge, so future runs can benefit without re-reading full history.

2. **Context isolation for complex tasks**
   - **Per-session state**: Each session has its own `session_id`, history buffer, and (if we add it) a small “session memory” that can be summarised.
   - **No cross-session pollution**: A new “session” (e.g. new `omni run` invocation in “session mode”, or new conversation in gateway) starts with a clean or capped context; we don’t mix histories.
   - **Explicit boundaries**: “Run one complex task” vs “run a conversation with a window” can be two modes: single-shot (current) vs session mode (new).

3. **Background gateway (Nanobot-style)**
   - **Daemon mode**: e.g. `omni run --gateway` or `omni gateway` that:
     - Starts kernel once.
     - Enters a loop: wait for next “message” (stdio, or later TCP/socket/HTTP).
     - For each message: run OmniLoop (or router fast path) in that session’s context; return response to the user.
   - **User communication**: User (or a channel adapter) sends a message and gets a response; skills are invoked inside the same kernel/loop as today.
   - **Avoid context pollution**: Each gateway “conversation” can be tied to a session_id; we cap history and optionally consolidate so long chats don’t blow up context.

---

## 5. Proposed Design

### 5.1 Session Window (Context Isolation)

- **Session**: Identified by `session_id` (e.g. UUID or `channel:chat_id`-style).
- **History**: Bounded list of (user, assistant) turns; e.g. `retained_turns` (already in PruningConfig) or a new `session_max_turns` / `session_max_tokens`.
- **Where**:
  - **Single-shot** (current): One implicit session per `execute_task_via_kernel()` call; no persistence.
  - **Session mode** (new): Optional `--session <id>` or `--session-dir <path>` so that:
    - We load existing history for that session (if any).
    - We run OmniLoop with that history as initial context.
    - We append the new turn and optionally persist (e.g. to `.data/sessions/<id>.json` or similar under PRJ_DATA).
- **Self-evolution**: When the session window is full (or on explicit “/consolidate” or end of run), run a consolidation step: e.g. call memory/knowledge skill to “save important facts/decisions from this conversation” so that future runs can recall them without re-reading full chat. Prefer writing into **omni-memory** (store_episode + mark_success/mark_failure) so future runs get two_phase_recall and Q-weighted episodes (see [omni-memory.md](../reference/omni-memory.md)).

### 5.2 ReAct Loop Unchanged at Core

- Keep **OmniLoop** + **ResilientReAct** as the execution engine.
- Changes are at the **boundary**:
  - **Input**: Instead of a single `task` string, we can pass “session_id + latest_user_message”; the orchestrator (or a thin wrapper) loads session history and builds the prompt (e.g. last K turns + new message).
  - **Output**: Append assistant response (and tool summary) to session history; optionally persist; optionally trigger consolidation.
- So “ReAct + self-evolution window” = same loop, plus session storage + history cap + optional consolidation.

### 5.3 Gateway (Background) Mode

- **Command**: e.g. `omni run --gateway` or `omni gateway`.
- **Behaviour**:
  1. Start kernel once; optionally start MCP/embedding as today.
  2. Loop:
     - Read one “message” from the chosen transport.
       - **Phase 1**: stdio only (like Nanobot’s CLI chat): one line or one block of input → one response.
       - **Phase 2**: optional TCP/socket or HTTP so that a separate “channel adapter” (e.g. a small Telegram bot) can send messages and receive responses.
     - Resolve session: e.g. by `channel:chat_id` or a single default session for stdio.
     - Load session history (if any).
     - Call `execute_task_via_kernel()`-style path with “session_id + message” (or equivalent).
     - Stream or return the response to the user.
     - Save session state (history + optional consolidation).
  3. No kernel shutdown between messages; one process serves many messages.
- **Skills**: Same as today: router + OmniLoop use kernel and MCP; gateway just feeds user message and returns assistant output.
- **Context isolation**: Per-session history and cap; no mixing across sessions.

### 5.4 Implementation Outline

| Component         | Action                                                                                                                                                                                                                            |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Session store** | Add a small module (e.g. `omni.agent.session` or under `run_entry`): load/save session by `session_id` (file or in-memory for now); structure: `{ "history": [...], "meta": { "created", "updated" } }`.                          |
| **run_entry**     | Add `execute_task_with_session(session_id, user_message, ...)` that: loads history, builds context (last N turns + new message), runs OmniLoop (or router fast path), appends to history, optionally consolidates, saves session. |
| **CLI run**       | Add `--session <id>` (and optionally `--session-dir`) to `omni run`; when set, use `execute_task_with_session` and persist after each turn.                                                                                       |
| **Gateway**       | New command or flag: `omni run --gateway` (stdio loop): read line/blob → `execute_task_with_session("stdio:default", line)` → print response; loop until exit.                                                                    |
| **Consolidation** | Optional: when session history exceeds threshold (or on `/new`-like command), call a small “session summariser” (e.g. memory skill or a dedicated prompt) and write to project memory; then trim or clear session history.        |

### 5.5 File / Config

- Session files: e.g. `PRJ_DATA("sessions", f"{session_id}.json")` (or under `.data/sessions/`).
- Config: e.g. in `settings.yaml`: `run.session_max_turns`, `run.session_consolidate_after_turns`, `run.gateway_enabled` (or leave gateway as a separate command).

---

## 6. Comparison with Nanobot

| Aspect            | Nanobot                                       | Omni (proposed)                                                    |
| ----------------- | --------------------------------------------- | ------------------------------------------------------------------ |
| Loop              | Single AgentLoop, bus-driven                  | Single OmniLoop (or router fast path), session-driven              |
| Entry points      | CLI + gateway (many channels)                 | CLI single-shot, REPL, graph; + gateway (stdio first)              |
| Session           | SessionManager, key = channel:chat_id         | Session store, key = session_id (stdio:default or channel:chat_id) |
| Memory            | MEMORY.md + HISTORY.md, consolidation in loop | Project memory + knowledge; optional consolidation step            |
| Tools             | Built-in + MCP                                | Skills (MCP-backed) + kernel                                       |
| Context isolation | memory_window + consolidation                 | session_max_turns / max_tokens + optional consolidation            |
| Background        | gateway runs loop, blocks on consume_inbound  | gateway runs loop, blocks on stdio (or socket)                     |

---

## 7. Summary

- **Nanobot** gives a clear pattern: one agent loop, multiple entry points (CLI + gateway), session per conversation, memory window + consolidation to avoid context pollution.
- **Omni** already has the right core (OmniLoop, kernel, skills) and **omni-memory** (self-evolving episodes, two-phase recall, Q-learning; see [omni-memory.md](../reference/omni-memory.md)). We need a **session window** (bounded history per session), **optional persistence** for that session, and an **optional consolidation** step that writes into omni-memory so the window maximizes self-evolution.
- **Gateway** is then a thin layer: long-lived process, read message → resolve session → run existing “run with session” path → return response; first phase can be stdio-only so we can “run omni in the background” and talk to it via a pipe or a simple script, then extend to TCP/HTTP and channel adapters (e.g. Telegram) later.

This design keeps `omni run` as the single entry point for “run a task” and extends it with session mode and gateway without duplicating the ReAct loop or the skill system.

---

## 8. Rust-Backed High-Performance Window (1k–10k Skill Invocations)

To support **long-running, complex tasks** with hundreds or thousands of skill invocations (and eventually a Nanobot-style background service where users interact through this window), the session window should be **Rust-native** for throughput and predictable memory use.

### 8.1 Scale and Constraints

- **Target**: 1k–10k skill invocations in a single logical session (e.g. one gateway conversation or one "mission").
- **Problem**: We cannot keep 10k full LLM messages in RAM; we need a **bounded window** that:
  - Retains only **recent turns** in full for context building.
  - Keeps **metadata** (turn index, tool count, checkpoint refs) for older turns.
  - Persists full state to **CheckpointStore** (existing LanceDB) by `thread_id` = `session_id`.
- **Hot path**: Append turn and tool events at O(1); read "last N turns" for context without scanning 10k items.

### 8.2 Existing Rust Building Blocks

| Component                                                           | Role                                                         | Use in window                                                                                                                          |
| ------------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| **omni-events**                                                     | `EventBus` (tokio broadcast)                                 | Agent publishes `agent/step_complete`; window can subscribe to drive incremental append (optional).                                    |
| **omni-vector CheckpointStore**                                     | LanceDB, `thread_id`, `get_history(table, thread_id, limit)` | Full checkpoint content per turn; window holds only refs/summaries.                                                                    |
| **omni-tokenizer ContextPruner**                                    | `window_size`, `max_tool_output`                             | Already used in Python for trimming; Rust window feeds "what to keep" (recent turn IDs).                                               |
| **omni-memory** (see [omni-memory.md](../reference/omni-memory.md)) | EpisodeStore, Q-table, two-phase search                      | Long-term self-evolving recall; consolidation writes session summaries as episodes; context build can inject two_phase_recall results. |

### 8.3 Proposed Rust Crate: `omni-window` (or module in omni-vector)

**Purpose**: High-performance session window that scales to 1k–10k invocations without holding 10k full messages in memory.

**Core types** (conceptual):

```text
TurnSlot (per turn):
  - turn_id: u64 or string
  - checkpoint_id: Option<String>   // ref into CheckpointStore
  - tool_count: u32
  - token_estimate: u32              // for cap decisions
  - role: user | assistant

SessionWindow:
  - session_id: String
  - ring: RingBuffer<TurnSlot>       // fixed capacity (e.g. 2048 slots)
  - total_turns: u64                 // monotonic count
  - total_tool_calls: u64            // for stats / consolidation trigger
```

**Operations**:

| Operation                                              | Description                                                                                                                                        |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `append_turn(session_id, turn_data)`                   | Push one TurnSlot to the ring; if over capacity, drop oldest. Optionally persist "summary" checkpoint for dropped range.                           |
| `append_tool_event(session_id, tool_name, result_len)` | Increment tool count for current turn (or append a lightweight tool-event slot).                                                                   |
| `get_recent_for_context(session_id, last_n)`           | Return slice of TurnSlots (or checkpoint_ids) for the last N turns so Python can load full content from CheckpointStore and pass to ContextPruner. |
| `get_stats(session_id)`                                | Return `{ total_turns, total_tool_calls, window_used }` for UI and consolidation triggers.                                                         |

**Persistence**:

- **Full content**: Already in **CheckpointStore** (Python/agent today writes per-step or per-turn checkpoints with `thread_id` = session_id). No change.
- **Window state**: Optional — either keep window in-process only (gateway holds it for active sessions) or persist the ring to a small file (e.g. `PRJ_DATA("sessions", "{session_id}.window")`) so that restart can restore "recent" refs. For 10k-scale, in-memory ring + checkpoint store is enough; persistence of the ring is for durability across gateway restarts.

**Python binding**:

- `PySessionWindow`: create(session_id, capacity), append_turn(...), get_recent_for_context(...), get_stats(...).
- Agent loop (or gateway) calls `append_turn` after each user/assistant turn; when building context, calls `get_recent_for_context(session_id, retained_turns)` and loads full content from existing CheckpointStore by checkpoint_id (or thread_id + limit).

### 8.4 Flow: Gateway + 10k Invocations

1. **Gateway** starts; kernel stays up; one or more **SessionWindow** instances per active session (e.g. `stdio:default` or `telegram:123`).
2. User sends message → gateway resolves session_id → loads "recent" from **SessionWindow** (Rust) + full content from **CheckpointStore** for those turns → builds context → runs **OmniLoop**.
3. Each step: agent publishes step_complete (optional); **SessionWindow.append_turn** / **append_tool_event** called so the ring stays up to date.
4. After response: gateway saves latest checkpoint for this turn to **CheckpointStore**; **SessionWindow** already has the new slot.
5. When **total_tool_calls** or **total_turns** crosses a threshold (e.g. 500 or 1000), trigger **consolidation** (summarise older turns into one checkpoint or into omni-memory episode); then **SessionWindow** can "collapse" older slots into one summary slot so the ring still only holds recent + summary.

This way the **window** is the high-performance, Rust-backed index over the session; the **heavy content** stays in CheckpointStore and is loaded only for the turns that fit in the LLM context (e.g. last 20–50 turns). 1k–10k skill invocations are supported without 10k messages in RAM.

### 8.5 Implementation Order

1. **Phase 1**: Add **omni-window** crate with `SessionWindow` (in-memory ring buffer of TurnSlot), `append_turn`, `get_recent_for_context`, `get_stats`; Python binding `PySessionWindow`. No persistence of the ring yet.
2. **Phase 2**: Integrate with **run_entry** / OmniLoop: when running in "session mode", create or reuse `PySessionWindow` for the session_id; after each turn append; when building context, use `get_recent_for_context` + CheckpointStore to load the message list.
3. **Phase 3**: **Gateway** (stdio loop) that keeps kernel + session windows alive; user input → session_id → run with session window as above.
4. **Phase 4**: Optional ring persistence and consolidation trigger (summary checkpoint + collapse old slots) for very long sessions (10k+ invocations).

### 8.6 Maximizing Omni-Memory (Self-Evolving Memory) in the Window

The session window and gateway should **maximize use of the existing self-evolving memory** implemented in Rust and exposed via [omni-memory](../reference/omni-memory.md) (MemRL-inspired: episode storage, Q-learning, two-phase search). This gives long-running sessions the same benefits as single-shot runs: **semantic + utility recall** and **self-evolution** from outcomes.

**Reference**: [docs/reference/omni-memory.md](../reference/omni-memory.md) — Episode storage, two-phase recall (semantic → Q-value rerank), `mark_success` / `mark_failure`, multi-hop reasoning, memory decay.

**Integration points**:

| Use case                     | How the window/gateway uses omni-memory                                                                                                                                                                                                                                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Context injection**        | When building context for the next turn, call **two_phase_recall** (or **multi_hop_recall** for complex intents) with the current user message (or session goal). Inject the top-k episodes into the system or early user context so the LLM sees prior successful patterns (e.g. "last time we fixed timeout by increasing to 30s"). |
| **Consolidation → episodes** | When the session window triggers **consolidation** (e.g. after N turns or N tool calls), summarise the completed segment (intent + key actions + outcome) and **store as an episode** via `MemoryService.store_episode(intent, experience, outcome)`. Future sessions then recall these via two-phase search.                         |
| **Outcome feedback**         | After a task or turn completes, call **mark_success(episode_id)** or **mark_failure(episode_id)** for any episode that was used in context (or for the consolidated episode just stored). This updates Q-values so the next two_phase_recall prefers high-utility episodes (MemRL-style self-evolution).                              |
| **Long sessions**            | For 1k–10k invocations, the **recent window** (Rust ring) holds only recent turns; **omni-memory** holds compressed, utility-weighted history. Context = recent turns (from CheckpointStore) + **two_phase_recall(current_intent)** so the model benefits from both recent detail and long-term successful patterns.                  |

**Concrete flow**:

1. **Start of turn (gateway or session mode)**: Optional `two_phase_recall(user_message, k2=5)` (or `multi_hop_recall` if the message implies multiple sub-goals). Append recalled episodes to system/context (e.g. "Relevant past episodes: …").
2. **After response**: If consolidation ran, `store_episode(intent=session_goal, experience=summary, outcome=success|failure)`; then `mark_success` / `mark_failure` for that episode (and optionally for any episode IDs that were injected and led to this outcome).
3. **No duplicate memory layer**: The window (ring + CheckpointStore) remains the **recent** buffer; omni-memory is the **long-term self-evolving** store. Both are used when building context; consolidation is the bridge (summarise window → episode, then optionally collapse window slots).

This way the **Rust window** (scale) and **omni-memory** (self-evolution, two-phase recall, Q-learning) are used together: the window handles high-volume recent state, and omni-memory handles durable, utility-weighted recall so that complex, long-running tasks benefit from the same paper-backed features already implemented.
