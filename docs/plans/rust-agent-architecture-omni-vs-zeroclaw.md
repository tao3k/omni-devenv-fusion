# Rust Agent Architecture: Omni vs ZeroClaw

> **Goal**: ZeroClaw-like target (fast Rust agent, gateway, daemon) without reimplementing tools or LLM providers. We design an architecture that is **different from ZeroClaw** but **sufficiently advantageous** by building on our current stack.

---

## 1. Target and Constraints

| Aspect             | ZeroClaw (reference)                           | Our target                                                                                                                                                                                                                          |
| ------------------ | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Why Rust agent** | Single binary, &lt;10ms startup, full control. | Same: fast agent loop, gateway, daemon; Rust is the main runtime for the “agent” experience.                                                                                                                                        |
| **MCP’s role**     | Not central; ZeroClaw has its own Tool trait.  | **Dual role**: (1) Our Rust agent calls **omni skills** via MCP. (2) **Codex / Gemini CLI** (and other MCP clients) use the **same** MCP server to call omni. So MCP = single tool surface for both our agent and external clients. |
| **Don’t repeat**   | N/A (they implement everything in Rust).       | We **must not** reimplement: skills (100+ tools in Python), LLM providers (LiteLLM’s 100+ backends). We reuse Python + LiteLLM and only add a thin bridge if needed.                                                                |

So: **ZeroClaw is the experience we want** (Rust-native agent, gateway, performance), but we **architect differently** so we don’t rebuild tools or LLM; we **reuse** MCP and (optionally) a Python LLM bridge.

---

## 2. ZeroClaw vs Omni: Where Each Puts Logic

| Layer               | ZeroClaw                                                   | Omni (proposed)                                                                                                                                                                                  |
| ------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Agent loop**      | Rust (trait-based loop).                                   | **Rust**: receive message → recall → build prompt → LLM → tool_calls → tools → consolidate. Same shape, Rust-owned.                                                                              |
| **Session**         | Rust (in-process state).                                   | **Rust**: omni-window (ring buffer, checkpoint refs). We already plan/use Rust for this.                                                                                                         |
| **Memory / recall** | Rust (SQLite + FTS + vector).                              | **Rust**: **omni-memory** (two-phase recall, Q-value rerank, episodes). We already have this; it’s a **differentiator** (not just vector search).                                                |
| **Gateway**         | Rust (HTTP, webhook, daemon).                              | **Rust**: same (axum/actix, POST /message, stdio).                                                                                                                                               |
| **Tools**           | Rust (Tool trait, implementations in Rust or adapters).    | **Registry + executor in Rust**; runnable is still Python/bash/other. Rust **executor** (not Python subprocess) spawns the tool process. See [rust-skill-executor.md](./rust-skill-executor.md). |
| **LLM**             | Rust (Provider trait; likely HTTP to one or few backends). | **Not in Rust**: use **LiteLLM** via (a) HTTP to LiteLLM proxy, or (b) **Python bridge** (Rust calls Python, Python calls LiteLLM). One place for 100+ providers.                                |

So: **Rust owns loop, session, memory, gateway, MCP client**. Rust **does not** own tool implementations or LLM provider logic; it **consumes** MCP (tools) and a single LLM endpoint (or bridge).

---

## 3. Why This Is Different and Advantageous

### 3.1 Same MCP surface for our agent and for Codex/Gemini

- **One** MCP server (`omni mcp`) exposes omni skills.
- **Our Rust agent** connects to it as MCP client (tools/list, tools/call).
- **Codex / Gemini CLI** (and any MCP client) connect to the **same** server.
- So we don’t maintain two “tool surfaces”; we don’t reimplement skills in Rust. We get interoperability (Codex/Gemini can use omni) and our Rust agent uses the same tools.

### 3.2 Omni-memory in Rust (differentiator)

- ZeroClaw: SQLite + FTS + vector (hybrid search).
- We already have **omni-memory**: two-phase recall (semantic → Q-value rerank), episodes, utility feedback, consolidation. All in Rust.
- The Rust agent can call **native Rust omni-memory** for context at turn start and for store_episode after turns. So we’re not “catching up” on memory; we’re **ahead** on design and can lean on it in the Rust path.

### 3.3 No wheel reinvention

- **Tools**: Python skills + MCP. No Rust reimplementation.
- **LLM**: LiteLLM (or bridge). No 100+ provider logic in Rust.
- **Rust** focuses on: loop, session, memory, gateway, MCP client. That’s where we get ZeroClaw-like performance and control without rebuilding the ecosystem.

### 3.4 Optional Python bridge for LLM

- If we want “one place for LLM config” (same as Python gateway), Rust calls a **Python bridge** (HTTP or PyO3) that runs LiteLLM. No OpenAI-compatible implementation in Rust.
- If we accept “one HTTP endpoint” (e.g. LiteLLM proxy), Rust is just an HTTP client to that URL. Either way, we don’t reimplement providers.

---

## 4. Component Diagram

```
                    ┌─────────────────────────────────────────────────┐
                    │              Rust agent (omni-agent)         │
                    │  loop │ session (omni-window) │ memory (omni-memory) │
                    │  gateway (HTTP / stdio) │ MCP client               │
                    └──────────────┬──────────────────────┬─────────────┘
                                   │                      │
              LLM (messages →      │                      │  tools/list
              content + tool_calls)│                      │  tools/call
                                   ▼                      ▼
                    ┌──────────────────────┐    ┌──────────────────────┐
                    │  LLM endpoint        │    │  MCP server (omni mcp)│
                    │  (LiteLLM proxy or   │    │  Python: skills       │
                    │   Python bridge)     │    │  same surface for     │
                    └──────────────────────┘    │  Codex / Gemini CLI   │
                                                └──────────────────────┘
```

