# Embedding: Replace Custom Service with LiteLLM + Local Backends

## Context

The current **custom embedding service** (SentenceTransformer + HTTP server in `omni.foundation.services.embedding` and `embedding_server.py`) has led to:

- High memory spike (e.g. 100MB → 10GB+) when loading the model and running the first batch in the embedding process.
- Extra complexity and failure modes we maintain ourselves.

**Goal:** Prefer a stable, community-maintained way to run local embedding models and/or use remote APIs, and simplify our codebase.

---

## LiteLLM Support for Embeddings

**LiteLLM** provides a unified interface to 100+ LLM/embedding providers. It supports **local** embedding via:

| Backend               | Description                                                                                 | LiteLLM usage                                                                                         |
| --------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **Ollama**            | Local inference (embedding models included). Runs in its own process; we only call its API. | `litellm.embedding(model="ollama/nomic-embed-text", input=texts, api_base="http://localhost:11434")`  |
| **Xinference**        | Open-source inference server (LLMs + embeddings). OpenAI-compatible `/v1` API.              | `litellm.embedding(model="xinference/bge-base-en", input=texts, api_base="http://127.0.0.1:9997/v1")` |
| **OpenAI-compatible** | Any server that exposes `/v1/embeddings` (e.g. our current server, or external API).        | `litellm.embedding(model="openai/...", input=texts, api_base="http://...")`                           |

- **Ollama** and **Xinference** run the model in a **separate process**; our app (e.g. MCP) stays small and only uses the SDK or HTTP client.
- **LiteLLM** does not run the model itself; it is a **proxy/SDK** that routes requests to these backends.

---

## Local Embedding with Ollama

1. Install and run Ollama: [ollama.com](https://ollama.com).
2. **Project model storage.** When the MCP command (or CLI entry) starts Ollama for you, it sets `OLLAMA_MODELS` to the project models directory **`.data/models`** (i.e. `PRJ_DATA("models")`), so all pulled models are stored there. If you start Ollama yourself, set `OLLAMA_MODELS` to that path to keep models in one place:
   ```bash
   export OLLAMA_MODELS="${PRJ_DATA_HOME:-.data}/models"
   mkdir -p "$OLLAMA_MODELS"
   ollama pull qwen3-embedding:0.6b
   ```
3. Pull an embedding model, e.g. Qwen 0.6 or nomic:
   ```bash
   ollama pull qwen3-embedding:0.6b
   # or: ollama pull nomic-embed-text
   ```
4. Ollama exposes `POST http://localhost:11434/api/embeddings` (and LiteLLM can route to it).
5. In our app, use LiteLLM Python SDK:
   ```python
   from litellm import embedding
   response = embedding(
       model="ollama/nomic-embed-text",
       input=["text to embed"],
       api_base="http://localhost:11434",
   )
   ```
6. No need to run our custom embedding server or load SentenceTransformer in our process; Ollama handles loading and memory.

---

## Local Embedding with Xinference

1. Install and start Xinference: [inference.readthedocs.io](https://inference.readthedocs.io/en/latest/index.html).
2. Launch an embedding model (e.g. `bge-base-en`, `gte-base`, or others from the [builtin embedding list](https://inference.readthedocs.io/en/latest/models/builtin/embedding/index.html)).
3. Xinference exposes an OpenAI-compatible API at e.g. `http://127.0.0.1:9997/v1`.
4. In our app:
   ```python
   from litellm import embedding
   response = embedding(
       model="xinference/bge-base-en",
       input=["text to embed"],
       api_base="http://127.0.0.1:9997/v1",
   )
   ```

---

## Options for Our Codebase

1. **Remove our custom embedding service** (no more in-process SentenceTransformer, no custom HTTP server for embedding).
2. **Use LiteLLM as the single embedding client** in our code:
   - **Local:** Configure `embedding.provider` (or similar) to `ollama` or `xinference` with the right `api_base` and model name; call `litellm.embedding(...)`.
   - **Remote:** Use LiteLLM with OpenAI / Azure / Voyage / etc. as today with `api_base` + keys.
3. **Keep a thin wrapper** that:
   - Reads config (local vs remote, model name, api_base).
   - Calls `litellm.embedding(...)` or `litellm.aembedding(...)`.
   - Returns the same shape our callers expect (list of vectors, dimension).

This avoids maintaining model loading, device/dtype logic, and HTTP server ourselves; we rely on Ollama or Xinference for local runs and on LiteLLM for a stable, well-supported client.

---

## Implementation (Current)

- **Config:** In `packages/conf/settings.yaml`, set `embedding.provider` to `ollama`, `xinference`, or `litellm`. Optional overrides: `embedding.litellm_model`, `embedding.litellm_api_base`. `embedding.dimension` must match the chosen model (e.g. 768 for nomic-embed-text).
- **Defaults when provider is ollama/xinference:** `litellm_model` and `litellm_api_base` default to `ollama/nomic-embed-text` + `http://localhost:11434`, or `xinference/bge-base-en` + `http://127.0.0.1:9997/v1`.
- **Code:** `omni.foundation.services.embedding` uses only LiteLLM (plus HTTP client and fallback). No in-process model loading; local models are used by running Ollama or Xinference and setting `provider=ollama` or `provider=xinference`.
- **Qwen 0.6 via Ollama:** `ollama pull qwen3-embedding:0.6b`, then `provider: "ollama"`, `litellm_model: "ollama/qwen3-embedding:0.6b"`, `dimension: 1024`. No Xinference needed.
- **MCP and Ollama lifecycle:** When you run `omni mcp` (stdio or SSE) with `embedding.provider: "ollama"`, the CLI will:
  - Detect if the `ollama` binary is in PATH.
  - If the configured API host:port (e.g. `localhost:11434`) is not listening, start `ollama serve` in a subprocess, wait for it to be ready, then run `ollama pull <model>` so the embedding model is available.
  - On MCP shutdown (Ctrl+C or normal exit), the subprocess we started is terminated gracefully. If Ollama was already running before MCP started, we do not stop it.

---

## References

- LiteLLM embeddings doc: [docs.litellm.ai/docs/embedding/supported_embedding](https://docs.litellm.ai/docs/embedding/supported_embedding)
- LiteLLM Ollama: [docs.litellm.ai/docs/providers/ollama](https://docs.litellm.ai/docs/providers/ollama)
- LiteLLM Xinference: [docs.litellm.ai/docs/providers/xinference](https://docs.litellm.ai/docs/providers/xinference)
- Ollama embedding model example: [ollama.com/library/nomic-embed-text](https://ollama.com/library/nomic-embed-text) (`ollama pull nomic-embed-text`, then `POST /api/embeddings`)
