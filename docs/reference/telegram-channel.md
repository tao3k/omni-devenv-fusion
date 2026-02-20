# Telegram Channel — Production Reference

> High-concurrency Telegram bot engine. Webhook mode, Valkey dedup, user/group allowlists. **Commercial-ready.**

---

## Overview

| Feature           | Implementation                                                                                                    |
| ----------------- | ----------------------------------------------------------------------------------------------------------------- |
| Transport         | Webhook (multi-instance, horizontal scaling)                                                                      |
| Deduplication     | Valkey/Redis (idempotent, no duplicate processing)                                                                |
| Access control    | `allowed_users` + `allowed_groups` + `group_policy` + `admin_users`                                               |
| Session isolation | `chat_id` per conversation by default (`chat` mode) + session-scoped memory recall/store (`session_id` scope key) |
| Background jobs   | `/bg`, `/job`, `/jobs` commands                                                                                   |

---

## Implementation Module Map

- `packages/rust/crates/omni-agent/src/channels/telegram/channel/mod.rs`: interface surface (module wiring, public exports, shared channel state).
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/state.rs`: `TelegramChannel` state carrier, API base env key, and shared channel-local helpers.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/policy.rs`: control/slash policy types and slash-rule authorization matcher.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/constructor.rs`: channel constructors and runtime initialization path.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/mod.rs`: ACL facade exports and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/types.rs`: ACL field constants and resolved ACL config carriers.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/normalization.rs`: identity normalization and control/slash policy normalization.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/slash_policy.rs`: managed slash policy rule construction.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/parsing.rs`: env/settings parsing helpers (string/bool/list parsing).
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/group_overrides.rs`: per-group/per-topic ACL override parsing.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl/settings.rs`: runtime settings -> ACL resolution assembly.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/acl_reload.rs`: settings fingerprinting and hot-reload apply flow.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/authorization.rs`: control/slash authorization evaluation.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/recipient_admin.rs`: recipient-scoped admin override mutation and resolution.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/identity.rs`: Telegram identity normalization and recipient parsing helpers.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/send_api/mod.rs`: outbound Telegram API send stack facade.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/send_api/request.rs`: generic API send request + retry entrypoints.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/send_api/gate.rs`: local/distributed (Valkey) send gate wait/update lifecycle.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/send_api/media.rs`: media URL/upload/media-group send flows with retry and caption fallback.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/send_api/chat_action.rs`: `sendChatAction` dispatch path with gate integration.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/send_api/response.rs`: Telegram HTTP/API response validation and error extraction.
- `packages/rust/crates/omni-agent/src/channels/telegram/channel/trait_impl.rs`: `Channel` trait implementation for Telegram.

### Runtime Jobs Module Map

- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/mod.rs`: jobs runtime facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/api.rs`: jobs runtime orchestration adapters (`handle_inbound_message`, completion push, preview utilities).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_router/mod.rs`: inbound command routing facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_router/dispatch.rs`: inbound command route dispatch orchestrator.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_router/session.rs`: session/control command chain dispatch.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_router/background.rs`: background command chain dispatch.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_router/foreground.rs`: foreground queue fallback forwarding.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/mod.rs`: command-handler namespace wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/background_jobs/mod.rs`: background-command facade (`/job`, `/jobs`, `/bg`).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/background_jobs/events.rs`: background-command observability event constants.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/background_jobs/job_status.rs`: `/job <id>`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/background_jobs/jobs_summary.rs`: `/jobs`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/background_jobs/background_submit.rs`: `/bg <prompt>`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/mod.rs`: session-command facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/events.rs`: structured event-name constants for session-command replies.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/helpers.rs`: shared helper functions (preview truncation, delegated-admin mutation reply formatting).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/session_context.rs`: `/session`, `/session budget`, `/session memory`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/session_feedback.rs`: `/session feedback`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/session_injection.rs`: `/session inject`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/session_admin.rs`: `/session admin`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_commands/session_partition.rs`: `/session partition`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_control/mod.rs`: session-control facade (`/help`, `/reset|/clear`, `/resume*`).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_control/events.rs`: session-control observability event constants.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_control/help.rs`: `/help`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_control/reset.rs`: `/reset` and `/clear`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/command_handlers/session_control/resume.rs`: `/resume`, `/resume status`, `/resume drop`.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/observability/mod.rs`: observability facade exports.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/observability/send.rs`: outbound send wrapper with structured logs.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/observability/render.rs`: Telegram payload render mode selection.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/observability/json_summary.rs`: JSON reply summary extraction/tokens.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/jobs/observability/preview.rs`: preview text normalization/truncation.

### Runtime Entry Module Map

- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/mod.rs`: runtime facade exports.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_polling/mod.rs`: polling-mode runtime facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_polling/run.rs`: polling-mode runtime orchestration entrypoint.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_polling/channel_listener.rs`: polling transport/channel bootstrap and listener task spawn.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_polling/loop_control.rs`: polling runtime event loop (inbound, completion, shutdown).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_webhook/mod.rs`: webhook-mode runtime facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_webhook/run.rs`: webhook-mode runtime orchestration entrypoint.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_webhook/secret.rs`: webhook secret normalization/validation.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_webhook/server.rs`: webhook server lifecycle (start/stop/health-drain).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/run_webhook/loop_control.rs`: webhook runtime event loop (inbound, completion, shutdown, server health).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/console.rs`: shared startup console output helpers.

### Runtime Dispatch Module Map

- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/dispatch/mod.rs`: foreground runtime dispatch facade.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/dispatch/startup.rs`: runtime startup wiring and queue/session-gate bootstrap.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/dispatch/worker_pool.rs`: foreground worker pool and session gate acquisition.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/dispatch/turn.rs`: per-message turn execution, timeout/error handling, send reply.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/dispatch/preview.rs`: log preview normalization/truncation.

### Session Gate Module Map

- `packages/rust/crates/omni-agent/src/channels/telegram/session_gate/mod.rs`: session gate facade exports (`SessionGate`), with interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/session_gate/types.rs`: session gate shared types (`SessionGate`, `SessionGuard`, backend/entry/permit carriers).
- `packages/rust/crates/omni-agent/src/channels/telegram/session_gate/core.rs`: session gate construction, backend selection, and acquire path orchestration.
- `packages/rust/crates/omni-agent/src/channels/telegram/session_gate/local.rs`: local in-process permit lifecycle and entry cleanup semantics.
- `packages/rust/crates/omni-agent/src/channels/telegram/session_gate/config.rs`: environment/settings parsing and runtime config normalization.
- `packages/rust/crates/omni-agent/src/channels/telegram/session_gate/valkey.rs`: distributed lease implementation (acquire/renew/release, valkey command retry/reconnect).

### Runtime Webhook Module Map

- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/mod.rs`: webhook facade and public builders export.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/builders/mod.rs`: webhook app builder facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/builders/api.rs`: public webhook builder entrypoints and policy-assembly adapters.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/builders/core.rs`: webhook app core assembly and route wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/handler/mod.rs`: webhook handler facade and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/handler/entry.rs`: webhook handler entrypoint (auth, dedup, dispatch).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/handler/ingest.rs`: Telegram update parse/enqueue flow and inbound observability logs.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/auth.rs`: webhook secret-token validation.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/dedup.rs`: update-id dedup guard (fail-open).
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/path.rs`: webhook path normalization.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/state.rs`: shared webhook handler state.
- `packages/rust/crates/omni-agent/src/channels/telegram/runtime/webhook/app.rs`: `TelegramWebhookApp` runtime/testing bundle.

---

## Configuration

### settings.yaml

```yaml
telegram:
  # Private chats + who can talk in groups
  allowed_users: "123456789,987654321"
  # Group chats (any member can talk if group allowed)
  allowed_groups: "-200123456,-200789012"
  # Persist `/session admin ...` runtime mutations to user settings override file.
  # false: process-local only; true: write to $PRJ_CONFIG_HOME/omni-dev-fusion/settings.yaml
  session_admin_persist: false
  # Group sender policy: open|allowlist|disabled
  group_policy: "open"
  # Optional sender allowlist for group_policy=allowlist
  # group_allow_from: "123456789,987654321"
  # Mention-gating baseline for groups
  require_mention: false
  # Optional per-group/per-topic overrides
  # groups:
  #   "*":
  #     require_mention: true
  #     admin_users: "123456789"
  #   "-200123456":
  #     group_policy: "allowlist"
  #     allow_from: "123456789"
  #     admin_users: "123456789,987654321"
  #     topics:
  #       "42":
  #         group_policy: "open"
  #         require_mention: false
  #         admin_users: "987654321"
  # Privileged control-command admins (empty by default: deny privileged commands)
  admin_users: "123456789"
  # Optional explicit allowlist override for privileged control commands.
  # When configured, this overrides admin_command_rules and admin_users.
  # Empty string means deny all privileged control commands.
  # control_command_allow_from: "123456789,987654321"
  # Optional per-command admin rules (command-selector=>users; semicolon-separated)
  # admin_command_rules: "/session partition=>123456789;/reset,/clear=>987654321;session.*=>555666777"
  #
  # Optional global override for managed slash commands (non-privileged command set).
  # Empty string means deny all managed slash commands.
  # slash_command_allow_from: "123456789,987654321"
  #
  # Optional command-specific allowlists (friendly keys, no selector expression):
  # slash_session_status_allow_from: "123456789"
  # slash_session_budget_allow_from: "123456789"
  # slash_session_memory_allow_from: "123456789"
  # slash_session_feedback_allow_from: "987654321"
  # slash_job_allow_from: "987654321"
  # slash_jobs_allow_from: "987654321"
  # slash_bg_allow_from: "987654321"
  max_tool_rounds: 30
  foreground_session_gate_backend: "auto" # auto|memory|valkey
  foreground_session_gate_key_prefix: "omni-agent:session-gate"
  foreground_session_gate_lease_ttl_secs: 30
  foreground_session_gate_acquire_timeout_secs: 120
  send_rate_limit_gate_key_prefix: "omni-agent:telegram:send-gate"

session:
  window_max_turns: 2048
  consolidation_take_turns: 32
  summary_max_segments: 8
  summary_max_chars: 480
  consolidation_async: true
  context_budget_tokens: 6000
  context_budget_reserve_tokens: 512
  context_budget_strategy: "recent_first" # recent_first|summary_first

memory:
  # Memory state persistence backend: auto|local|valkey
  # auto: use Valkey when valkey url is configured, otherwise local files
  persistence_backend: "auto"
  # URL source is unified: VALKEY_URL or session.valkey_url
  persistence_key_prefix: "omni-agent:memory"
