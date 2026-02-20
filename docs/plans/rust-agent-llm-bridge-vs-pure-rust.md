# Rust Agent: LLM via Python Bridge vs Pure Rust

We have two clear choices for where the LLM call lives in the Rust agent path.

---

## Option 1: Pure Rust — drop LiteLLM Python, use Rust ecosystem

**Idea**: No Python for inference. The Rust agent uses Rust crates or direct HTTP to talk to providers (OpenAI, Anthropic, Ollama, etc.). We implement or depend on “OpenAI-compatible” or per-provider clients in Rust.

| Pros                                                    | Cons                                                                                        |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Single binary possible; no Python runtime for agent.    | Rust LLM ecosystem is smaller: we maintain or glue several providers, no 100+ like LiteLLM. |
| Maximum control over hot path; no process/FFI overhead. | Duplicate provider logic (routing, fallbacks, keys) already in LiteLLM.                     |
| Good for constrained or non-Python deployments.         | New providers = Rust work; we lag behind LiteLLM.                                           |

**When it’s worth it**: We explicitly optimize for “no Python, single binary, minimal deps” and accept a smaller, curated provider set (e.g. OpenAI + Anthropic + Ollama) and maintaining them in Rust.

---

## Option 2: Rust uses Python bridge — LLM stays in Python (LiteLLM)

**Idea**: Rust agent does **not** implement OpenAI-compatible HTTP (or any provider) itself. All LLM calls go through a **Python bridge** that uses LiteLLM. Rust only knows: “call bridge with (messages, model, tools) → get completion”.

- **Bridge shape**: Either (a) a tiny Python HTTP service (e.g. FastAPI) that Rust calls with a minimal JSON contract, and the service calls `litellm.completion(...)`, or (b) Rust embeds Python (PyO3) and calls a Python function that runs LiteLLM in-process.
- **Result**: One place for all provider logic, routing, keys, fallbacks: Python + LiteLLM. Rust stays “agent loop + MCP client + session (+ future gateway)”.

| Pros                                                                     | Cons                                                                         |
| ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| One source of truth: Python + LiteLLM for 100+ providers, routing, cost. | Extra hop (Rust → bridge) or Python runtime in process.                      |
| No reimplementation of API shapes or providers in Rust.                  | Latency: one more process or FFI boundary (usually small vs LLM round-trip). |
| Same config and keys as existing Python stack (gateway, MCP).            | Not a single static binary; depends on Python/bridge.                        |
| New providers = LiteLLM update, no Rust change.                          |                                                                              |

**When it’s worth it**: We want to keep “one stack” for LLM (LiteLLM) and treat Rust as the fast orchestration layer (loop, MCP, session, gateway) that delegates inference to Python.

---

## Recommendation

**Prefer Option 2 (Python bridge)** for the current product:

1. **Latency**: The dominant cost is the LLM API round-trip (network). Saving a few ms by having the client in Rust is marginal; the bridge (HTTP or PyO3) is cheap compared to that.
2. **Single place for LLM**: All provider logic, keys, routing, and fallbacks stay in Python + LiteLLM. No duplicate implementation or drift between Rust and Python.
3. **Consistency**: Today’s Python gateway and MCP already use LiteLLM. Rust agent calling the same bridge keeps one config surface and one mental model.
4. **Rust’s role**: Agent loop, MCP client, session store, future gateway—things where Rust’s control and performance matter. Provider SDKs and 100+ backends are better left to LiteLLM.

**Choose Option 1 (pure Rust)** only if we explicitly target “zero Python, single binary” or “minimal footprint” and accept a smaller, Rust-maintained provider set and no LiteLLM feature parity.

---

## Concretely: what changes if we adopt the bridge

- **Rust agent**: Remove (or make optional) the current “OpenAI-compatible HTTP” `LlmClient` that posts to an arbitrary URL. Replace with a **bridge client** that:
  - Either **HTTP**: `POST bridge_url/chat` with `{ "messages", "model", "tools" }` → bridge (Python + LiteLLM) returns `{ "content", "tool_calls" }`.
  - Or **PyO3**: Rust calls a Python function `omni.bridge.chat(messages, model, tools)` that runs LiteLLM and returns the same shape.
- **Python side**: Add a small **bridge** module or service that exposes `chat(messages, model, tools)` and uses existing LiteLLM (same as gateway/MCP). No new provider logic.
- **Config**: `AgentConfig` has `llm: bridge` with `bridge_url` (or “use embedded Python bridge”) instead of `inference_url` + raw API key. Keys stay in LiteLLM’s env.

So: we **do** use a bridge; we **don’t** implement OpenAI compatibility in Rust. Rust “fully uses the Python bridge” for LLM; only the bridge talks to LiteLLM.
