# Run the Rust Agent (omni-agent)

> Verification checklist for omni-agent: gateway, stdio, repl, MCP, memory, and session window. Use this to confirm feature parity with Nanobot/ZeroClaw.

**Quick start**: After `cargo build -p omni-agent`, use `omni agent --rust` or `omni gateway --rust` to run the Rust agent from the main CLI.

---

## E2E Validation Checklist

| Step                | Command / Action                                                 | Status                                                 |
| ------------------- | ---------------------------------------------------------------- | ------------------------------------------------------ |
| 1. Build            | `cargo build -p omni-agent`                                      | ✅                                                     |
| 2. Unit tests       | `cargo test -p omni-agent`                                       | ✅                                                     |
| 3. Gateway + LLM    | Start MCP + gateway; `curl POST /message`                        | Manual (needs `OPENAI_API_KEY` or `LITELLM_PROXY_URL`) |
| 4. Stdio            | `echo "msg" \| cargo run -p omni-agent -- stdio`                 | Manual                                                 |
| 5. REPL             | `omni agent --rust` or `cargo run -p omni-agent -- repl`         | Manual                                                 |
| 6. Integration test | `cargo test -p omni-agent --test agent_integration -- --ignored` | Manual (needs API key + MCP)                           |

**Full E2E (Rust agent + Python MCP + LiteLLM)**: See §3 Gateway and §9 Integration test. Run `omni mcp --transport sse --port 3002` in one terminal, then `omni gateway --rust --webhook-port 8080`, then `curl` or run the integration test.

---

## Prerequisites

- **LLM**: `OPENAI_API_KEY` (or `ANTHROPIC_API_KEY` for Claude), or LiteLLM proxy (`LITELLM_PROXY_URL`, `OMNI_AGENT_MODEL`)
- **MCP** (optional): `omni mcp --transport sse --port 3002` running; add to `.mcp.json` (see below)

---

## 1. Build and unit tests

```bash
cargo build -p omni-agent
cargo test -p omni-agent
```

Or run the full test pipeline (includes omni-agent):

```bash
just test
```

**Expected**: Build succeeds; all non-ignored tests pass (config, session, MCP config, gateway validation, gateway HTTP 400/404, agent summarisation).

---

## 2. MCP config (.mcp.json)

Create or edit `.mcp.json` in project root:

```json
{
  "mcpServers": {
    "omniAgent": {
      "type": "http",
      "url": "http://127.0.0.1:3002"
    }
  }
}
```

If MCP server uses SSE at `/sse`, the agent appends it. Override path with `--mcp-config /path/to/mcp.json`.

---

## 3. Gateway (HTTP)

**Terminal 1** — start MCP (optional):

```bash
omni mcp --transport sse --port 3002
```

**Terminal 2** — start gateway:

```bash
# Via omni CLI (after cargo build -p omni-agent)
omni gateway --rust --webhook-port 8080 --webhook-host 0.0.0.0

# Or directly
cargo run -p omni-agent -- gateway --bind 0.0.0.0:8080
```

**Terminal 3** — send a message:

```bash
curl -X POST http://127.0.0.1:8080/message \
  -H "Content-Type: application/json" \
  -d '{"session_id":"s1","message":"Say hello in one sentence."}'
```

**Expected**: JSON `{"output":"...","session_id":"s1"}` with model reply.

**Validation**: Empty `session_id` or `message` returns 400.

---

## 4. Stdio mode

```bash
echo "What is 2+2?" | cargo run -p omni-agent -- stdio --session-id test-session
```

**Expected**: One line of model output printed to stdout.

---

## 5. REPL (interactive or one-shot)

**Via omni CLI** (after `cargo build -p omni-agent`):

```bash
omni agent --rust
```

**One-shot** (direct):

```bash
cargo run -p omni-agent -- repl --query "List three programming languages."
```

**Interactive** (read-eval-print loop):

```bash
cargo run -p omni-agent -- repl
# Type a message, press Enter; repeat. Exit with Ctrl+C or EOF.
```

