# Discord Channel — Runtime Reference

> HTTP-ingress Discord channel runtime for `omni-agent` with allowlists, session partitioning, and control-command authorization.

---

## Start

```bash
DISCORD_BOT_TOKEN=<token> \
cargo run -p omni-agent -- channel \
  --provider discord \
  --allowed-users "123456789" \
  --ingress-bind 0.0.0.0:8082 \
  --ingress-path /discord/ingress
```

The runtime receives Discord-style message events on `POST /discord/ingress` (or custom path), runs one agent turn, and replies through Discord REST (`/channels/{id}/messages`).

Managed command path is handled before LLM turns:

- Session/control: `/help`, `/session*`, `/feedback*`, `/reset`, `/clear`, `/resume*`,
  `/session partition*`
- Background: `/bg`, `/job`, `/jobs`

---

## Implementation Module Map

- `packages/rust/crates/omni-agent/src/channels/discord/runtime/mod.rs`: runtime facade exports and interface-only module wiring.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/config.rs`: Discord runtime config parsing/defaults.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/run.rs`: Discord ingress runtime orchestration loop.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/dispatch.rs`: foreground turn dispatch and managed-command short-circuit.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/ingress.rs`: HTTP ingress app builder and request-to-message conversion.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/mod.rs`: managed-command runtime facade.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/handlers/mod.rs`: managed command execution facade.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/handlers/command_dispatch.rs`: managed command dispatch path (`/session*`, `/bg`, `/job`, `/jobs`).
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/handlers/background_completion.rs`: background completion notification rendering/dispatch.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/handlers/auth.rs`: managed command ACL helpers.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/handlers/send.rs`: managed command reply/completion send wrappers.
- `packages/rust/crates/omni-agent/src/channels/discord/runtime/managed/handlers/events.rs`: managed command observability event constants.
- `packages/rust/crates/omni-agent/src/channels/managed_runtime/turn.rs`: cross-channel foreground turn utilities (`session_id`, timeout execution, error classification).

---

## settings.yaml

```yaml
discord:
  allowed_users: "123456789,owner"
  allowed_guilds: "3001,3002"

  admin_users: "owner"
  # Optional override: when configured, this is the only source for privileged control commands.
  # control_command_allow_from: "owner,ops"

  # Optional per-command mapping rules (used only when control_command_allow_from is unset).
  # Format: <command-selector>=>user1,user2;...
  # admin_command_rules: "/session partition=>owner;/reset,/clear=>ops;session.*=>owner"

  # Optional explicit override for managed slash commands (`/session*`, `/job`, `/jobs`, `/bg`).
  # Empty string means deny all managed slash commands.
  # slash_command_allow_from: "owner,ops"
  # Optional command-scoped slash grants (used when slash_command_allow_from is unset):
  # slash_session_status_allow_from: "auditor"
  # slash_session_budget_allow_from: "auditor"
  # slash_session_memory_allow_from: "auditor"
  # slash_session_feedback_allow_from: "ops"
  # slash_job_allow_from: "ops"
  # slash_jobs_allow_from: "ops"
  # slash_bg_allow_from: "runner"

  ingress_bind: "0.0.0.0:8082"
  ingress_path: "/discord/ingress"
  # ingress_secret_token: "replace-with-shared-secret"

  # guild_channel_user | channel | user | guild_user
  session_partition: "guild_channel_user"

  inbound_queue_capacity: 512
  turn_timeout_secs: 120

  # Example profile: guild-open chat + admin-only privileged controls
  # allowed_users: "owner"
  # allowed_guilds: "*"
  # admin_users: "owner"
  # control_command_allow_from: "owner"
  # admin_command_rules: "/session partition=>owner;/reset,/clear=>owner"
```

---

## Environment Variables

- `DISCORD_BOT_TOKEN`
- `OMNI_AGENT_DISCORD_ALLOWED_USERS`
- `OMNI_AGENT_DISCORD_ALLOWED_GUILDS`
- `OMNI_AGENT_DISCORD_ADMIN_USERS`
- `OMNI_AGENT_DISCORD_CONTROL_COMMAND_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_ADMIN_COMMAND_RULES`
- `OMNI_AGENT_DISCORD_SLASH_COMMAND_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_SESSION_STATUS_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_SESSION_BUDGET_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_SESSION_MEMORY_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_SESSION_FEEDBACK_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_JOB_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_JOBS_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_SLASH_BG_ALLOW_FROM`
- `OMNI_AGENT_DISCORD_INGRESS_BIND`
- `OMNI_AGENT_DISCORD_INGRESS_PATH`
- `OMNI_AGENT_DISCORD_INGRESS_SECRET_TOKEN`
- `OMNI_AGENT_DISCORD_SESSION_PARTITION`
- `OMNI_AGENT_DISCORD_INBOUND_QUEUE_CAPACITY`
- `OMNI_AGENT_DISCORD_TURN_TIMEOUT_SECS`

Priority: CLI > env > `settings.yaml`.

---

## Rule Syntax

`admin_command_rules` uses command selectors instead of regex:

- Optional selector prefix: `cmd:` (readability helper)
- Exact command path: `/session partition` or `session.partition`
- Multiple selectors: `/reset,/clear`
- Wildcard prefix: `session.*`
- Global wildcard: `*`
- `@bot` suffixes are normalized for both selectors and incoming commands (`/reset@mybot` == `/reset`)

Examples:

- `/session partition=>owner`
- `/reset,/clear=>ops`
- `session.*=>owner`

Authorization priority:

1. `control_command_allow_from`
2. `admin_command_rules`
3. `admin_users`

Managed slash authorization priority:

1. `slash_command_allow_from`
2. `slash_*_allow_from` (command-scoped)
3. `admin_users`

---

## Ingress Contract

- Method: `POST`
- Path: `/discord/ingress` (configurable)
- Header (optional): `x-omni-discord-ingress-token` (must match configured secret)
- Payload shape (subset):

```json
{
  "id": "message_id",
  "content": "hello",
  "channel_id": "2001",
  "guild_id": "3001",
  "author": {
    "id": "1001",
    "username": "alice"
  }
}
```

If sender/guild is not authorized, the event is ignored.

For managed slash/control commands, ACL denial returns a structured permission message instead of
running a model turn.

Authorized managed commands are executed in Discord runtime directly (not via LLM foreground turn),
including background queue submission (`/bg`) and completion push notifications.
