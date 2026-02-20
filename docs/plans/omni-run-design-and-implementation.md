# Omni Run: Design, Naming, and Implementation Plan

> Consolidated design and implementation direction for the agent run surface: how to design (and optionally rename) `omni run`, how to leverage our framework’s strengths—especially **omni-memory** and **Rust + Python**—and how to execute the roadmap toward Nanobot/ZeroClaw parity without rebuilding.

**Related**: [omni-run-roadmap-nanobot-zeroclaw.md](./omni-run-roadmap-nanobot-zeroclaw.md) (phases), [omni-run-react-gateway-design.md](./omni-run-react-gateway-design.md) (session window, gateway), [research-memrl-vs-omni-memory.md](../workflows/research-memrl-vs-omni-memory.md) (memory design).

---

## 1. Principles (Recap)

- **Product goal**: Same capabilities as Nanobot and ZeroClaw (one loop, gateway, session, MCP as tool surface, optional channels).
- **How we get there**: Extend and reuse our stack; do not reimplement their designs. Our **skills management** and **MCP integration** are different and stay that way.
- **Memory and performance**: Use our **unique memory design** (omni-memory: two-phase recall, utility feedback, episodes) and our **Rust + Python** split (Rust for high-throughput path, Python for orchestration and MCP/skills). No duplicate memory layer; no rewriting the hot path in pure Python.

---

## 2. Our Framework’s Strengths to Use

### 2.1 Omni-Memory (Unique Design)

Our memory is **not** “another vector store.” It is a MemRL-inspired, self-evolving engine with a clear role in the run/gateway design:

| Strength                             | What we have                                                                                                                                                        | How run/gateway uses it                                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Two-phase recall**                 | Semantic recall → Q-value rerank ([omni-memory.md](../reference/omni-memory.md), [research-memrl-vs-omni-memory.md](../workflows/research-memrl-vs-omni-memory.md)) | At turn start: `two_phase_recall(user_message)` (or multi_hop) and inject top-k episodes into context so the LLM sees high-utility past patterns.                     |
| **Utility feedback**                 | `mark_success` / `mark_failure`, Q-updates                                                                                                                          | After a turn or consolidation: mark outcomes so future recall prefers successful episodes (MemRL-style).                                                              |
| **Episode store**                    | Rust EpisodeStore + persistence                                                                                                                                     | Consolidation: summarise session window segment → `store_episode(intent, experience, outcome)`; long-term state lives in omni-memory, not only in the session buffer. |
| **Stable reasoning, plastic memory** | LLM + skills fixed; only memory/knowledge evolve                                                                                                                    | Same as today: no fine-tuning; session window + omni-memory are the “plastic” part; router + OmniLoop are stable.                                                     |
| **Hippocampus + Knowledge**          | Selective storage, graph + vector, Trinity                                                                                                                          | Session consolidation can write into project memory / knowledge where appropriate; omni-memory holds episodic “I did this and it worked” for two-phase recall.        |

**Implication**: Every design for “session” and “gateway” must **integrate omni-memory** (two-phase recall in context, store_episode + mark_success/failure on consolidation). We do not add a second, unrelated memory system. See [omni-run-react-gateway-design.md](./omni-run-react-gateway-design.md) §8.6.

### 2.2 Rust + Python Split (Performance and Interface)

We have both a **Rust side** (high performance) and a **Python interface** (orchestration, MCP, skills). The run/gateway design should use each where it fits:

| Layer      | Role                                                                                                                                    | Use in run/gateway                                                                                                                                                                           |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Rust**   | omni-vector (CheckpointStore, search), omni-tokenizer (pruning), **omni-memory** (two-phase, Q-table, episodes), future **omni-window** | Session window at 1k–10k steps (ring buffer, append, get_recent); checkpoint refs; two_phase_recall and store_episode via existing bindings; context size control.                           |
| **Python** | Kernel, router, skills, MCP server, run_entry, CLI                                                                                      | Single agent loop (execute_task_via_kernel / run_with_session); gateway message loop; MCP tools = skills; session orchestration (load history, call Rust window + omni-memory, consolidate). |

So: **high-throughput session state and memory recall live in Rust**; **orchestration, tool execution, and transport** stay in Python. No “rewrite the loop in Rust” for Phase 2–3; we add a Rust **session window** and wire it to existing Python run_entry and omni-memory.