## 6. Scheduled Jobs (Recurring)

Run recurring background jobs directly from CLI:

```bash
cargo run -p omni-agent -- schedule \
  --prompt "research latest Rust actor runtime benchmarks" \
  --interval-secs 300 \
  --max-runs 3 \
  --schedule-id nightly-research \
  --session-prefix scheduler \
  --recipient scheduler \
  --wait-for-completion-secs 30
```

What this does:

- Submits one background job every `interval-secs`
- Stops after `max-runs` (or runs until Ctrl+C if omitted)
- Waits up to `wait-for-completion-secs` for in-flight jobs before exit

Use this for long-running recurring tasks without external cron orchestration.

---

## 7. Memory (recall + store)

When `config.memory` is set, the agent:

- Calls `two_phase_recall(user_message)` before the LLM and injects a system message with relevant past experiences
- Stores each turn as an episode (`try_store_turn`) and optionally consolidates when the window is full

**To enable**: Use an `AgentConfig` with `memory: Some(MemoryConfig::default())` (or custom path/embedding_dim). The main CLI uses memory by default when building the agent.

**Verification**: Run several turns in the same session; later turns should reflect earlier context (if recall finds relevant episodes).

---

## 8. Session window + consolidation

When `config.window_max_turns` and `config.consolidation_threshold_turns` are set:

- Session history is bounded (ring buffer)
- When turn count ≥ threshold, oldest `consolidation_take_turns` turns are drained
- Drained turns are stored in two forms:
  - one `omni-memory` episode (for recall)
  - one compact session summary segment (for prompt reuse in future turns)

### Compression settings (session)

```yaml
session:
  window_max_turns: 2048
  consolidation_take_turns: 32
  # consolidation_threshold_turns: 1536
  summary_max_segments: 8
  summary_max_chars: 480
  consolidation_async: true
  context_budget_tokens: 6000
  context_budget_reserve_tokens: 512
```

Environment overrides:

- `OMNI_AGENT_WINDOW_MAX_TURNS`
- `OMNI_AGENT_CONSOLIDATION_THRESHOLD_TURNS`
- `OMNI_AGENT_CONSOLIDATION_TAKE_TURNS`
- `OMNI_AGENT_SUMMARY_MAX_SEGMENTS`
- `OMNI_AGENT_SUMMARY_MAX_CHARS`
- `OMNI_AGENT_CONSOLIDATION_ASYNC`
- `OMNI_AGENT_CONTEXT_BUDGET_TOKENS`
- `OMNI_AGENT_CONTEXT_BUDGET_RESERVE_TOKENS`

`context_budget_tokens` + `context_budget_reserve_tokens` enable token-budget packing before each LLM call, so the latest turn is retained while older context is trimmed/truncated to stay within budget.

**Verification**: Long session (e.g. 50+ turns) with memory + window enabled; check that consolidation runs (e.g. via logs or memory store).

---

## 9. Graceful shutdown

**Gateway**: Press Ctrl+C (or send SIGTERM on Unix). Server stops accepting new connections and waits for in-flight requests to finish.

**Expected**: Log "gateway stopped"; no abrupt connection drops.

---

## 10. Integration test (real LLM + MCP)

Requires `OPENAI_API_KEY` and optional MCP on port 3002:

```bash
cargo test -p omni-agent --test agent_integration -- --ignored
```

---

## 11. Telegram Channel (Production-Ready)

`omni-agent channel` runs a high-concurrency Telegram bot with webhook mode, Valkey dedup, and user/group allowlists. **Suitable for commercial deployment.**

### Architecture

| Component     | Default           | Purpose                                              |
| ------------- | ----------------- | ---------------------------------------------------- |
| Transport     | `webhook`         | Multi-instance, horizontal scaling                   |
| Dedup backend | `valkey` (Redis)  | Idempotent webhook handling, no duplicate processing |
| Session key   | `chat_id:user_id` | Isolates group members, bounded history per user     |