```

### Environment variables

| Variable                                                | Description                                                                   |
| ------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `TELEGRAM_BOT_TOKEN`                                    | Bot token (required)                                                          |
| `TELEGRAM_ALLOWED_USERS`                                | Comma-separated Telegram user_ids                                             |
| `TELEGRAM_ALLOWED_GROUPS`                               | Comma-separated group chat_ids (negative)                                     |
| `OMNI_AGENT_TELEGRAM_GROUP_POLICY`                      | Group sender policy (`open`, `allowlist`, `disabled`)                         |
| `OMNI_AGENT_TELEGRAM_GROUP_ALLOW_FROM`                  | Optional group sender allowlist (numeric user_ids)                            |
| `OMNI_AGENT_TELEGRAM_REQUIRE_MENTION`                   | Group mention gating baseline (`true`/`false`)                                |
| `OMNI_AGENT_TELEGRAM_SESSION_ADMIN_PERSIST`             | Persist `/session admin` runtime mutations to user settings (`true`/`false`)  |
| `OMNI_AGENT_TELEGRAM_ADMIN_USERS`                       | Comma-separated admin user_ids for privileged control commands                |
| `OMNI_AGENT_TELEGRAM_CONTROL_COMMAND_ALLOW_FROM`        | Optional explicit allowlist override for privileged control commands          |
| `OMNI_AGENT_TELEGRAM_ADMIN_COMMAND_RULES`               | Per-command admin rules: `<command-selector>=>user1,user2;...`                |
| `OMNI_AGENT_TELEGRAM_SLASH_COMMAND_ALLOW_FROM`          | Optional explicit allowlist override for managed slash commands               |
| `OMNI_AGENT_TELEGRAM_SLASH_SESSION_STATUS_ALLOW_FROM`   | Optional allowlist for `/session` and `/session status`                       |
| `OMNI_AGENT_TELEGRAM_SLASH_SESSION_BUDGET_ALLOW_FROM`   | Optional allowlist for `/session budget`                                      |
| `OMNI_AGENT_TELEGRAM_SLASH_SESSION_MEMORY_ALLOW_FROM`   | Optional allowlist for `/session memory` / `/session recall`                  |
| `OMNI_AGENT_TELEGRAM_SLASH_SESSION_FEEDBACK_ALLOW_FROM` | Optional allowlist for `/session feedback` / `/feedback`                      |
| `OMNI_AGENT_TELEGRAM_SLASH_JOB_ALLOW_FROM`              | Optional allowlist for `/job <id>`                                            |
| `OMNI_AGENT_TELEGRAM_SLASH_JOBS_ALLOW_FROM`             | Optional allowlist for `/jobs`                                                |
| `OMNI_AGENT_TELEGRAM_SLASH_BG_ALLOW_FROM`               | Optional allowlist for `/bg <prompt>`                                         |
| `TELEGRAM_WEBHOOK_SECRET`                               | Webhook secret token (required in `webhook` mode)                             |
| `OMNI_AGENT_TELEGRAM_API_BASE_URL`                      | Optional Telegram Bot API base override (default: `https://api.telegram.org`) |
| `VALKEY_URL`                                            | Unified Valkey endpoint used by dedup/session/memory/send-gate backends       |
| `OMNI_AGENT_TELEGRAM_SESSION_GATE_BACKEND`              | Session gate backend (`auto`, `memory`, `valkey`)                             |
| `OMNI_AGENT_TELEGRAM_SESSION_GATE_KEY_PREFIX`           | Distributed session gate key prefix                                           |
| `OMNI_AGENT_TELEGRAM_SESSION_GATE_LEASE_TTL_SECS`       | Distributed lease TTL seconds                                                 |
| `OMNI_AGENT_TELEGRAM_SESSION_GATE_ACQUIRE_TIMEOUT_SECS` | Wait timeout seconds for acquiring session lease                              |
| `OMNI_AGENT_TELEGRAM_SEND_RATE_LIMIT_GATE_KEY_PREFIX`   | Distributed outbound send gate key prefix                                     |
| `OMNI_AGENT_MEMORY_PERSISTENCE_BACKEND`                 | Memory state backend (`auto`, `local`, `valkey`)                              |
| `OMNI_AGENT_MEMORY_VALKEY_KEY_PREFIX`                   | Memory snapshot key prefix in Valkey                                          |
| `OMNI_AGENT_WINDOW_MAX_TURNS`                           | Session window size (turns)                                                   |
| `OMNI_AGENT_CONSOLIDATION_THRESHOLD_TURNS`              | Consolidation trigger threshold (turns)                                       |
| `OMNI_AGENT_CONSOLIDATION_TAKE_TURNS`                   | Turns drained per consolidation                                               |
| `OMNI_AGENT_SUMMARY_MAX_SEGMENTS`                       | Number of compact summary segments injected                                   |
| `OMNI_AGENT_SUMMARY_MAX_CHARS`                          | Max chars per compact summary segment                                         |
| `OMNI_AGENT_CONSOLIDATION_ASYNC`                        | Store consolidated episodes asynchronously                                    |
| `OMNI_AGENT_CONTEXT_BUDGET_TOKENS`                      | Total context token budget before each LLM call                               |
| `OMNI_AGENT_CONTEXT_BUDGET_RESERVE_TOKENS`              | Reserved tokens kept for response/tool headroom                               |
| `OMNI_AGENT_CONTEXT_BUDGET_STRATEGY`                    | Context retention strategy (`recent_first`, `summary_first`)                  |

### allowed_users

