//! Agent configuration: inference API, model, API key, MCP server list.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// One MCP server entry (e.g. SSE URL or stdio command).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct McpServerEntry {
    /// Display name for logging.
    pub name: String,
    /// For Streamable HTTP: full URL (e.g. `http://127.0.0.1:3002/sse`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub url: Option<String>,
    /// For stdio: command to spawn (e.g. `omni` with args `["mcp", "--transport", "stdio"]`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub command: Option<String>,
    /// For stdio: arguments to the command (e.g. `["mcp", "--transport", "stdio"]`).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub args: Option<Vec<String>>,
}

/// Optional memory (omni-memory) config for two-phase recall and episode storage.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryConfig {
    /// Path to the memory store (directory).
    #[serde(default = "default_memory_path")]
    pub path: String,
    /// Optional embedding client base URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_base_url: Option<String>,
    /// Optional embedding model id used by the embedding service.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub embedding_model: Option<String>,
    /// Embedding dimension for intent vectors (must match encoder).
    #[serde(default = "default_embedding_dim")]
    pub embedding_dim: usize,
    /// Table name for episodes.
    #[serde(default = "default_memory_table")]
    pub table_name: String,
    /// Phase 1 candidate count for two-phase recall.
    #[serde(default = "default_recall_k1")]
    pub recall_k1: usize,
    /// Phase 2 result count after Q-value reranking.
    #[serde(default = "default_recall_k2")]
    pub recall_k2: usize,
    /// Q-value weight in reranking (0.0 = semantic only, 1.0 = Q only).
    #[serde(default = "default_recall_lambda")]
    pub recall_lambda: f32,
    /// Persistence backend mode: auto/local/valkey.
    #[serde(default = "default_memory_persistence_backend")]
    pub persistence_backend: String,
    /// Optional Valkey URL override injected by runtime builder/tests.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub persistence_valkey_url: Option<String>,
    /// Key prefix for Valkey-backed memory state.
    #[serde(default = "default_memory_persistence_key_prefix")]
    pub persistence_key_prefix: String,
    /// Optional strict-startup override for Valkey-backed persistence.
    ///
    /// - `Some(true)`: fail startup when initial Valkey load fails.
    /// - `Some(false)`: continue startup with empty memory on load failure.
    /// - `None`: use backend defaults (strict for Valkey, relaxed for local).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub persistence_strict_startup: Option<bool>,
    /// Whether to apply post-turn recall credit updates to recalled episodes.
    #[serde(default = "default_recall_credit_enabled")]
    pub recall_credit_enabled: bool,
    /// Maximum recalled episodes to receive post-turn credit updates.
    #[serde(default = "default_recall_credit_max_candidates")]
    pub recall_credit_max_candidates: usize,
    /// Whether to apply periodic memory decay.
    #[serde(default = "default_decay_enabled")]
    pub decay_enabled: bool,
    /// Apply memory decay every N successful stored turns.
    #[serde(default = "default_decay_every_turns")]
    pub decay_every_turns: usize,
    /// Decay factor passed to memory store decay routine.
    #[serde(default = "default_decay_factor")]
    pub decay_factor: f32,
    /// Utility threshold for promote gate decision.
    #[serde(default = "default_gate_promote_threshold")]
    pub gate_promote_threshold: f32,
    /// Utility threshold for obsolete gate decision.
    #[serde(default = "default_gate_obsolete_threshold")]
    pub gate_obsolete_threshold: f32,
    /// Minimum usage count required before promote is allowed.
    #[serde(default = "default_gate_promote_min_usage")]
    pub gate_promote_min_usage: u32,
    /// Minimum usage count required before obsolete is allowed.
    #[serde(default = "default_gate_obsolete_min_usage")]
    pub gate_obsolete_min_usage: u32,
    /// Failure-rate ceiling for promote gate decision.
    #[serde(default = "default_gate_promote_failure_rate_ceiling")]
    pub gate_promote_failure_rate_ceiling: f32,
    /// Failure-rate floor for obsolete gate decision.
    #[serde(default = "default_gate_obsolete_failure_rate_floor")]
    pub gate_obsolete_failure_rate_floor: f32,
    /// Minimum TTL score for promote gate decision.
    #[serde(default = "default_gate_promote_min_ttl_score")]
    pub gate_promote_min_ttl_score: f32,
    /// Maximum TTL score for obsolete gate decision.
    #[serde(default = "default_gate_obsolete_max_ttl_score")]
    pub gate_obsolete_max_ttl_score: f32,
    /// Enable Valkey memory stream consumer (`memory.events` -> learning metrics).
    #[serde(default = "default_stream_consumer_enabled")]
    pub stream_consumer_enabled: bool,
    /// Valkey stream name to consume memory events from.
    #[serde(default = "default_stream_name")]
    pub stream_name: String,
    /// Consumer group name for memory event stream processing.
    #[serde(default = "default_stream_consumer_group")]
    pub stream_consumer_group: String,
    /// Consumer name prefix (final consumer name includes pid + timestamp suffix).
    #[serde(default = "default_stream_consumer_name_prefix")]
    pub stream_consumer_name_prefix: String,
    /// Max events read per XREADGROUP poll.
    #[serde(default = "default_stream_consumer_batch_size")]
    pub stream_consumer_batch_size: usize,
    /// Block timeout (milliseconds) for XREADGROUP polling.
    #[serde(default = "default_stream_consumer_block_ms")]
    pub stream_consumer_block_ms: u64,
}

