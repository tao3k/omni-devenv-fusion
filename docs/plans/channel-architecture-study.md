# Channel Architecture Study: Nanobot and ZeroClaw

> Study of how Nanobot and ZeroClaw implement chat channels (Telegram, Discord, etc.) so we can implement our own. **Read this before implementing Omni channels.**

---

## 1. Nanobot (Python)

**Repo**: [github.com/HKUDS/nanobot](https://github.com/HKUDS/nanobot)  
**Paths**: `nanobot/channels/`, `nanobot/bus/`

### Structure

| File                                                                                                  | Purpose                                                        |
| ----------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `base.py`                                                                                             | Base channel class / interface                                 |
| `manager.py`                                                                                          | ChannelManager — starts channels, routes to agent              |
| `telegram.py`                                                                                         | Telegram channel                                               |
| `discord.py`, `slack.py`, `email.py`, `feishu.py`, `dingtalk.py`, `qq.py`, `whatsapp.py`, `mochat.py` | Other channels                                                 |
| `bus/`                                                                                                | MessageBus — `InboundMessage`, `OutboundMessage`, `MessageBus` |

### Flow

1. **MessageBus** decouples channels from agent: `consume_inbound` / `publish_outbound`
2. **ChannelManager** starts all configured channels; each channel pushes to the bus
3. **Session** key: `channel:chat_id` (e.g. `telegram:123456`)
4. **allowFrom** whitelist for security

### Key files to inspect

- `nanobot/channels/base.py` — channel interface
- `nanobot/channels/manager.py` — how channels are started and wired
- `nanobot/channels/telegram.py` — Telegram polling/webhook
- `nanobot/bus/queue.py` — MessageBus implementation

---

## 2. ZeroClaw (Rust)

**Repo**: [github.com/zeroclaw-labs/zeroclaw](https://github.com/zeroclaw-labs/zeroclaw)  
**Paths**: `src/channels/`

### Structure

| File                                                                                                                        | Purpose                                                                  |
| --------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `traits.rs`                                                                                                                 | `Channel` trait + `ChannelMessage` struct                                |
| `mod.rs`                                                                                                                    | `start_channels`, `process_channel_message`, `run_message_dispatch_loop` |
| `telegram.rs`                                                                                                               | TelegramChannel (long-poll Bot API)                                      |
| `discord.rs`, `slack.rs`, `matrix.rs`, `whatsapp.rs`, `imessage.rs`, `email_channel.rs`, `irc.rs`, `lark.rs`, `dingtalk.rs` | Other channels                                                           |
| `cli.rs`                                                                                                                    | CliChannel                                                               |

### Channel trait (traits.rs)

```rust
#[async_trait]
pub trait Channel: Send + Sync {
    fn name(&self) -> &str;
    async fn send(&self, message: &str, recipient: &str) -> Result<()>;
    async fn listen(&self, tx: mpsc::Sender<ChannelMessage>) -> Result<()>;
    async fn health_check(&self) -> bool;
    async fn start_typing(&self, recipient: &str) -> Result<()>;
    async fn stop_typing(&self, recipient: &str) -> Result<()>;
}

pub struct ChannelMessage {
    pub id: String,
    pub sender: String,
    pub content: String,
    pub channel: String,
    pub timestamp: u64,
}
```

### Flow

1. **Single message bus**: `(tx, rx) = mpsc::channel(100)` — all channels send `ChannelMessage` to `tx`
2. **spawn_supervised_listener** per channel — long-running `listen()` with backoff on error
3. **run_message_dispatch_loop** — receives from `rx`, spawns `process_channel_message` per message (semaphore limits concurrency)
4. **process_channel_message**: memory recall → LLM + tools → `channel.send(response, sender)`
5. **Session**: `conversation_memory_key(msg) = "{channel}_{sender}_{id}"` — e.g. `telegram_alice_telegram_123_789`
6. **allowed_users** per channel — empty = deny all (secure default)

### Telegram specifics (telegram.rs)

- **Long-poll** `getUpdates` with `timeout: 30`
- **send**: `sendMessage` with Markdown; fallback to plain if Markdown fails
- **Message splitting**: 4096 chars per chunk; split at newline/space
- **Message ID**: `telegram_{chat_id}_{message_id}` — prevents duplicate memories after restart
- **Typing**: `sendChatAction` "typing" on receive
- **allowlist**: username or numeric user_id; `*` = allow all

---

## 3. Comparison: What to adopt

| Aspect               | Nanobot                       | ZeroClaw                              | Adopt                                                |
| -------------------- | ----------------------------- | ------------------------------------- | ---------------------------------------------------- |
| **Abstraction**      | Base class + Manager          | Channel trait                         | **Trait** — clear interface, testable                |
| **Message bus**      | MessageBus (Inbound/Outbound) | mpsc channel                          | **mpsc** — simple, one type                          |
| **Session key**      | channel:chat_id               | channel_sender_id                     | **channel:chat_id** — matches our gateway session_id |
| **Concurrency**      | —                             | Semaphore (4 per channel, 8–64 total) | **Yes** — avoid overload                             |
| **Listener restart** | —                             | spawn_supervised_listener + backoff   | **Yes** — resilience                                 |
| **Typing indicator** | —                             | start_typing / stop_typing            | **Yes** — UX                                         |
| **Message ID**       | —                             | platform ID (telegram_chat_msg)       | **Yes** — no duplicate memories                      |
| **Security**         | allowFrom                     | allowed_users, empty=deny             | **Empty=deny** — secure default                      |

---

## 4. Implementation plan for Omni

### Option A: Python channel layer (align with Python MCP)

- Add `packages/python/agent/src/omni/agent/channels/` (or `assets/skills/channel/`)
- Channel base class: `send`, `listen`, `health_check`
- Telegram channel: python-telegram-bot or httpx to Bot API
- Bridge: channel receives message → POST to `omni gateway --rust` (or Python gateway) with `session_id=telegram:{chat_id}`
- **Pro**: Reuse Python MCP, faster to ship
- **Con**: Two processes (channel bridge + agent)

### Option B: Rust channel layer (align with omni-agent)

- Add `packages/rust/crates/omni-agent/src/channels/` — `Channel` trait, `TelegramChannel`
- `omni-agent channel start` — starts listeners, dispatches to existing `run_turn`
- **Pro**: Single binary, same process as gateway
- **Con**: More Rust work, need to add channel deps (reqwest for Telegram API)

### Recommended: Option B (Rust)

- omni-agent already has gateway, stdio, repl — channels fit naturally
- ZeroClaw’s `Channel` trait is a proven pattern
- Session: `session_id = format!("telegram:{}", chat_id)` — our gateway already accepts any session_id

### First channel: Telegram

1. `Channel` trait in `omni-agent` (mirror ZeroClaw traits.rs)
2. `TelegramChannel`: `listen` = long-poll getUpdates, `send` = sendMessage
3. Config: `--bot-token` / `TELEGRAM_BOT_TOKEN`, plus `telegram.allowed_users` (settings/env)
4. `omni-agent channel --telegram` or `omni channel --rust --telegram`
5. Wire: `ChannelMessage` → `run_turn(session_id, message)` → `channel.send(output, recipient)`

---

## 5. Repo paths (quick reference)

| Project      | Channels                | Bus/Transport                                  |
| ------------ | ----------------------- | ---------------------------------------------- |
| **Nanobot**  | `nanobot/channels/*.py` | `nanobot/bus/`                                 |
| **ZeroClaw** | `src/channels/*.rs`     | `src/channels/mod.rs` (mpsc in start_channels) |

---

## 6. Changelog

- Initial study: Nanobot channels + bus, ZeroClaw Channel trait + flow
- Documented Telegram specifics, session keys, security, implementation options
