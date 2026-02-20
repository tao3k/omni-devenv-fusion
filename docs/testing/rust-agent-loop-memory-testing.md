# Rust Agent: Loop, ReAct, and Memory Testing

> How the omni-agent loop aligns with Nanobot/ZeroClaw and how we test loop, ReAct (tool roundtrip), and omni-memory in one place.

## 1. Loop and ReAct vs Nanobot / ZeroClaw

### Reference behaviour (Nanobot, ZeroClaw)

- **Nanobot**: One `AgentLoop`; each message → session (by `channel:chat_id`) → context (history + memory window) → **LLM → tools → repeat** until done → publish. MCP tools in same registry as built-in tools.
- **ZeroClaw**: Rust, one agent loop; gateway/daemon/service are modes of the same runtime; trait-based Provider/Channel/Memory/Tool.

### Our loop (omni-agent)

One **ReAct cycle** per user turn is implemented in `Agent::run_turn`:

1. **Optional recall**: If memory is enabled, run `two_phase_recall(intent)` and inject "Relevant past experiences" as first system message.
2. **Build messages**: Session history + user message (and recall context when present).
3. **LLM**: Call OpenAI-compatible `/v1/chat/completions` with optional `tools`.
4. **Tool round**: If the LLM returns `tool_calls`, call each via MCP `tools/call`, append results to messages, then go back to step 3 (up to `max_tool_rounds`).
5. **Final reply**: When the LLM returns no `tool_calls`, append the turn to session and, if memory is enabled, **store_episode** (intent + experience + outcome).

So: **one `run_turn` = one Nanobot-style “process message”** (session + optional recall → LLM ↔ tools loop → store). Gateway/stdio only differ by transport; the loop is the same.

## 2. Test layers

| Layer           | What                                                                           | Where                                                               |
| --------------- | ------------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| **Unit**        | Config, session, qualify/parse, agent `from_config` with memory                | `config_and_session`, `multiple_mcp`, `config_mcp`, `gateway_stdio` |
| **Integration** | One turn with real LLM; one turn with LLM + MCP (ReAct); two turns with memory | `agent_integration`                                                 |

### What each test covers

| Test                                      | Loop (LLM) | ReAct (tool roundtrip)       | Memory (recall + store)           |
| ----------------------------------------- | ---------- | ---------------------------- | --------------------------------- |
| `config_and_session`                      | —          | —                            | `from_config` with `MemoryConfig` |
| `agent_from_config_with_memory_succeeds`  | —          | —                            | Agent builds with memory          |
| `test_agent_one_turn_with_llm_and_mcp`    | ✓          | ✓ (if model uses a tool)     | —                                 |
| `test_agent_one_turn_litellm_project_mcp` | ✓          | ✓ (if MCP + model uses tool) | —                                 |
| **`test_agent_react_flow_tool_used`**     | ✓          | **✓ (required)**             | —                                 |
| `test_agent_two_turns_memory_stored`      | ✓          | optional                     | ✓ (episode count ≥ 2)             |

- **Loop**: Any integration test that calls `run_turn` and gets a non-empty reply exercises the loop (LLM call, optional tool rounds, final reply).
- **ReAct (same as Nanobot/ZeroClaw)**: `test_agent_react_flow_tool_used` **requires** the model to use a tool: it sends a prompt that asks the model to call the echo (demo) tool with a fixed string; the test asserts the final reply contains that string, proving the path **LLM → tool_calls → MCP tools/call → LLM → final reply** ran. This is the same flow as Nanobot’s “LLM + tools” and ZeroClaw’s tool execution in the loop.
- **Memory**: Unit test ensures the agent builds with memory; `test_agent_two_turns_memory_stored` runs two turns and asserts `test_episode_count() >= 2`.

## 3. Running the tests

### Unit tests (no network, no API key)

```bash
cargo test -p omni-agent --test config_and_session
cargo test -p omni-agent --test multiple_mcp
cargo test -p omni-agent --test config_mcp
cargo test -p omni-agent --test gateway_stdio
```

### Integration tests (real LLM and/or MCP; run with `--ignored`)

Require env (and optionally a running MCP server):

- `LITELLM_PROXY_URL` or `OMNI_AGENT_INFERENCE_URL` (inference endpoint)
- `OMNI_AGENT_MODEL` (model name)
- `OPENAI_API_KEY` or `OMNI_AGENT_INFERENCE_API_KEY` (unless inference is local)
- For project MCP: `.mcp.json` in project root or `MCP_CONFIG_PATH` / `PRJ_ROOT`