fn default_memory_path() -> String {
    let root = std::env::var("PRJ_ROOT")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));

    let data_home = std::env::var("PRJ_DATA_HOME")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join(".data"));

    data_home
        .join("omni-agent")
        .join("memory")
        .to_string_lossy()
        .to_string()
}
fn default_embedding_dim() -> usize {
    384
}
fn default_memory_table() -> String {
    "episodes".to_string()
}
fn default_recall_k1() -> usize {
    20
}
fn default_recall_k2() -> usize {
    5
}
fn default_recall_lambda() -> f32 {
    0.3
}
fn default_memory_persistence_backend() -> String {
    "auto".to_string()
}
fn default_memory_persistence_key_prefix() -> String {
    "omni-agent:memory".to_string()
}
fn default_recall_credit_enabled() -> bool {
    true
}
fn default_recall_credit_max_candidates() -> usize {
    4
}
fn default_decay_enabled() -> bool {
    true
}
fn default_decay_every_turns() -> usize {
    24
}
fn default_decay_factor() -> f32 {
    0.985
}
fn default_gate_promote_threshold() -> f32 {
    0.78
}
fn default_gate_obsolete_threshold() -> f32 {
    0.32
}
fn default_gate_promote_min_usage() -> u32 {
    3
}
fn default_gate_obsolete_min_usage() -> u32 {
    2
}
fn default_gate_promote_failure_rate_ceiling() -> f32 {
    0.25
}
fn default_gate_obsolete_failure_rate_floor() -> f32 {
    0.70
}
fn default_gate_promote_min_ttl_score() -> f32 {
    0.50
}
fn default_gate_obsolete_max_ttl_score() -> f32 {
    0.45
}
fn default_stream_consumer_enabled() -> bool {
    true
}
fn default_stream_name() -> String {
    "memory.events".to_string()
}
fn default_stream_consumer_group() -> String {
    "omni-agent-memory".to_string()
}
fn default_stream_consumer_name_prefix() -> String {
    "agent".to_string()
}
fn default_stream_consumer_batch_size() -> usize {
    32
}
fn default_stream_consumer_block_ms() -> u64 {
    1000
}

impl Default for MemoryConfig {
    fn default() -> Self {
        Self {
            path: default_memory_path(),
            embedding_base_url: None,
            embedding_model: None,
            embedding_dim: default_embedding_dim(),
            table_name: default_memory_table(),
            recall_k1: default_recall_k1(),
            recall_k2: default_recall_k2(),
            recall_lambda: default_recall_lambda(),
            persistence_backend: default_memory_persistence_backend(),
            persistence_valkey_url: None,
            persistence_key_prefix: default_memory_persistence_key_prefix(),
            persistence_strict_startup: None,
            recall_credit_enabled: default_recall_credit_enabled(),
            recall_credit_max_candidates: default_recall_credit_max_candidates(),
            decay_enabled: default_decay_enabled(),
            decay_every_turns: default_decay_every_turns(),
            decay_factor: default_decay_factor(),
            gate_promote_threshold: default_gate_promote_threshold(),
            gate_obsolete_threshold: default_gate_obsolete_threshold(),
            gate_promote_min_usage: default_gate_promote_min_usage(),
            gate_obsolete_min_usage: default_gate_obsolete_min_usage(),
            gate_promote_failure_rate_ceiling: default_gate_promote_failure_rate_ceiling(),
            gate_obsolete_failure_rate_floor: default_gate_obsolete_failure_rate_floor(),
            gate_promote_min_ttl_score: default_gate_promote_min_ttl_score(),
            gate_obsolete_max_ttl_score: default_gate_obsolete_max_ttl_score(),
            stream_consumer_enabled: default_stream_consumer_enabled(),
            stream_name: default_stream_name(),
            stream_consumer_group: default_stream_consumer_group(),
            stream_consumer_name_prefix: default_stream_consumer_name_prefix(),
            stream_consumer_batch_size: default_stream_consumer_batch_size(),
            stream_consumer_block_ms: default_stream_consumer_block_ms(),
        }
    }
}