#### Why gateway and agent loop are in Python (not Rust like ZeroClaw)

ZeroClaw is a **Rust-native** stack: single binary, trait-based Provider/Channel/Memory/Tool, &lt;10ms startup. We keep **gateway, agent loop, and transport in Python** by design:

| Reason                                 | Explanation                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Skills and MCP are Python-centric**  | Our tool surface is the **skill registry** (metadata-driven, discovery by intent, JIT install) and the **MCP server** that exposes Python callables. Moving the gateway to Rust would require either (1) reimplementing the entire skill/MCP layer in Rust (large rewrite), or (2) a Rust gateway that **proxies every request to a Python worker** (IPC per message, extra latency). Neither fits our "Rust for hot path, Python for orchestration" split. |
| **One process, one loop**              | CLI and gateway share the **same** kernel, router, and tool registry. That loop is Python (OmniLoop, router, skill execution). Putting only the HTTP transport in Rust would require Rust ↔ Python IPC for every message, or the loop stays in Python and Rust is just a thin HTTP front-end (marginal gain).                                                                                                                                              |
| **Leverage existing stack**            | The roadmap says "leverage our stack, don't rebuild." Kernel, Cortex, skills, MCP are in Python. Moving gateway to Rust would mean rebuilding the orchestration boundary; we prefer to **evolve** it and push only **data-plane hot path** (window, memory, vector) to Rust.                                                                                                                                                                                |
| **When Rust gateway could make sense** | If we built a **Rust-first runtime** (Rust agent loop + Rust tools + FFI for ops), a Rust gateway would be natural (like ZeroClaw). That would be a different product; for the current "Python loop + Rust acceleration" shape, gateway stays in Python.                                                                                                                                                                                                    |

So: **gateway, webhook, and agent loop remain in Python**; **Rust** is used for session window (omni-window), vector/memory/search, and tokenizer.

#### Clarification: Python as MCP service only; MCP glues the model and Python

It is not “two backends” in the sense of gateway vs agent. The Python side is **only an MCP server**: it exposes tools (skills). **MCP is the glue** that connects the LLM and Python — the model talks to MCP (tools/list, tools/call), and the MCP server runs the actual tool code in Python (kernel/skills). So:

- **Orchestration side** (gateway, session, agent loop, LLM client): can live in Rust or elsewhere. It runs the loop: user message → LLM → tool calls → **call MCP** (tools/call) → get results → back to LLM → … → reply to user.
- **Python side**: **MCP service only** — no separate “agent service” or “run_turn” API. Python just implements the MCP protocol: list tools, execute tools. The LLM and Python are glued together **through MCP**.

So the split is: one side that does HTTP/session/LLM/loop and calls MCP for tools; one side that is the MCP server (Python, skills). We keep single-process today (gateway + kernel + MCP in one Python process); a future shape can be Rust gateway + Rust-orchestrated loop calling **Python MCP server** for tools only.

#### Pure Rust agent + MCP: think, verify, reflect

**Claim**: We can implement a **pure Rust agent** (gateway, session, loop, LLM client all in Rust), and still **use MCP to tie tool calls together** — because MCP is a **universal interface** for the model ecosystem, not tied to Python.

**Verification**:

- MCP is **protocol- and language-agnostic**. It defines tools/list (discover tools) and tools/call (execute a tool with arguments). The side that runs the “agent” (session, LLM, reasoning, when to call which tool) is the **MCP client**. The side that implements the tools (our skills) is the **MCP server**.
- A **Rust agent** = Rust process that: holds session, receives user message, calls the LLM, gets tool calls from the LLM, and for each tool call sends **tools/call** to an MCP server (over stdio or SSE/HTTP). The MCP server can be our **existing Python MCP server** (kernel + skills). So the Rust agent never reimplements the tools; it just speaks **MCP client** and connects to the Python MCP server. All tools stay in Python; the “glue” is MCP.
- Routing: the Rust agent can get the full tool list via **tools/list** from the MCP server and let the LLM choose which tool to call (and with what arguments). No separate “router” process needed; the LLM + tools/list is enough for tool selection.