```bash
# One turn (loop; ReAct if MCP + model use a tool)
cargo test -p omni-agent --test agent_integration test_agent_one_turn_litellm_project_mcp -- --ignored

# ReAct flow: model must use a tool (loop + tool roundtrip, like Nanobot/ZeroClaw)
cargo test -p omni-agent --test agent_integration test_agent_react_flow_tool_used -- --ignored

# Two turns with memory (loop + memory store)
cargo test -p omni-agent --test agent_integration test_agent_two_turns_memory_stored -- --ignored
```

To run all integration tests:

```bash
cargo test -p omni-agent --test agent_integration -- --ignored
```

## 4. Unified “matrix” (what to run for parity)

To approximate Nanobot/ZeroClaw behaviour in one go:

1. **Unit**: All unit tests above (config, session, MCP qualify/parse, gateway/stdio, agent with memory from_config).
2. **Loop + ReAct**: Run **`test_agent_react_flow_tool_used`** — this explicitly requires the model to call an MCP tool (echo) and asserts the reply contains the tool result, matching the Nanobot/ZeroClaw “model uses tool” flow.
3. **Memory**: `test_agent_two_turns_memory_stored` (two turns, then assert episode count ≥ 2).

Together these cover: **loop**, **ReAct (tool roundtrip, same as reference projects)**, and **memory (recall + store)** in a single test suite.

## 5. Session Compression Tracking (2026-02-18)

This round adds rolling session compression in `omni-agent` so long-running channel sessions
can keep recent turns while preserving older context as compact summaries.

### Implemented

- Added `SessionSummarySegment` (session summary record) and persistence path:
  - in-memory bounded store
  - Valkey/Redis backend (`omni-agent:session:summary:<session_id>`)
- Consolidation now does both:
  - drains oldest turns and stores one episode into `omni-memory`
  - stores one compact summary segment for prompt reuse
- Prompt context for bounded sessions now includes:
  - compacted summary segments (old history)
  - recent window turns (working memory)

### Config added

- `summary_max_segments` (default `8`)
- `summary_max_chars` (default `480`)
- `consolidation_async` (default `true`)
- `context_budget_tokens` (optional total context budget)
- `context_budget_reserve_tokens` (default `512`)

Paths and env:

- `session.summary_max_segments` and `session.summary_max_chars` in `settings.yaml`
- `session.consolidation_async`
- `session.context_budget_tokens`
- `session.context_budget_reserve_tokens`
- `OMNI_AGENT_SUMMARY_MAX_SEGMENTS`
- `OMNI_AGENT_SUMMARY_MAX_CHARS`
- `OMNI_AGENT_CONSOLIDATION_ASYNC`
- `OMNI_AGENT_CONTEXT_BUDGET_TOKENS`
- `OMNI_AGENT_CONTEXT_BUDGET_RESERVE_TOKENS`

### Tests added/updated

- `tests/session_summary.rs`
  - bounded summary retention + trimming
  - clear session removes both window and summary data
- `tests/agent_context_budget.rs`
  - latest non-system message retention under budget
  - reserve-token behavior
  - truncation behavior for oversized content
- `tests/config_settings.rs`
  - user-over-system merge for summary settings
- Updated explicit `AgentConfig` builders in integration/unit examples to include summary fields

### Verification

- Commands:
  - `cargo test -p omni-agent --test agent_summary --test agent_context_budget --test config_settings -q`
  - `cargo test -p omni-agent --test session_summary -q`
- Result on **2026-02-18**: pass for targeted memory/session tests

## 6. References

- [omni-run-react-gateway-design.md](../plans/omni-run-react-gateway-design.md) — Nanobot analysis, session window, gateway.
- [omni-run-roadmap-nanobot-zeroclaw.md](../plans/omni-run-roadmap-nanobot-zeroclaw.md) — Product goal and phased roadmap.
- [rust-agent-architecture-omni-vs-zeroclaw.md](../plans/rust-agent-architecture-omni-vs-zeroclaw.md) — Architecture comparison.

**Local reference implementations (researcher cache):**

- ZeroClaw source: `.cache/researcher/zeroclaw-labs/zeroclaw/`
- Other harvested/cloned repos: `.cache/researcher/`
