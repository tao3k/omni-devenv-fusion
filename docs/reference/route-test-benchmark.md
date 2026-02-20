# Route Test Benchmark

Final benchmark for `omni route test` after optimizations (lazy dimension check, single store init, no redundant warm embed, `--timing` instrumentation).

## Command

```bash
time uv run omni route test "help me to research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl"
```

Optional: add `--timing` for per-phase breakdown.

## Wall-clock (5 runs, cold process each time)

| Run | Total (s) |
| --- | --------- |
| 1   | 2.174     |
| 2   | 2.150     |
| 3   | 2.052     |
| 4   | 2.005     |
| 5   | 1.991     |

- **Typical**: **~2.0–2.1 s** (end-to-end, one embedding round-trip to Ollama).
- **Best observed**: **~1.99 s**.

## Per-phase timing (`--timing`)

| Phase              | Time (s)       | Note                                      |
| ------------------ | -------------- | ----------------------------------------- |
| profile_select     | ~0.001         | No LLM when no `--confidence-profile`.    |
| store_init         | ~0.003         | Single RustVectorStore (cached).          |
| dimension_warm     | 0.000          | Skipped on hot path (lazy on empty only). |
| search             | ~1.15–1.20     | Query embed + Rust hybrid search.         |
| **run_test total** | **~1.15–1.20** | Dominated by first Ollama embed.          |

Bottleneck: **first embedding call to Ollama** (~1.1–1.2 s). Sub-second runs would require the embedding service already warm in the same process (e.g. MCP server).

### Why is the first embed slow if we use HTTP?

Embedding is done over HTTP: our code uses **LiteLLM** → `litellm.embedding(model=..., api_base=http://localhost:11434)` → HTTP POST to Ollama. The **HTTP client and network round-trip are fast** (tens of ms). The ~1 s is spent on the **Ollama server side**:

1. **Model load on first request**  
   Ollama does **not** keep every model in memory. The first time you call the embedding API for a given model (e.g. `qwen3-embedding:0.6b`), Ollama loads that model from disk into RAM/VRAM. That load (read + init) is what takes ~0.5–1.5 s. The HTTP request stays open until Ollama finishes and returns the vector.

2. **Later requests**  
   Once the model is loaded, the same process’s next embedding requests are much faster (e.g. ~50–200 ms per call), because it’s just inference over an already-loaded model.

So the time is **not** in our HTTP client; it’s in **Ollama’s first-time model load**. To get “秒出” on the first `omni route test` in a new shell, you’d need the model already loaded (e.g. run one embed right after `ollama serve`, or keep an MCP that already did an embed).

## Environment

- **Embedding**: LiteLLM → Ollama `qwen3-embedding:0.6b` at `localhost:11434`.
- **Vector store**: RustVectorStore at `.cache/omni-vector` (keyword_index=True).
- **Profile**: `balanced` (active-profile, no LLM).

## Reproduce

```bash
# Single run with breakdown
time uv run omni route test "help me to research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl" --timing

# 5-run sample
for i in 1 2 3 4 5; do echo "=== Run $i ==="; time uv run omni route test "help me to research https://github.com/nickel-lang/tf-ncl/blob/main/examples/aws/modules/aws-simple-ec2.ncl"; done
```