**Reflection**: **Correct.** MCP is exactly the universal interface that lets a pure-blood (纯血) Rust agent and our Python skills work together. We do not need two “backends” or a Python “agent service”; we need a **Rust agent (MCP client)** and a **Python MCP server (tools)**. MCP unites (联合) the model and the tools. A pure Rust agent is therefore feasible: implement the loop and MCP client in Rust, keep the tool implementations in Python behind MCP.

**Same as Claude Code / Cursor agent: load MCP servers by config.** Claude Code and Cursor agent, after they run, **load MCP server(s) by port/URL** from config (e.g. one or more SSE endpoints or stdio processes). The omni-rust agent can do the same: at runtime it **loads and connects to MCP server(s)** from config — our Python skills MCP server, or any other MCP server (different port, different tools). So one Rust agent can talk to **different MCP servers** (or multiple at once), just like Cursor/Claude Code; the agent is an MCP client that discovers and calls tools from whichever MCP server(s) are configured.

### 2.3 Skills + MCP (Our Model)

- **Skills**: Metadata-driven index, discovery by intent, JIT install, `@omni("skill.command")` surface.
- **MCP**: Server exposes skills as tools; one registry; kernel executes.
- **Run/gateway**: Same kernel and MCP; no second tool layer. Gateway and CLI both go through the same loop and same tool surface.

### 2.4 Single Loop, Multiple Entry Points

- **One loop**: Kernel + router + OmniLoop (and when we have it: session window + omni-memory in the context path).
- **Entry points**: One-shot task, interactive chat, gateway (stdio then HTTP/channels). All use the same loop; only transport and session resolution differ.

---

## 2.5 Single Loop vs Multiple Loops: Tradeoffs

| Dimension               | Single loop (our target)                                                                                                                                                  | Multiple loops                                                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Behaviour**           | CLI one-shot, interactive, and gateway all see the **same** agent: same tools, same router, same memory. No “which agent did I just talk to?”                             | Different processes or loops can diverge: different tool sets, configs, or behaviour unless carefully kept in sync.                           |
| **State and resources** | One kernel, one skill/MCP registry, one load of Cortex. Many sessions = many `session_id`s through the same loop; no duplicate tool loading per channel.                  | Each loop typically has its own kernel and registry → more RAM and startup cost; sharing memory/session across loops requires extra plumbing. |
| **Code path**           | One execution path (run_entry → OmniLoop or router fast path). Fixes and features apply to CLI and gateway at once.                                                       | Multiple paths to maintain; bugs can be “only in gateway” or “only in REPL.”                                                                  |
| **Session and memory**  | Session = `session_id` in one process; omni-memory and (later) Rust window are shared. Consolidation and two_phase_recall behave the same for every entry point.          | Sessions may live in different processes; sharing omni-memory or window across loops needs a shared store and protocol.                       |
| **Isolation**           | One runaway session can block others in the same process unless we add timeouts/limits and possibly per-session fairness.                                                 | Strong isolation: one process per loop/session; one crash doesn’t kill others.                                                                |
| **Scale-out**           | One process serves many sessions (multiplexed). To scale horizontally, run multiple gateway instances and put a load balancer in front; each instance still has one loop. | “Multiple loops” can mean multiple machines, but then routing, sticky session, and state distribution become necessary.                       |

**When single loop wins**: When the product is “one agent” that users talk to via CLI or gateway (like Nanobot/ZeroClaw). Same capabilities, same memory, same tools everywhere; simpler implementation and operations.

**When multiple loops can help**: When you need hard isolation (e.g. untrusted tenants per process) or deliberately different agents (e.g. “lightweight REPL” vs “full gateway”). For our goal (parity with Nanobot/ZeroClaw, one agent, one tool surface), **single loop is the right default**; we can add timeouts and per-session limits to avoid one session starving others.

---

## 3. Design and Naming: How “omni run” Fits

### 3.1 Option A: Keep `omni run`, Add Siblings (Recommended for Clarity)

Align CLI surface with Nanobot/ZeroClaw **semantics** while keeping our naming consistent:

| Command                                      | Meaning                                               | Implementation                                                                                                                                                    |
| -------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`omni run "task"`**                        | One-shot task (current fixed behaviour)               | `execute_task_via_kernel(task)`; no persistent session.                                                                                                           |
| **`omni run`** (no args) or **`omni agent`** | Interactive chat using the **same** loop              | Either: in-process REPL that calls `execute_task_with_session(session_id, message)` per line, or connect to a running gateway. Same loop as one-shot and gateway. |
| **`omni gateway`**                           | Long-lived daemon; one loop; stdio (then webhook/SSE) | Start kernel once; message loop: read message → resolve session → run loop with session window + omni-memory → return response.                                   |