| Value                | Meaning                                         |
| -------------------- | ----------------------------------------------- |
| `""`                 | Deny all                                        |
| `*`                  | Allow all (testing only)                        |
| `123456789`          | Numeric Telegram user_id                        |
| `telegram:123456789` | Numeric Telegram user_id (prefixed, normalized) |
| `tg:123456789`       | Numeric Telegram user_id (prefixed, normalized) |
| `123,456,789`        | Comma-separated                                 |

### allowed_groups

| Value             | Meaning         |
| ----------------- | --------------- |
| `""`              | No groups       |
| `*`               | All groups      |
| `-200123`         | Group chat_id   |
| `-200123,-200456` | Comma-separated |

### group_policy

| Value       | Meaning                                                                                          |
| ----------- | ------------------------------------------------------------------------------------------------ |
| `open`      | Any sender in allowed groups can trigger normal turns                                            |
| `allowlist` | Group sender must match `group_allow_from` (or `allowed_users` when `group_allow_from` is unset) |
| `disabled`  | Drop all group messages                                                                          |

### group_allow_from

| Value         | Meaning                                                    |
| ------------- | ---------------------------------------------------------- |
| unset         | Use `allowed_users` fallback when `group_policy=allowlist` |
| `""`          | Explicitly deny all group senders for allowlist mode       |
| `123456789`   | Numeric Telegram user_id                                   |
| `123,456,789` | Comma-separated                                            |

### require_mention

| Value   | Meaning                                                                           |
| ------- | --------------------------------------------------------------------------------- |
| `false` | Group messages trigger normally (subject to ACL)                                  |
| `true`  | Group messages must be slash command, reply-to-bot, or include `@mention` trigger |

### admin_users

| Value         | Meaning                                                                |
| ------------- | ---------------------------------------------------------------------- |
| `""`          | Deny privileged control commands                                       |
| `123456789`   | Allow this admin user_id                                               |
| `*`           | Allow all identities to run privileged control commands (testing only) |
| `123,456,789` | Comma-separated                                                        |

### control_command_allow_from

| Value         | Meaning                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| unset         | Not configured; fall back to rule/admin chain                           |
| `""`          | Deny all privileged control commands                                    |
| `123456789`   | Allow this user_id for all privileged control commands                  |
| `*`           | Allow all identities for all privileged control commands (testing only) |
| `123,456,789` | Comma-separated                                                         |

### Privilege model

- `allowed_users` + `allowed_groups`: who can talk to the bot (normal turns + read-only commands).
- Group traffic has an independent policy chain:
  - `group_policy` baseline (`open|allowlist|disabled`)
  - optional `group_allow_from` (or `allowed_users` fallback when unset)
  - optional mention gating via `require_mention`
  - optional per-group/per-topic overrides under `groups.<chat_id>` and `groups.<chat_id>.topics.<thread_id>`
- Group policy override precedence is deterministic:
  - baseline (`group_policy` / `group_allow_from` / `require_mention`)
  - `groups."*"` (wildcard group override)
  - `groups."<chat_id>"`
  - `groups."<chat_id>".topics."<thread_id>"`
- `control_command_allow_from`: optional explicit override. When configured, this is the single authorization source for privileged control commands.
- `admin_command_rules`: optional per-command override (`<command-selector>=>user1,user2;...`), used only when `control_command_allow_from` is not configured.
- `admin_users`: fallback allowlist for privileged control commands when no rule matches.
- `groups.<chat_id>.admin_users` and `groups.<chat_id>.topics.<thread_id>.admin_users`:
  - recipient-scoped command admins (control + managed slash commands) for that group/topic only.
  - evaluated only when global ACL resolution falls back to `admin_users` stage.
  - do not bypass explicit global overrides (`control_command_allow_from`, `slash_command_allow_from`) or matched command-specific rules.
- `/session admin [list|set|add|remove|clear] [json]`:
  - mutates recipient-scoped delegated admins for current group/topic at runtime.
  - writes back into user settings only when `session_admin_persist=true`; otherwise process-local only.
- `admin_users` has secure default `""` (deny privileged commands) when omitted.
- Authorization priority: `control_command_allow_from` > `admin_command_rules` > `admin_users`.
- Managed slash commands (`/session`, `/session budget`, `/session memory`, `/session feedback`, `/job`, `/jobs`, `/bg`) use a separate ACL chain:
  - `slash_command_allow_from` (global override) > command-specific `slash_*_allow_from` > `admin_users` fallback.
  - `slash_*_allow_from` is additive for non-admin users; `admin_users` keep full command coverage.
  - Group members can still send normal text turns when `allowed_groups` permits the chat.
- Current privileged command set: `/reset` (`/clear`), `/resume`, `/resume drop`, `/session admin ...`, `/session partition ...`.
- Read-only exception: `/resume status` remains available to non-admin users.
- `admin_command_rules` selector syntax:
  - optional selector prefix: `cmd:` (for readability in config-heavy setups)
  - exact path: `/session partition` or `session.partition`
  - multi-selector: `/reset,/clear`
  - wildcard prefix: `session.*`
  - global wildcard: `*`
  - `@bot` suffixes are normalized for both selectors and incoming commands (`/reset@mybot` == `/reset`)

**Get chat_id**: Add @userinfobot to group, or check logs when unauthorized.

---

## Commands

### Quick start (polling)

```bash
TELEGRAM_BOT_TOKEN=<token> just agent-channel
```

`just agent-channel` bootstraps local Valkey on `127.0.0.1:6379` (override with
`just agent-channel <port>` or `VALKEY_PORT`).