/// Agent config: inference API + MCP server list + optional memory.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentConfig {
    /// Chat completions endpoint (e.g. `https://api.openai.com/v1/chat/completions` or LiteLLM).
    pub inference_url: String,
    /// Model id (e.g. `gpt-4o-mini`, `claude-3-5-sonnet`).
    pub model: String,
    /// API key; if None, read from env OPENAI_API_KEY or ANTHROPIC_API_KEY depending on URL.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub api_key: Option<String>,
    /// MCP servers to connect to (tools from all are merged).
    #[serde(default)]
    pub mcp_servers: Vec<McpServerEntry>,
    /// MCP pool size for concurrent tool calls.
    #[serde(default = "default_mcp_pool_size")]
    pub mcp_pool_size: usize,
    /// MCP handshake timeout per connect attempt, in seconds.
    #[serde(default = "default_mcp_handshake_timeout_secs")]
    pub mcp_handshake_timeout_secs: u64,
    /// MCP connect retries before failing startup.
    #[serde(default = "default_mcp_connect_retries")]
    pub mcp_connect_retries: u32,
    /// Initial backoff between MCP connect retries, in milliseconds.
    #[serde(default = "default_mcp_connect_retry_backoff_ms")]
    pub mcp_connect_retry_backoff_ms: u64,
    /// MCP tool call timeout, in seconds.
    #[serde(default = "default_mcp_tool_timeout_secs")]
    pub mcp_tool_timeout_secs: u64,
    /// MCP tools/list snapshot cache TTL (milliseconds) on the Rust client side.
    #[serde(default = "default_mcp_list_tools_cache_ttl_ms")]
    pub mcp_list_tools_cache_ttl_ms: u64,
    /// Max tool-call rounds per user turn (avoid infinite loops).
    #[serde(default = "default_max_tool_rounds")]
    pub max_tool_rounds: u32,
    /// Optional omni-memory config (two-phase recall + store_episode). None = memory disabled.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub memory: Option<MemoryConfig>,
    /// If set, use omni-window (ring buffer) for session history with this max turns; context for LLM is built from window. None = use in-memory SessionStore (unbounded).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub window_max_turns: Option<usize>,
    /// When window turn count >= this, consolidate oldest segment into omni-memory. None = consolidation disabled.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub consolidation_threshold_turns: Option<usize>,
    /// Number of oldest turns to drain per consolidation (when threshold exceeded). Ignored if consolidation disabled.
    #[serde(default = "default_consolidation_take_turns")]
    pub consolidation_take_turns: usize,
    /// If true, store consolidated memory episodes in background task.
    #[serde(default = "default_consolidation_async")]
    pub consolidation_async: bool,
    /// Optional token budget for prompt context packing. None = no token-budget pruning.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub context_budget_tokens: Option<usize>,
    /// Reserved tokens in context budget to avoid packing right at hard limit.
    #[serde(default = "default_context_budget_reserve_tokens")]
    pub context_budget_reserve_tokens: usize,
    /// Strategy for deciding which context classes are retained first under tight budget.
    #[serde(default)]
    pub context_budget_strategy: ContextBudgetStrategy,
    /// Maximum number of compacted summary segments injected into prompt context.
    #[serde(default = "default_summary_max_segments")]
    pub summary_max_segments: usize,
    /// Maximum chars kept per compacted summary segment.
    #[serde(default = "default_summary_max_chars")]
    pub summary_max_chars: usize,
}

fn default_max_tool_rounds() -> u32 {
    30
}

fn default_mcp_pool_size() -> usize {
    4
}

fn default_mcp_handshake_timeout_secs() -> u64 {
    30
}

fn default_mcp_connect_retries() -> u32 {
    3
}

fn default_mcp_connect_retry_backoff_ms() -> u64 {
    1_000
}

fn default_mcp_tool_timeout_secs() -> u64 {
    180
}

fn default_mcp_list_tools_cache_ttl_ms() -> u64 {
    1_000
}

fn default_consolidation_take_turns() -> usize {
    10
}

fn default_consolidation_async() -> bool {
    true
}