- **Rust** = orchestration + hot path (session, memory, gateway, MCP client).
- **MCP server** = single tool surface for our agent and for Codex/Gemini.
- **LLM** = single endpoint (LiteLLM or bridge); no provider logic in Rust.

---

## 5. Performance: Do We Match or Beat Pure Rust?

We want Python's flexibility (skills, LiteLLM) **without** paying a large performance tax. The answer: **we are not meaningfully slower than a pure-Rust agent**; on the hot path we are on par or better.

### 5.1 Where time is spent (per turn)

| Component                                                 | Typical latency                       | Who owns it in our design        | Pure Rust (ZeroClaw) |
| --------------------------------------------------------- | ------------------------------------- | -------------------------------- | -------------------- |
| **LLM round-trip**                                        | **200–3000+ ms** (network + model)    | Rust → HTTP/bridge → LiteLLM/API | Rust → HTTP → API    |
| **Tool execution** (business logic)                       | 1–500+ ms per tool (skill-dependent)  | Python (MCP server)              | Rust (or adapter)    |
| **MCP boundary** (Rust ↔ Python per tools/call)          | **&lt;1–5 ms** (localhost TCP + JSON) | Our extra hop                    | N/A (in-process)     |
| **Loop + session + memory** (recall, prompt build, parse) | **1–20 ms**                           | **Rust**                         | Rust                 |

So: **LLM dominates** (often 80–95% of turn time). Tool logic is the same whether run in Python or Rust; the only **extra** we add is the MCP hop per tool call.

### 5.2 Cost of the Python boundary (MCP)

- One **tools/list** per turn: one round-trip to MCP (local). Typically **&lt;5 ms**.
- **N** tool calls → **N** round-trips. Each is: Rust serializes request → localhost TCP → Python deserialize → run skill → serialize → TCP → Rust deserialize. On the same machine this is **~0.5–3 ms** per call for simple tools; more if the skill does heavy work (then the skill dominates, not the hop).
- Example: 5 tool calls, 2 ms per hop → **10 ms** extra. If the turn has 1 LLM call at 800 ms and 5 tools at 50 ms each (250 ms), total ~1060 ms; we add ~10 ms → **&lt;1%** overhead. So the **flexibility of Python (skills) costs only a small, bounded overhead**.

### 5.3 Where we are faster or equal

- **Loop, session, memory**: All in **Rust**. No Python in the hot path for recall, window append, or prompt assembly. So we are **at least as fast** as pure Rust here; we can be **faster** than an all-Python agent because we never touch the interpreter for these steps.
- **LLM**: Both we and pure Rust do HTTP to an API (or proxy). Same network and model latency. Using a **Python bridge** (Rust → Python → LiteLLM) adds one local hop (e.g. 1–2 ms) vs Rust → LiteLLM proxy directly; if we use **Rust → LiteLLM proxy over HTTP**, we have **zero** extra cost vs pure Rust.
- **Startup**: Rust binary starts in **milliseconds**. If the MCP server and (optional) bridge are long-lived, our process startup is **ZeroClaw-like**. No Python in the critical path for "agent start".

### 5.4 Summary table

| Metric                       | Pure Rust (ZeroClaw-style) | Our design (Rust + MCP + bridge/proxy)                                   |
| ---------------------------- | -------------------------- | ------------------------------------------------------------------------ |
| Turn latency (dominant: LLM) | Same (network-bound)       | **Same** (or +1–2 ms if bridge in process)                               |
| Turn latency (tool calls)    | In-process                 | **+&lt;1–5 ms per tool call** (MCP hop); usually **&lt;5%** of turn time |
| Loop/session/memory          | Rust                       | **Rust** → same or better (omni-memory)                                  |
| Startup                      | &lt;10 ms                  | **Same** for Rust binary; MCP/bridge can be pre-started                  |
| Memory footprint             | One process                | Rust process + Python MCP (separate); acceptable for daemon              |

So: **we do not fall below "pure Rust" in any meaningful way**. The only penalty is the **MCP hop per tool call** (low single-digit ms per call), which keeps Python's flexibility without "losing a lot of performance." The hot path (loop, session, recall) stays in Rust; the dominant cost (LLM) is unchanged; tool overhead is small and predictable.

---

## 6. Summary: “Rust orchestration, externalized tools and LLM”

| Principle                        | Meaning                                                                                                                                                                           |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ZeroClaw-like experience**     | Fast Rust agent, gateway, daemon; one binary possible for the orchestration layer.                                                                                                |
| **MCP for interop and tools**    | Same MCP server serves our Rust agent and Codex/Gemini CLI; we don’t reimplement tools.                                                                                           |
| **Rust owns the loop and state** | Loop, session (omni-window), memory (omni-memory), gateway, MCP client — all in Rust.                                                                                             |
| **Don’t reimplement**            | Tools = Python (MCP). LLM = LiteLLM (proxy or Python bridge). We reuse and only integrate.                                                                                        |
| **Advantage over ZeroClaw**      | Same product shape (agent, gateway, session, tools) with **omni-memory** and **one MCP surface** for omni and for external clients; no duplicate tool or provider implementation. |

This gives us an architecture that is **different from ZeroClaw** (we delegate tools and LLM instead of implementing traits for them) but **enough of an advantage** (performance where it matters, one MCP surface, richer memory, no wheel reinvention).