- **Rename**: No forced rename of `omni run`. We **add** `omni agent` (interactive) and `omni gateway` (daemon) so that “run” = “execute one task,” “agent” = “chat with the agent,” “gateway” = “agent as a service.” This matches user expectations from Nanobot/ZeroClaw.
- **Backward compatibility**: `omni run "task"` and `omni run --graph "..."` stay; `omni run --repl` can be deprecated in favour of `omni agent` once the in-process REPL (or gateway client) exists.

### 3.2 Option B: “omni agent” as Umbrella

- **`omni agent "task"`** = one-shot
- **`omni agent`** = interactive
- **`omni agent --gateway`** or **`omni gateway`** = daemon

Then `omni run` becomes an alias for “run one task” (e.g. `omni run "task"` → `omni agent "task"`) so the **primary** noun is “agent.” This is closer to Nanobot’s `nanobot agent` but requires more CLI churn.

### 3.3 Recommendation

- **Short term**: Option A. Keep `omni run "task"` and `omni run --graph`; add **`omni agent`** for interactive (same loop); add **`omni gateway`** for daemon. Document that “run” = single task, “agent” = chat, “gateway” = service.
- **Later**: If we want one umbrella, we can introduce `omni agent` as the main command and make `omni run` an alias without changing behaviour.

---

