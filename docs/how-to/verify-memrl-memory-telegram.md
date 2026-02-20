# Verify MemRL Memory (Self-Evolution) via REPL or Telegram

> **Purpose**: Validate that omni-agent's memory (MemRL-inspired: two-phase recall, Q-learning, store_episode) works. The "self-evolution" effect: high-utility episodes surface in recall; low-utility ones are deprioritized.

---

## Prerequisites

- LLM configured (`OPENAI_API_KEY` or `LITELLM_PROXY_URL`)
- MCP optional (`.mcp.json` if using tools)

---

## Recommended: REPL (Two Commands)

Memory persists to disk (`memory/`). Run two one-shot commands with the same `--session-id`:

```bash
# Turn 1: Store episode
cargo run -p omni-agent -- repl --query "Remember: my favorite number is 42." --session-id mem-test

# Turn 2: Recall (new process loads same memory store)
cargo run -p omni-agent -- repl --query "What's my favorite number?" --session-id mem-test
```

**Expected**: Turn 2 reply includes "42" (recalled from Turn 1).

**Embedding**: When the embedding HTTP server is running (e.g. `omni mcp` with embedding on port 18501), omni-agent uses it for semantic encoding. Otherwise it falls back to hash-based encoder (identical wording required). Set `OMNI_EMBEDDING_URL` to override the default `http://127.0.0.1:18501`.

---

## Alternative: Telegram

- `omni channel --rust` (or `cargo run -p omni-agent -- channel`) running with bot token configured
- Same Telegram chat = same session (`telegram:{chat_id}`)
- For local testing, use `--mode polling`; for production with a public URL, use `--mode webhook` (see [Run the Rust Agent §10](../how-to/run-rust-agent.md#10-telegram-channel))

### Automated Telegram validation suite

Use the Pythonized suite for repeatable black-box validation:

```bash
# Quick command-path checks
python3 scripts/channel/test_omni_agent_memory_suite.py --suite quick --max-wait 90 --max-idle-secs 40 --username tao3k

# Full live suite: includes memory self-evolution DAG validation by default
python3 scripts/channel/test_omni_agent_memory_suite.py --suite full --max-wait 90 --max-idle-secs 40 --username tao3k

# Full suite but skip DAG stage (command probes + Rust regressions only)
python3 scripts/channel/test_omni_agent_memory_suite.py --suite full --skip-evolution
```

### CI gate runner (mock Telegram + local webhook runtime)

Use the orchestrator for repeatable CI/local gate execution:

```bash
# PR-level quick gate (command-path + Rust regressions, no DAG)
python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile quick

# Nightly gate (full suite + DAG quality + session matrix + benchmark)
python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile nightly

# Debug matrix/benchmark path without DAG stage
python3 scripts/channel/test_omni_agent_memory_ci_gate.py --profile nightly --skip-evolution --skip-benchmark
```

The gate runner automatically starts/stops Valkey, a local Telegram API mock server, and the local webhook runtime.
By default it uses an auto-generated Valkey key prefix per run (`OMNI_AGENT_SESSION_VALKEY_PREFIX`)
to isolate CI traffic from any other local runtime sharing the same `VALKEY_URL`.
By default it also writes run-scoped log/report files (profile + run suffix), so concurrent quick/nightly runs do not overwrite each other.
If Valkey is already running before the gate starts, the gate will not shut it down in cleanup.
Use `--valkey-prefix <prefix>` to override the default isolation prefix when needed.
Use explicit `--runtime-log-file`, `--mock-log-file`, and `--*-report-*` options only when you intentionally need fixed output paths.

Benchmark note: the nightly benchmark issues `/reset` and `/session feedback ...` control commands.
The benchmark `--user-id` must map to an admin-capable Telegram identity in runtime policy, otherwise the run fails with `admin_required`.

---

## Scenario 1: Memory Recall (Multi-Turn)

**Validates**: Episodes are stored; two_phase_recall injects them into context.

| Turn | You send                              | Expected                               |
| ---- | ------------------------------------- | -------------------------------------- |
| 1    | "Remember: my favorite number is 42." | Agent acknowledges                     |
| 2    | "What's my favorite number?"          | Agent says "42" (recalled from Turn 1) |

**Why it works**: Turn 1 is stored as episode (intent + experience + outcome=completed, Q=1.0). Turn 2 triggers `two_phase_recall("What's my favorite number?")` → semantic match finds Turn 1 → injected as system context → LLM sees it.

---

## Scenario 2: Self-Purification (Q-Value Filtering)

**Validates**: Two-phase recall prefers high-Q episodes. When similar intents have different outcomes, successful ones rank higher.

**Mechanism**:

- Each turn: `store_episode` + `update_q(reward)`. Success → Q↑; response containing "error"/"failed" → Q↓.
- Recall: Phase 1 semantic → Phase 2 rerank by `(1-λ)×similarity + λ×Q`. High-Q episodes surface.

**How to observe** (requires multiple similar intents with mixed outcomes):

1. **Turn 1**: "How do I fix a connection timeout?" → Agent gives a good answer → stored, Q=1.0
2. **Turn 2**: Ask something that leads to an error response (e.g. trigger a tool failure) → stored, Q=0.0
3. **Turn 3**: "How do I fix a connection timeout?" again → Recall should prefer Turn 1 (high Q) over Turn 2 (low Q); response should reflect the successful pattern

**Note**: Outcome is inferred from assistant message (contains "error"/"failed"/"exception" → failure). Tool failures often produce such text, so they get Q=0.0.

---

## Scenario 3: Consolidation (Long Session)

**Validates**: When session window is full, oldest turns are consolidated into one episode.

**Requirement**: Agent must be built with `window_max_turns` and `consolidation_threshold_turns` set. Currently the default config has these as `None`, so consolidation does not run. To enable:

- Modify `build_agent` in `main.rs` (or add config): `window_max_turns: Some(20)`, `consolidation_threshold_turns: Some(10)`, `consolidation_take_turns: 5`
- Then: 10+ turns in same session → consolidation drains oldest 5 → summarises → stores as one episode with reward

---

## Quick Test (Scenario 1)

**REPL** (with embedding server for semantic recall, or identical wording for hash fallback):

```bash
# With embedding server (omni mcp or embedding on 18501): semantic recall works
cargo run -p omni-agent -- repl --query "Remember: my favorite number is 42." --session-id mem-test
cargo run -p omni-agent -- repl --query "What's my favorite number?" --session-id mem-test

# Without embedding server: use identical wording
cargo run -p omni-agent -- repl --query "What is my favorite number? (Answer: 42)" --session-id mem-test
cargo run -p omni-agent -- repl --query "What is my favorite number? (Answer: 42)" --session-id mem-test
```

**Expected**: Second reply includes "42".

**Telegram**: Start `omni channel --rust`, send the same two messages in sequence.

---

## Troubleshooting

| Issue                  | Cause                               | Fix                                                                                                |
| ---------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------------- |
| Agent doesn't recall   | Memory disabled or store path wrong | Check `config.memory` in agent; default path `PRJ_CACHE_HOME/omni-memory/` (see dirs.py / omni-io) |
| No episodes stored     | store_episode fails                 | Check disk space; ensure embedding_dim matches                                                     |
| Recall returns nothing | No similar past episodes            | Run Scenario 1 first to create episodes                                                            |

---

## References

- [Omni-Memory](../reference/omni-memory.md) — implementation
- [MemRL vs Omni-Memory](../workflows/research-memrl-vs-omni-memory.md) — research comparison
- [Unified Execution Engine](../reference/unified-execution-engine-design.md) — MemRL integration