fn default_context_budget_reserve_tokens() -> usize {
    512
}

fn default_summary_max_segments() -> usize {
    8
}

fn default_summary_max_chars() -> usize {
    480
}

/// Prompt context budget retention strategy under tight token constraints.
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Default)]
#[serde(rename_all = "snake_case")]
pub enum ContextBudgetStrategy {
    /// Keep recent dialogue turns ahead of compacted summary segments.
    #[default]
    RecentFirst,
    /// Keep compacted summary segments ahead of older dialogue turns.
    SummaryFirst,
}

impl ContextBudgetStrategy {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::RecentFirst => "recent_first",
            Self::SummaryFirst => "summary_first",
        }
    }
}

impl Default for AgentConfig {
    fn default() -> Self {
        Self {
            inference_url: "https://api.openai.com/v1/chat/completions".to_string(),
            model: "gpt-4o-mini".to_string(),
            api_key: None,
            mcp_servers: Vec::new(),
            mcp_pool_size: default_mcp_pool_size(),
            mcp_handshake_timeout_secs: default_mcp_handshake_timeout_secs(),
            mcp_connect_retries: default_mcp_connect_retries(),
            mcp_connect_retry_backoff_ms: default_mcp_connect_retry_backoff_ms(),
            mcp_tool_timeout_secs: default_mcp_tool_timeout_secs(),
            mcp_list_tools_cache_ttl_ms: default_mcp_list_tools_cache_ttl_ms(),
            max_tool_rounds: default_max_tool_rounds(),
            memory: None,
            window_max_turns: None,
            consolidation_threshold_turns: None,
            consolidation_take_turns: default_consolidation_take_turns(),
            consolidation_async: default_consolidation_async(),
            context_budget_tokens: None,
            context_budget_reserve_tokens: default_context_budget_reserve_tokens(),
            context_budget_strategy: ContextBudgetStrategy::default(),
            summary_max_segments: default_summary_max_segments(),
            summary_max_chars: default_summary_max_chars(),
        }
    }
}

/// Default LiteLLM proxy path (when using `litellm --port 4000`).
pub const LITELLM_DEFAULT_URL: &str = "http://127.0.0.1:4000/v1/chat/completions";

impl AgentConfig {
    /// Build config that uses a LiteLLM proxy as the inference endpoint.
    pub fn litellm(model: impl Into<String>) -> Self {
        let inference_url =
            std::env::var("LITELLM_PROXY_URL").unwrap_or_else(|_| LITELLM_DEFAULT_URL.to_string());
        let model = std::env::var("OMNI_AGENT_MODEL").unwrap_or_else(|_| model.into());
        Self {
            inference_url,
            model,
            api_key: None,
            mcp_servers: Vec::new(),
            mcp_pool_size: default_mcp_pool_size(),
            mcp_handshake_timeout_secs: default_mcp_handshake_timeout_secs(),
            mcp_connect_retries: default_mcp_connect_retries(),
            mcp_connect_retry_backoff_ms: default_mcp_connect_retry_backoff_ms(),
            mcp_tool_timeout_secs: default_mcp_tool_timeout_secs(),
            mcp_list_tools_cache_ttl_ms: default_mcp_list_tools_cache_ttl_ms(),
            max_tool_rounds: default_max_tool_rounds(),
            memory: None,
            window_max_turns: None,
            consolidation_threshold_turns: None,
            consolidation_take_turns: default_consolidation_take_turns(),
            consolidation_async: default_consolidation_async(),
            context_budget_tokens: None,
            context_budget_reserve_tokens: default_context_budget_reserve_tokens(),
            context_budget_strategy: ContextBudgetStrategy::default(),
            summary_max_segments: default_summary_max_segments(),
            summary_max_chars: default_summary_max_chars(),
        }
    }

    /// Resolve API key: config value, or env (OPENAI_API_KEY / ANTHROPIC_API_KEY).
    /// When inference goes to our own MCP server (127.0.0.1 / localhost), returns None
    /// so we do not send a key — the server holds the key and forwards to the real LLM.
    pub fn resolve_api_key(&self) -> Option<String> {
        if let Some(ref k) = self.api_key {
            return Some(k.clone());
        }
        if self.inference_url.contains("127.0.0.1") || self.inference_url.contains("localhost") {
            return None;
        }
        if self.inference_url.contains("anthropic") || self.inference_url.contains("claude") {
            return std::env::var("ANTHROPIC_API_KEY").ok();
        }
        std::env::var("OPENAI_API_KEY").ok()
    }
}
