# LiteLLM and the Rust Agent

For the choice "pure Rust LLM vs Rust using a Python bridge (LiteLLM)", see [rust-agent-llm-bridge-vs-pure-rust.md](../plans/rust-agent-llm-bridge-vs-pure-rust.md). Below describes the **current** design (OpenAI-compatible client pointing at LiteLLM).

The omni-agent uses a **single OpenAI-compatible HTTP endpoint** for chat completions. That design **reuses LiteLLM by default** without an extra “bridge” process or SDK.

## Why the current design needs no separate bridge

- **Rust agent** = HTTP client: `POST inference_url` with `model`, `messages`, optional `tools` (OpenAI request shape).
- **LiteLLM** = proxy/server: exposes the same OpenAI-compatible API and routes by `model` to OpenAI, Anthropic, Ollama, Azure, etc.

So “bridge” is just: **point `inference_url` at LiteLLM**. The agent does not need a separate component that “calls LiteLLM”; it only needs the proxy’s URL.

## How to use LiteLLM

1. Run LiteLLM (e.g. `litellm --port 4000`). Set provider keys in LiteLLM’s environment (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
2. Configure the Rust agent to use that endpoint:
   - **Explicit**: `AgentConfig { inference_url: "http://127.0.0.1:4000/v1/chat/completions", model: "gpt-4o-mini", .. }`.
   - **Helper**: `AgentConfig::litellm("gpt-4o-mini")` (uses `LITELLM_PROXY_URL` env, default `http://127.0.0.1:4000/v1/chat/completions`; model from `OMNI_AGENT_MODEL` or the argument).
3. Use any model string LiteLLM supports: `gpt-4o`, `claude-3-5-sonnet`, `ollama/llama2`, etc.

No Rust–Python bridge, no in-process LiteLLM: the agent talks to LiteLLM over HTTP like any other OpenAI-compatible server.

## Relation to Python stack

The Python side already uses LiteLLM for inference (`omni.foundation.services.llm`) and embeddings (Ollama/Xinference via LiteLLM). The Rust agent reuses the **same idea** (one API shape, many providers) by targeting a single endpoint; that endpoint can be LiteLLM so both stacks share the same routing and provider set.