### Webhook (production)

```bash
TELEGRAM_BOT_TOKEN=<token> just agent-channel-webhook
```

### Direct cargo

```bash
cargo run -p omni-agent -- channel \
  --mode webhook \
  --webhook-bind 127.0.0.1:8081 \
  --webhook-secret-token "<secret>" \
  --allowed-users "123456789" \
  --allowed-groups "-200123456"
```

---

## Production Deployment

1. **Valkey**: `just valkey-start` (or Redis)
2. **Reverse proxy**: nginx/Caddy → `http://127.0.0.1:8081`
3. **Webhook**: `curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://your-domain.com/telegram/webhook"`
4. **Agent**: Run with `--mode webhook`, `VALKEY_URL` set

---

## Background Commands

- `/bg <prompt>` — Queue long-running task
- `/job <id>` — Job status
- `/jobs` — Queue health

## Session Commands

- `/session` (`/session status`, `/window`, `/context`) — Show session context dashboard (overview, active window counters, and saved snapshot metadata).
- `/session budget` (`/window budget`, `/context budget`) — Show the latest token-budget packing snapshot for this session in dashboard format (overview, per-class counters, and bottleneck hints).
- `/session memory` (`/session recall`, `/window memory`, `/context recall`) — Show the latest memory-recall planning snapshot for this session (decision, adaptive `k1/k2/lambda`, pressure indicators, query token count, recall feedback bias, embedding source, pipeline duration, and injected context chars/result). `embedding_source` now distinguishes `embedding`, `embedding_repaired` (dimension drift auto-repaired), and `hash` fallback. Output now also includes process-level recall metrics (planned/injected/skipped counters, selected/injected totals, and latency buckets). Snapshot payload is stored under session backend keys, so Valkey deployments can inspect across agent instances.
- Explicit recall-feedback override: send `/session feedback up|down` (or `/feedback up|down`; `success|failure` aliases are also accepted). The same explicit signal is available inline via `feedback: success|failure` and `[feedback:success|failure]`. When absent, runtime falls back to tool execution summary and then assistant-text heuristic.
- `/reset` or `/clear` — Clear the active context window for this logical Telegram session; admin-only.
- `/resume` — Restore the latest cleared snapshot; admin-only.
- `/resume drop` (`/resume discard`) — Drop saved snapshot without restoring it; admin-only.
- `/resume status` (`/resume stats`, `/resume info`) — Inspect snapshot counters and age (read-only).
- `/session admin [list|set|add|remove|clear] [json]` (`/window admin ...`, `/context admin ...`) — Manage recipient-scoped delegated admins for the current group/topic at runtime. This updates `groups.<chat_id>.admin_users` or `groups.<chat_id>.topics.<thread_id>.admin_users` override state for the running process; `clear` removes the current-scope override and returns to inherited ACL behavior.
- `/session partition [mode|on|off] [json]` — Runtime session partition control (`chat`, `chat_user`, `user`, `chat_thread_user`); admin-only.

## Attachment Markers

Use marker syntax in outbound text when tool output includes media URLs or local files:

- `[IMAGE:https://example.com/a.png]` → `sendPhoto`
- `[IMAGE:/tmp/a.png]` or `[IMAGE:file:///tmp/a.png]` → `sendPhoto` (multipart upload)
- `[DOCUMENT:https://example.com/a.pdf]` → `sendDocument`
- `[VIDEO:https://example.com/a.mp4]` → `sendVideo`
- `[AUDIO:https://example.com/a.mp3]` → `sendAudio`
- `[VOICE:https://example.com/a.ogg]` → `sendVoice`

Behavior:

- If both text and markers are present:
  - short text (`<= 1024` chars) is attached as the first media caption when the first attachment type supports captions,
  - longer text is sent first (chunked if needed) to avoid truncation, then media is sent.
- Multiple compatible attachments are batched through `sendMediaGroup` where supported (`URL` and local-file `attach://` paths), split by Telegram's per-request limit (10 items), and segmented around unsupported types (for example `VOICE`); transient failures are retried with bounded backoff first, then sender falls back to sequential sends.
- Invalid markers are preserved as plain text (no content loss).
- Topic routing (`chat_id:thread_id`) is applied to both text and media payloads.
- MarkdownV2 fenced code blocks preserve safe language identifiers (for example `rust`, `python`, `c++`) and drop unsafe identifiers to avoid parse failures.

---

## Session Compression Semantics

- Session isolation key defaults to `chat_id` (configurable by partition mode).
- Partition behavior quick-reference:

| Mode               | Session key shape           | Same group, different users | Same user, different groups |
| ------------------ | --------------------------- | --------------------------- | --------------------------- |
| `chat` (default)   | `chat_id`                   | Shared                      | Isolated                    |
| `chat_user`        | `chat_id:user_id`           | Isolated                    | Isolated                    |
| `user`             | `user_id`                   | Shared                      | Shared                      |
| `chat_thread_user` | `chat_id:thread_id:user_id` | Isolated (per user/thread)  | Isolated                    |

- Recent turns are kept in a bounded window.
- Older drained turns are compressed into summary segments and persisted in session storage.
- On next turns, prompt context combines:
  - compressed summary segments (older history)
  - bounded recent turns (working history)
- Context budget packing is summary-aware (V2):
  - always retains the latest non-system turn (truncated if needed),
  - default strategy (`recent_first`) prioritizes recent dialogue turns before summary segments,
  - optional `summary_first` strategy prioritizes newer summary segments before older dialogue turns,
  - retains newer summary segments before older ones when budget is tight.