### Configuration: allowed_users and allowed_groups

**Priority**: CLI > `TELEGRAM_*` env > `telegram.*` in settings.yaml

#### allowed_users (private chats + who can talk in groups)

| Value                 | Meaning                                                       |
| --------------------- | ------------------------------------------------------------- |
| `""`                  | Deny all (secure default)                                     |
| `*`                   | Allow all users (testing only)                                |
| `123456789`           | Allow by **numeric Telegram user_id**                         |
| `telegram:123456789`  | Allow by numeric user_id with `telegram:` prefix (normalized) |
| `tg:123456789`        | Allow by numeric user_id with `tg:` prefix (normalized)       |
| `123456789,987654321` | Comma-separated numeric user_id allowlist                     |

#### allowed_groups (group chats — any member can talk if group allowed)

| Value             | Meaning                                   |
| ----------------- | ----------------------------------------- |
| `""`              | No groups allowed                         |
| `*`               | Allow all groups                          |
| `-200123`         | Allow group by chat_id (negative = group) |
| `-200123,-200456` | Comma-separated group allowlist           |

**How to get chat_id**: Add @userinfobot to the group, or check logs when an unauthorized message is rejected (logs show `chat_id=...`).

### settings.yaml examples

```yaml
telegram:
  # Single user (user_id preferred)
  allowed_users: "123456789"
  allowed_groups: ""

  # Multiple users
  # allowed_users: "123456789,987654321"

  # Single group (any member can talk)
  # allowed_groups: "-200123456"

  # Users + groups (private DMs + team group)
  # allowed_users: "123456789"
  # allowed_groups: "-200123456"

  # Testing: allow all
  # allowed_users: "*"
  # allowed_groups: "*"

  max_tool_rounds: 30
```

### .env example

```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USERS=123456789,987654321
TELEGRAM_ALLOWED_GROUPS=-200123456
```

### Polling (local testing)

```bash
TELEGRAM_BOT_TOKEN=<token> just agent-channel
```

`just agent-channel` now auto-starts local Valkey (`127.0.0.1:6379`) before
starting the polling runtime. Override with `just agent-channel <port>` or
`VALKEY_PORT`.

Or with explicit allowlist:

```bash
TELEGRAM_BOT_TOKEN=<token> \
TELEGRAM_ALLOWED_USERS=123456789 \
TELEGRAM_ALLOWED_GROUPS=-200123456 \
just agent-channel
```

### Webhook (production)

**Requirement**: Public HTTPS URL. Use ngrok for dev, or a reverse proxy (nginx, Caddy) for production.

**One-shot** (ngrok + setWebhook + agent):

```bash
TELEGRAM_BOT_TOKEN=<token> just agent-channel-webhook
```

Settings are read from `packages/conf/settings.yaml` when env vars are not set.

**Production deployment** (manual):

1. Start Valkey: `just valkey-start`
2. Expose webhook (e.g. nginx → `http://127.0.0.1:8081`)
3. Set webhook: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain.com/telegram/webhook"`
4. Run agent:

   ```bash
   TELEGRAM_BOT_TOKEN=<token> \
   TELEGRAM_ALLOWED_USERS=123456789 \
   TELEGRAM_ALLOWED_GROUPS=-200123456 \
   VALKEY_URL=redis://127.0.0.1:6379/0 \
   cargo run -p omni-agent -- channel \
     --mode webhook \
     --webhook-bind 0.0.0.0:8081 \
     --allowed-users "123456789" \
     --allowed-groups "-200123456"
   ```

### Background commands

- `/bg <prompt>` — Queue long-running task
- `/job <id>` — Job status
- `/jobs` — Queue health

### Valkey Stress Test

Run ignored stress tests that require a live Valkey backend:

```bash
just test-omni-agent-valkey-stress
```

Or directly:

```bash
VALKEY_URL=redis://127.0.0.1:6379/0 \
cargo test -p omni-agent --test channels_webhook_stress -- --ignored --nocapture
```