## 4. Target Architecture (How It All Fits)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLI: omni run "task" | omni agent | omni gateway                        │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Entry layer (Python)                                                    │
│  - run: execute_task_via_kernel(task)                                    │
│  - agent: REPL or gateway client → execute_task_with_session(id, msg)    │
│  - gateway: message loop → resolve session → execute_task_with_session  │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  One loop (Python: run_entry, kernel, router, OmniLoop)                   │
│  - Input: session_id + user_message (+ optional session history)        │
│  - Context build: recent turns (from Rust window or in-memory buffer)    │
│            + two_phase_recall(user_message) from omni-memory (Rust)     │
│  - Execution: router fast path or OmniLoop → kernel.execute_tool (MCP)    │
│  - Output: append to session; optional consolidate → store_episode       │
│            + mark_success/failure (omni-memory)                          │
└─────────────────────────────────────────────────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Rust:        │ │ Rust:        │ │ Python:      │
│ omni-window  │ │ omni-memory  │ │ Skills+MCP   │
│ (session     │ │ (two-phase,  │ │ (kernel,     │
│  ring buffer)│ │  episodes)   │ │  registry)   │
└──────────────┘ └──────────────┘ └──────────────┘
```

- **Session**: Identified by `session_id`. History = Rust window (when available) or simple in-memory buffer. Consolidation writes into **omni-memory** (store_episode, mark_success/failure) and optionally trims the window.
- **No duplicate memory**: “Recent” = window (Rust or buffer); “long-term, self-evolving” = omni-memory. Both are used in context building; consolidation is the bridge.

---

## 5. Refactor and Implementation Plan

### 5.1 Phase 1: Thin CLI + Extract Graph (Unchanged)

- Extract LangGraph Robust Workflow from `run.py` into e.g. `omni.agent.workflows.robust_task.runner`.
- Shrink `run.py` to parsing + delegation.
- (Optional) In-process REPL: loop that reads a line and calls `execute_task_via_kernel(line)` or a minimal `execute_task_with_session("stdio:default", line)` so interactive use shares the same loop as one-shot.

**Outcome**: Clean separation; CLI is thin; one-loop behaviour is clear.

### 5.2 Phase 2: Gateway + Session (Same Loop, Our Stack)

- **Gateway process**: `omni gateway` (or `omni run --gateway`) — start kernel once, enter message loop (stdio first). For each message: resolve `session_id` (e.g. `stdio:default`) → call **execute_task_with_session(session_id, message)** → return response.
- **execute_task_with_session** (new or extended in run_entry):
  - Load session: from in-memory buffer or (when available) Rust window.
  - **Context**: last N turns + **two_phase_recall(message)** via existing omni-memory Python binding; inject episodes into system/context.
  - Run existing OmniLoop (or router fast path).
  - Append turn to session; if over threshold, **consolidate**: summarise → **store_episode** + **mark_success**/mark_failure (omni-memory), then trim window/buffer.
- **MCP**: Gateway process embeds the same MCP server (kernel already up); one process = gateway + MCP. No second tool layer.
- **CLI**: Add **`omni agent`** for interactive: either in-process REPL using execute_task_with_session, or client to local gateway.

**Outcome**: One loop, gateway mode, session per conversation, omni-memory used for context and consolidation. No new memory system; we use our Rust omni-memory and Python orchestration.

### 5.3 Phase 3: Rust Session Window (Scale 1k–10k)

- Implement **omni-window** (Rust): ring buffer of turn metadata, refs to CheckpointStore; `append_turn`, `get_recent_for_context`, stats. Python binding.
- Integrate with run_entry: in session/gateway mode, create or reuse a session window per `session_id`; after each turn append; when building context use window + CheckpointStore; when threshold exceeded, consolidate into omni-memory (as in Phase 2).
- Gateway and long-running sessions use the Rust window so that 1k–10k tool calls do not blow context; omni-memory still handles long-term, utility-weighted recall.

**Outcome**: Same design as Phase 2, but with a high-performance window in Rust; Python still orchestrates and calls omni-memory.

### 5.4 Phase 4–5: Channels, Onboard, Doctor (Optional)

- Channels: Webhook/SSE, then optional Telegram/Discord/Slack; same loop, session_id from channel.
- Onboard, doctor, service install: as in roadmap.

---

## 6. Summary: What Changes for “omni run”

| Aspect       | Direction                                                                                                                                                                                                                                                                                      |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Naming**   | Keep `omni run` for one-shot and graph; add **`omni agent`** (interactive) and **`omni gateway`** (daemon). Optionally later make `omni agent` the umbrella.                                                                                                                                   |
| **Design**   | One loop (kernel + router + OmniLoop); session = session_id + history (buffer or Rust window); context = recent turns + **two_phase_recall** (omni-memory); consolidation = **store_episode** + **mark_success**/mark_failure.                                                                 |
| **Memory**   | Use **omni-memory** only (no duplicate layer): two-phase recall at turn start, utility feedback at consolidation, episode store for long-term. Align with [research-memrl-vs-omni-memory.md](../workflows/research-memrl-vs-omni-memory.md) and [omni-memory.md](../reference/omni-memory.md). |
| **Rust**     | Session window (omni-window) for scale; omni-memory and CheckpointStore already in Rust; Python calls via existing bindings.                                                                                                                                                                   |
| **Python**   | Orchestration, MCP, skills, run_entry, gateway message loop; no rewrite of the hot path in Python for the window—only integration.                                                                                                                                                             |
| **Refactor** | Phase 1: thin CLI + extract graph. Phase 2: gateway + execute_task_with_session + omni-memory in the loop. Phase 3: Rust window for 1k–10k. Phase 4–5: channels and ops.                                                                                                                       |

This gives a clear path: **design and naming** (run / agent / gateway), **maximise our framework** (omni-memory, Rust + Python, skills + MCP), and **phased implementation** toward Nanobot/ZeroClaw parity without rebuilding their stack.

---

## 7. Implementation Status

| Phase         | Status  | Delivered                                                                                                                                                                                                                                                                                                                    |
| ------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Phase 1**   | Done    | Thin CLI; graph extracted to `robust_task.runner`; `run_robust_task(request, console=...)`; unit tests for runner and \_node_display.                                                                                                                                                                                        |
| **Phase 2**   | Done    | Session store (`omni.agent.session`); `execute_task_with_session(session_id, user_message, kernel=...)` with two_phase_recall and consolidation; `_run_one_turn`; `omni gateway` and `omni agent` (stdio loop, shared kernel); unit tests for session store and gateway loop.                                                |
| **Phase 3**   | Done    | **Rust omni-window** only: ring buffer (`SessionWindow`), `append_turn`, `get_recent_turns`, `get_stats`; PyO3 `PySessionWindow` in `omni_core_rs`. **run_entry** uses `PySessionWindow` exclusively; `session.window_max_turns` (default 2048) from settings. No Python backend; single implementation for maintainability. |
| **Phase 4–5** | Backlog | Channels (webhook/SSE), onboard, doctor, service install.                                                                                                                                                                                                                                                                    |