---

## Reliability Hardening (2026-02-18)

| Area                                | Current behavior                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UTF-8 safety                        | Chunk splitting is Unicode-safe and no longer slices at invalid UTF-8 byte boundaries.                                                                                                                                                                                                                                                                                                                                                                                            |
| Markdown fallback                   | Any Telegram `400 Bad Request` for MarkdownV2 now retries without `parse_mode`.                                                                                                                                                                                                                                                                                                                                                                                                   |
| API-level send errors               | `sendMessage` now validates both HTTP status and JSON `ok`; HTTP `200` with `ok=false` is treated as failure and triggers plain-text fallback for markdown sends.                                                                                                                                                                                                                                                                                                                 |
| Transient send retries              | `sendMessage` retries transient failures (`429` with `retry_after`, `5xx`, and transient network errors) with bounded backoff before surfacing failure; outbound send paths honor a shared `retry_after` gate with staggered post-gate release, and synchronize across instances through Valkey when `VALKEY_URL` (or `session.valkey_url`) is configured.                                                                                                                        |
| Topic/thread routing                | Recipient supports `chat_id:thread_id`; outbound payload includes `message_thread_id` so replies stay in the same Telegram forum topic.                                                                                                                                                                                                                                                                                                                                           |
| Attachment markers                  | Outbound text supports URL and local file targets in `[IMAGE:...]`, `[DOCUMENT:...]`, `[VIDEO:...]`, `[AUDIO:...]`, `[VOICE:...]`; short text can be attached as a first-media caption, while longer text is chunked and sent as messages before media to avoid truncation.                                                                                                                                                                                                       |
| Caption markdown fallback           | Caption sends (single media and media-group first item) try MarkdownV2 first and automatically retry with plain caption on Telegram `400` parse failures.                                                                                                                                                                                                                                                                                                                         |
| Markdown parser regression coverage | Markdown renderer regressions now explicitly cover fenced-code info-string normalization, CJK/full-width punctuation preservation in code blocks, large multibyte fenced-code payload stability, and local-file caption fallback integrity under Markdown parse failures.                                                                                                                                                                                                         |
| Media batching                      | Compatible attachment runs are batched with `sendMediaGroup` (including local files via multipart `attach://`), split at Telegram's 10-item limit, and automatically segmented around unsupported kinds; transient failures are retried with bounded backoff, then sender falls back to sequential attachment sends when retries are exhausted.                                                                                                                                   |
| Invalid marker safety               | Invalid attachment markers (e.g. non-URL targets) are preserved and delivered as plain text rather than dropped.                                                                                                                                                                                                                                                                                                                                                                  |
| Escaping overflow                   | If MarkdownV2 escaping pushes a chunk over 4096 chars, it is sent as plain text without truncation.                                                                                                                                                                                                                                                                                                                                                                               |
| Polling API errors                  | `getUpdates` handles both HTTP and JSON API errors (`401/403` fail-fast, `409` conflict backoff, `429` retry-after backoff).                                                                                                                                                                                                                                                                                                                                                      |
| HTTP timeout                        | Telegram client uses explicit connect/request timeout defaults to avoid hanging requests.                                                                                                                                                                                                                                                                                                                                                                                         |
| Context snapshot fidelity           | Bounded session `/reset` + `/resume` now snapshots/restores raw `omni-window` slots (instead of message-pair reconstruction), preserving per-slot metadata such as tool-call counts and checkpoint references.                                                                                                                                                                                                                                                                    |
| Context snapshot atomicity          | In Valkey-backed bounded mode, `/reset`, `/resume`, and snapshot drop use Lua-backed atomic key transitions (active ↔ backup + metadata) to avoid cross-instance race windows during concurrent operations.                                                                                                                                                                                                                                                                      |
| Session/Valkey observability        | Session store, bounded window store, and webhook dedup emit structured debug logs with stable `event` IDs (for example `session.window_slots.loaded`, `telegram.dedup.update_accepted`, `telegram.dedup.duplicate_detected`, `telegram.dedup.evaluated`) plus backend selection, append/read/clear/drain counts, and Valkey retry outcomes (`operation` + `attempt`).                                                                                                             |
| Memory state durability             | Episode/Q snapshots support `auto/local/valkey` persistence backend, with strict startup mode when backend is explicitly set to `valkey` and the backend is unavailable; memory persistence now emits structured startup/save events (`agent.memory.state_load_succeeded` / `agent.memory.state_load_failed` / `agent.memory.state_save_succeeded` / `agent.memory.state_save_failed`) with backend, strictness, reason, duration, and episode/Q counts for easier debug tracing. |
| Memory scope isolation              | Memory episodes are now persisted with a logical scope key (`session_id`) and runtime recall is executed with scope-filtered APIs, preventing cross-session memory contamination even when multiple chats/groups share one backend.                                                                                                                                                                                                                                               |
| CI isolation gate                   | PR checks now include deterministic isolation gates for Rust (`chat` + `chat_thread_user` partition paths and topic-scoped delegated admin ACL) and Python black-box harness logic (`test_agent_channel_command_events.py` + `test_agent_channel_session_matrix.py`).                                                                                                                                                                                                             |

### Targeted verification

