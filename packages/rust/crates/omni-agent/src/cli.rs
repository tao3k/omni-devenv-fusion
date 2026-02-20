use std::path::PathBuf;

use clap::{Parser, Subcommand, ValueEnum};

use omni_agent::DEFAULT_STDIO_SESSION_ID;

#[derive(Parser)]
#[command(name = "omni-agent")]
#[command(about = "Rust agent: LLM + MCP tools. Gateway, stdio, or repl (interactive / one-shot).")]
pub(crate) struct Cli {
    /// Override config directory (same semantics as Python `--conf`).
    #[arg(long, global = true)]
    pub(crate) conf: Option<PathBuf>,

    #[command(subcommand)]
    pub(crate) command: Command,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub(crate) enum TelegramChannelMode {
    Polling,
    Webhook,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub(crate) enum ChannelProvider {
    Telegram,
    Discord,
}

#[derive(Debug, Clone, Copy, ValueEnum)]
pub(crate) enum WebhookDedupBackendMode {
    Memory,
    Valkey,
}

#[derive(Subcommand)]
pub(crate) enum Command {
    /// Run HTTP server (POST /message). Default bind: 0.0.0.0:8080
    Gateway {
        /// Listen address (e.g. 0.0.0.0:8080)
        #[arg(long, default_value = "0.0.0.0:8080")]
        bind: String,

        /// Per-turn timeout in seconds (default: 300)
        #[arg(long)]
        turn_timeout: Option<u64>,

        /// Max concurrent agent turns (default: 4; omit for no limit)
        #[arg(long)]
        max_concurrent: Option<usize>,

        /// Path to mcp.json (default: .mcp.json)
        #[arg(long, default_value = ".mcp.json")]
        mcp_config: PathBuf,
    },
    /// Read lines from stdin, run turn, print output. Exit on EOF or Ctrl+C.
    Stdio {
        /// Session ID for conversation (default: default)
        #[arg(long, default_value = DEFAULT_STDIO_SESSION_ID)]
        session_id: String,

        /// Path to mcp.json (default: .mcp.json)
        #[arg(long, default_value = ".mcp.json")]
        mcp_config: PathBuf,
    },
    /// REPL: interact with the model (complex intents, tool use). One-shot with --query, or interactive loop.
    Repl {
        /// Run one turn with this intent and exit (no interactive loop).
        #[arg(long)]
        query: Option<String>,

        /// Session ID for conversation (default: default)
        #[arg(long, default_value = DEFAULT_STDIO_SESSION_ID)]
        session_id: String,

        /// Path to mcp.json (default: .mcp.json)
        #[arg(long, default_value = ".mcp.json")]
        mcp_config: PathBuf,
    },
    /// Run recurring scheduled jobs via JobManager.
    Schedule {
        /// Prompt executed on every schedule tick.
        #[arg(long)]
        prompt: String,

        /// Tick interval in seconds.
        #[arg(long, default_value_t = 300)]
        interval_secs: u64,

        /// Optional number of submissions before exit.
        #[arg(long)]
        max_runs: Option<u64>,

        /// Logical schedule id for session namespacing.
        #[arg(long, default_value = "default")]
        schedule_id: String,

        /// Session prefix for generated schedule job sessions.
        #[arg(long, default_value = "scheduler")]
        session_prefix: String,

        /// Recipient identifier attached to job records/completions.
        #[arg(long, default_value = "scheduler")]
        recipient: String,

        /// Grace period (seconds) to drain in-flight completions before exit.
        #[arg(long, default_value_t = 30)]
        wait_for_completion_secs: u64,

        /// Path to mcp.json (default: .mcp.json)
        #[arg(long, default_value = ".mcp.json")]
        mcp_config: PathBuf,
    },
    /// Run messaging channel runtime (`telegram` or `discord`).
    Channel {
        /// Channel provider.
        #[arg(long, value_enum, default_value_t = ChannelProvider::Telegram)]
        provider: ChannelProvider,

        /// Bot token (TELEGRAM_BOT_TOKEN for Telegram, DISCORD_BOT_TOKEN for Discord).
        #[arg(long)]
        bot_token: Option<String>,

        /// Allowed identities (comma-separated). Empty = deny all; `*` = allow all.
        /// Telegram expects numeric sender IDs.
        #[arg(long)]
        allowed_users: Option<String>,

        /// Allowed Telegram group chat_ids (comma-separated, negative IDs e.g. -200123). Empty = no groups; `*` = allow all groups.
        #[arg(long)]
        allowed_groups: Option<String>,

        /// Allowed Discord guild IDs (comma-separated). Empty = no guild allowlist; `*` = allow all guilds.
        #[arg(long)]
        allowed_guilds: Option<String>,

        /// Admin identities (comma-separated) for privileged control commands.
        /// Empty/unset = deny privileged commands.
        /// Telegram expects numeric sender IDs.
        #[arg(long)]
        admin_users: Option<String>,

        /// Optional explicit allowlist for privileged control commands.
        /// When configured, this overrides `admin_command_rules` and `admin_users`.
        /// Empty string means deny all privileged control commands.
        #[arg(long)]
        control_command_allow_from: Option<String>,

        /// Per-command admin authorization rules for privileged control commands.
        /// Format: `<command-selector>=>user1,user2;...` (for example:
        /// `/session partition=>1001,1002;/reset,/clear=>2001;session.*=>3001`).
        #[arg(long)]
        admin_command_rules: Option<String>,

        /// Optional explicit allowlist override for supported non-privileged slash commands.
        /// When configured, this becomes the single authorization source for slash commands.
        #[arg(long)]
        slash_command_allow_from: Option<String>,

        /// Optional allowlist for `/session` and `/session status` (`json` included).
        #[arg(long)]
        slash_session_status_allow_from: Option<String>,

        /// Optional allowlist for `/session budget` (`json` included).
        #[arg(long)]
        slash_session_budget_allow_from: Option<String>,

        /// Optional allowlist for `/session memory` and `/session recall` (`json` included).
        #[arg(long)]
        slash_session_memory_allow_from: Option<String>,

        /// Optional allowlist for `/session feedback` and `/feedback` (`json` included).
        #[arg(long)]
        slash_session_feedback_allow_from: Option<String>,

        /// Optional allowlist for `/job <id>` (`json` included).
        #[arg(long)]
        slash_job_allow_from: Option<String>,

        /// Optional allowlist for `/jobs` (`json` included).
        #[arg(long)]
        slash_jobs_allow_from: Option<String>,

        /// Optional allowlist for `/bg <prompt>`.
        #[arg(long)]
        slash_bg_allow_from: Option<String>,

        /// Path to mcp.json (default: .mcp.json)
        #[arg(long, default_value = ".mcp.json")]
        mcp_config: PathBuf,

        /// Telegram transport mode (`polling` for single instance, `webhook` for multi-instance).
        #[arg(long, value_enum)]
        mode: Option<TelegramChannelMode>,

        /// Webhook listen address (used only when `--mode webhook`).
        #[arg(long)]
        webhook_bind: Option<String>,

        /// Webhook path (used only when `--mode webhook`).
        #[arg(long)]
        webhook_path: Option<String>,

        /// Telegram webhook secret token (required when `--mode webhook`; or TELEGRAM_WEBHOOK_SECRET env).
        #[arg(long)]
        webhook_secret_token: Option<String>,

        /// Discord ingress listen address (used when `--provider discord`).
        #[arg(long)]
        ingress_bind: Option<String>,

        /// Discord ingress path (used when `--provider discord`).
        #[arg(long)]
        ingress_path: Option<String>,

        /// Discord ingress secret token (or OMNI_AGENT_DISCORD_INGRESS_SECRET_TOKEN env).
        #[arg(long)]
        ingress_secret_token: Option<String>,

        /// Discord session partition (`guild_channel_user`, `channel`, `user`, `guild_user`).
        #[arg(long)]
        session_partition: Option<String>,

        /// Discord inbound queue capacity.
        #[arg(long)]
        inbound_queue_capacity: Option<usize>,

        /// Discord foreground turn timeout in seconds.
        #[arg(long)]
        turn_timeout_secs: Option<u64>,

        /// Webhook dedup backend (`valkey` recommended for multi-node, `memory` for single node).
        #[arg(long, value_enum)]
        webhook_dedup_backend: Option<WebhookDedupBackendMode>,

        /// Valkey URL for webhook dedup (or VALKEY_URL env).
        #[arg(long)]
        valkey_url: Option<String>,

        /// TTL (seconds) for webhook dedup keys.
        #[arg(long)]
        webhook_dedup_ttl_secs: Option<u64>,

        /// Key prefix for webhook dedup keys in Valkey/Redis.
        #[arg(long)]
        webhook_dedup_key_prefix: Option<String>,

        /// Verbose logs: show user messages and bot replies (also enables debug-level tracing).
        #[arg(long, short = 'v')]
        verbose: bool,
    },
}