Stop local Valkey when done:

```bash
just valkey-stop
```

Implementation note: `just` channel/valkey recipes are thin wrappers; operational logic lives in `scripts/channel/*.sh`.

### Debugging

When no logs or bot reply appear:

- Use `--verbose` or `-v` for detailed logs (shows user messages and bot replies).
- Check logs: `Webhook received Telegram update` → Telegram reached the server; `Parsed message, forwarding to agent` → message processed.
- If no logs: Telegram is not reaching the server. Ensure webhook URL is public and `setWebhook` was called.

### Telegram hardening tests

Run Telegram-specific robustness tests (Unicode-safe chunking, markdown fallback including API-level `ok=false`, caption MarkdownV2 fallback for single/media-group sends, transient send retries, topic routing via `chat_id:thread_id`, URL/local attachment marker routing, short-text caption routing with long-text fallback, `sendMediaGroup` batching/split/fallback behavior, polling error handling):

```bash
cargo test -p omni-agent --test channels_telegram --test channels_telegram_chunking --test channels_telegram_markdown --test channels_telegram_media --test channels_telegram_polling
```

---

## 11. Scheduled Jobs (Recurring)

`omni-agent schedule` runs recurring prompts through the existing `JobManager` runtime.

One-shot finite run (useful for verification):

```bash
cargo run -p omni-agent -- schedule \
  --prompt "research compare rust actor runtimes" \
  --interval-secs 60 \
  --max-runs 3
```

Long-running scheduler (stop with Ctrl+C):

```bash
cargo run -p omni-agent -- schedule \
  --prompt "collect system summary" \
  --interval-secs 300
```

Notes:

- Scheduler submissions reuse background job workers (`JobManager`).
- `--max-runs` controls submission count; without it, scheduler runs until interrupted.
- `--wait-for-completion-secs` controls post-stop drain time for in-flight jobs.

---

## Env vars

| Var                      | Purpose                                                                                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY`         | API key for OpenAI-compatible endpoint                                                                                                                    |
| `ANTHROPIC_API_KEY`      | For Claude endpoints                                                                                                                                      |
| `LITELLM_PROXY_URL`      | **Recommended.** Chat completions URL (e.g. `http://127.0.0.1:4000/v1/chat/completions`). If unset, agent may infer from MCP URL, which is usually wrong. |
| `OMNI_AGENT_MODEL`       | Model id (e.g. `gpt-4o-mini`)                                                                                                                             |
| `OMNI_MCP_URL`           | Override MCP URL for one_turn example (otherwise from mcp.json)                                                                                           |
| `TELEGRAM_BOT_TOKEN`     | Telegram bot token for `omni-agent channel`                                                                                                               |
| `TELEGRAM_ALLOWED_USERS` | Comma-separated numeric Telegram user_ids. Empty denies all; `*` allows all. `telegram:` / `tg:` numeric prefixes are normalized.                         |
| `VALKEY_URL`             | Valkey/Redis URL for Telegram webhook dedup (default: `redis://127.0.0.1:6379/0`)                                                                         |

**First-time setup**: Set `LITELLM_PROXY_URL` (or run LiteLLM and point to it) and `OPENAI_API_KEY` before starting the agent. The MCP server URL in `.mcp.json` is for tools only, not chat.

---

## CLI reference

```bash
omni-agent gateway --help
omni-agent stdio --help
omni-agent repl --help
omni-agent channel --help
omni-agent schedule --help
```

**Gateway options**: `--bind`, `--turn-timeout`, `--max-concurrent`, `--mcp-config`

**Channel options**: `--bot-token`, `--mode` (polling|webhook), `--webhook-bind`, `--webhook-path`, `--webhook-secret-token`, `--webhook-dedup-backend` (memory|valkey), `--valkey-url`, `--webhook-dedup-ttl-secs`, `--webhook-dedup-key-prefix`, `--allowed-users` (empty=deny all, `*`=allow all), `-v`/`--verbose` (show user messages and bot replies in logs)