```bash
cargo test -p omni-agent --test channels_telegram --test channels_telegram_chunking --test channels_telegram_polling
cargo test -p omni-agent --test channels_telegram_media
cargo test -p omni-agent --test channels_telegram_markdown
cargo test -p omni-agent --test channels_telegram telegram_send_global_rate_limit_gate_delays_parallel_send
cargo test -p omni-agent --test channels_telegram telegram_send_global_rate_limit_gate_spreads_parallel_followup_requests
cargo test -p omni-agent --test channels_telegram_send_gate telegram_send_rate_limit_valkey_constructor_rejects_invalid_url
cargo test -p omni-agent --test telegram_session_gate
cargo test -p omni-agent --test channels_telegram_group_policy telegram_group_policy_recipient_admin_users_runtime_mutation_topic_scope
cargo test -p omni-agent --test channels_telegram_group_policy telegram_group_policy_recipient_admin_users_runtime_mutation_group_topic_isolation
cargo test -p omni-agent --test channels_idempotency --test agent_session_context
cargo test -p omni-agent --test agent_memory_persistence_backend --test observability_session_events
cargo test -p omni-memory --test test_scope
cargo test -p omni-agent --test agent_memory_scope_isolation
uv run pytest -q packages/python/test-kit/tests/test_agent_channel_command_events.py packages/python/test-kit/tests/test_agent_channel_session_matrix.py
```

### Black-box webhook probe

Use the local probe to inject one synthetic Telegram webhook update and verify end-to-end processing from logs.
The probe now asserts that observed `session_key` matches the target `chat_id[:thread_id]:user_id` and fails on mismatch.

Group-profile file (pinned path for local runs):

- `.run/config/agent-channel-groups.env`
- Generated by `scripts/channel/capture_telegram_group_profile.py`
- Current profile variables include `OMNI_TEST_CHAT_ID`, `OMNI_TEST_CHAT_B`, `OMNI_TEST_CHAT_C`, and `OMNI_TEST_USER_ID`
- Black-box command scripts resolve webhook secret in this order: `--secret-token` > `TELEGRAM_WEBHOOK_SECRET` env > repo `.env` > `telegram.webhook_secret_token` in settings.

```bash
# Load pinned Telegram group profile for black-box runs
set -a
source .run/config/agent-channel-groups.env
set +a

# Basic: event-driven wait (no hard timeout)
just agent-channel-blackbox "ping from probe"

# Optional upper bound
just agent-channel-blackbox "/session json" 30

# Dedicated dedup probe: same update_id posted twice, must see accepted + duplicate events
just agent-channel-blackbox-dedup 25

# Memory-focused suite (quick black-box checks):
just test-omni-agent-memory-suite quick 25 25

# Memory-focused suite (quick + real non-command turn):
python3 scripts/channel/test_omni_agent_memory_suite.py --suite quick --require-live-turn --max-wait 90 --max-idle-secs 40 --username tao3k

# Memory-focused suite (full Rust regressions, when webhook runtime is not running):
python3 scripts/channel/test_omni_agent_memory_suite.py --suite full --skip-blackbox

# Memory-focused suite (full live validation, includes self-evolution DAG black-box scenario by default):
python3 scripts/channel/test_omni_agent_memory_suite.py --suite full --username tao3k --max-wait 90 --max-idle-secs 40

# Memory-focused suite (full but skip evolution DAG stage):
python3 scripts/channel/test_omni_agent_memory_suite.py --suite full --skip-evolution

# Memory A/B benchmark suite (baseline vs adaptive feedback):
just test-omni-agent-memory-benchmark both 1 90 40 1304799695

# Memory A/B benchmark suite (JSON/Markdown report written under .run/reports):
python3 scripts/channel/test_omni_agent_memory_benchmark.py --user-id 1304799695 --iterations 1 --max-wait 90 --max-idle-secs 40

# Session isolation matrix (dual session reset/resume/session commands):
python3 scripts/channel/test_omni_agent_session_matrix.py --max-wait 45 --max-idle-secs 30

# Memory benchmark pinned to one logical session target (recommended to avoid drift in shared runtime logs):
python3 scripts/channel/test_omni_agent_memory_benchmark.py --chat-id 1304799691 --user-id 1304799695 --iterations 1 --max-wait 90 --max-idle-secs 40

# Command-event admin suite using group profile (defaults to OMNI_TEST_CHAT_ID from profile)
python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}"

# Command-event admin matrix across Test1/Test2/Test3 from group profile
python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-matrix --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}"

# Command-event admin matrix with transient retry/backoff hardening (recommended for noisy shared runtime)
python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-matrix --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}" --matrix-retries 3 --matrix-backoff-secs 3 --max-wait 60 --max-idle-secs 40

# Command-event admin matrix with explicit cross-group contamination assertions and structured reports
python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-matrix --assert-admin-isolation --admin-user-id "${OMNI_TEST_USER_ID}" --matrix-retries 3 --matrix-backoff-secs 3 --output-json .run/reports/agent-channel-command-events.json --output-markdown .run/reports/agent-channel-command-events.md

# Command-event admin matrix in a specific forum topic/thread scope
python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-matrix --assert-admin-isolation --group-thread-id 42 --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}"

# Same-group cross-topic delegated-admin isolation (thread A must not leak to thread B)
python3 scripts/channel/test_omni_agent_command_events.py --suite admin --assert-admin-topic-isolation --group-thread-id 42 --group-thread-id-b 43 --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}"

# Run admin suite against Test2/Test3 group ids from the same profile
OMNI_TEST_GROUP_CHAT_ID="${OMNI_TEST_CHAT_B}" python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}"
OMNI_TEST_GROUP_CHAT_ID="${OMNI_TEST_CHAT_C}" python3 scripts/channel/test_omni_agent_command_events.py --suite admin --admin-user-id "${OMNI_TEST_USER_ID}" --secret-token "${TELEGRAM_WEBHOOK_SECRET}"

# Acceptance runner: if OMNI_TEST_GROUP_THREAD_ID is set, it automatically adds:
# - command_events_topic_isolation step
# - session_matrix thread-aware run (`--thread-a/--thread-b`)
bash scripts/channel/agent-channel-acceptance.sh

# Advanced checks (regex expectations / forbidden patterns / idle guard)
# If webhook uses `allowed_users`, provide OMNI_TEST_USER_ID/--user-id.
bash scripts/channel/agent-channel-blackbox.sh \
  --prompt "/session budget json" \
  --user-id 1304799695 \
  --expect-log-regex "session_context" \
  --expect-bot-regex "session_budget" \
  --forbid-log-regex "tools/call: Mcp error" \
  --max-idle-secs 20

# Session-control commands are handled in the runtime fast path (`/reset`, `/resume`, `/session*`).
# They may not emit foreground `→ Bot` logs; validate with log expectations:
bash scripts/channel/agent-channel-blackbox.sh \
  --prompt "/reset" \
  --allow-no-bot \
  --expect-log-regex "session.context_window.reset" \
  --max-idle-secs 20
```

Admin matrix stability notes:

- `--admin-matrix` retries transient probe exits (`2`, `3`, `4`, `6`, `7`) with exponential backoff (`--matrix-backoff-secs`).
- Black-box duplicate dedup events are now treated as fatal only when the probe never reaches target dispatch; accepted+duplicate races no longer produce false negatives.
- `--assert-admin-isolation` performs extra per-group add/list/clear checks and cross-group zero-count assertions using `json_override_admin_count` from command-reply JSON summaries.
- `--assert-admin-topic-isolation` performs same-group cross-topic add/list/clear checks and enforces per-thread `json_override_admin_count` isolation.
- Use `--group-thread-id` to pin admin-matrix assertions to one Telegram forum topic; combine with session matrix `--thread-a/--thread-b` when validating cross-topic isolation in the same group.
- `--group-thread-id-b` can override secondary topic id; when omitted, it defaults to `group-thread-id + 1`.
- For strongest isolation signals, avoid running matrix probes concurrently with stress suites (MCP startup/concurrency sweeps, large memory benchmarks).

---

## Related

- `docs/how-to/run-rust-agent.md` §11 — Full guide
- `packages/conf/settings.yaml` — Default config
- `scripts/channel/agent-channel-webhook.sh` — Webhook launcher
- `scripts/channel/agent-channel-blackbox.sh` — Local black-box webhook probe entrypoint
- `scripts/channel/agent_channel_blackbox.py` — Black-box probe implementation (webhook inject + log-based reply wait)
- `scripts/channel/test_omni_agent_command_events.py` — Python command-event matrix probe (`test-omni-agent-command-events.sh` wrapper target)
- `scripts/channel/test-omni-agent-dedup-events.sh` — Deterministic dedup black-box probe (same update ID posted twice)
- `scripts/channel/test_omni_agent_dedup_events.py` — Python dedup probe implementation (`test-omni-agent-dedup-events.sh` wrapper target)
- `scripts/channel/check_omni_agent_event_sequence.py` — Python observability event-sequence checker (`check-omni-agent-event-sequence.sh` wrapper target)
- `scripts/channel/test_omni_agent_valkey_suite.py` — Unified Python Valkey live-suite runner (`--suite stress|session-gate|session-context|multi-http|multi-process|full`)
- `scripts/channel/test-omni-agent-valkey-full.sh` — Compatibility wrapper for the Python Valkey full-suite runner
- `scripts/channel/test_omni_agent_memory_suite.py` — Unified Python memory suite runner (`quick|full`, full includes self-evolution DAG by default; optional `--skip-evolution`, `--with-valkey`, `--skip-blackbox`)
- `scripts/channel/test-omni-agent-memory-suite.sh` — Compatibility wrapper for the Python memory suite runner
- `scripts/channel/test_omni_agent_memory_benchmark.py` — Unified Python memory A/B benchmark runner (baseline/adaptive, JSON+Markdown reports)
- `scripts/channel/test-omni-agent-memory-benchmark.sh` — Compatibility wrapper for the Python memory benchmark runner
- `.run/config/agent-channel-groups.env` — Pinned local Telegram group profile for black-box test chat ids/users
- `scripts/channel/test_omni_agent_session_matrix.py` — Session isolation matrix runner (dual-session reset/resume/session command flow)
- `scripts/channel/test-omni-agent-session-matrix.sh` — Compatibility wrapper for the Python session matrix runner
- `scripts/channel/test_omni_agent_concurrent_sessions.py` — Concurrent dual-session webhook probe (`same-chat/different-user`, `cross-chat/same-user` via `--chat-b`, and synthetic mode via `--allow-send-failure`)
- `scripts/channel/test-omni-agent-concurrent-sessions.sh` — Compatibility wrapper for the concurrent dual-session probe
- `scripts/channel/fixtures/memory_benchmark_scenarios.json` — Reproducible benchmark scenario dataset
- `scripts/channel/fixtures/memory_evolution_complex_scenarios.json` — High-complexity memory self-evolution + isolation DAG dataset
