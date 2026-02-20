//! Runtime settings loader for omni-agent.
//!
//! Loads and merges:
//! - System defaults: `<PRJ_ROOT>/packages/conf/settings.yaml`
//! - User overrides:  `<PRJ_CONFIG_HOME>/omni-dev-fusion/settings.yaml`
//!
//! Merge precedence is user over system.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use serde::Deserialize;

const DEFAULT_SYSTEM_SETTINGS_RELATIVE_PATH: &str = "packages/conf/settings.yaml";
const DEFAULT_USER_SETTINGS_RELATIVE_PATH: &str = "omni-dev-fusion/settings.yaml";
const DEFAULT_CONFIG_HOME_RELATIVE_PATH: &str = ".config";
static CONFIG_HOME_OVERRIDE: OnceLock<PathBuf> = OnceLock::new();

#[derive(Debug, Clone, Default, Deserialize)]
pub struct RuntimeSettings {
    #[serde(default)]
    pub mcp: McpSettings,
    #[serde(default)]
    pub telegram: TelegramSettings,
    #[serde(default)]
    pub discord: DiscordSettings,
    #[serde(default)]
    pub session: SessionSettings,
    #[serde(default)]
    pub embedding: EmbeddingSettings,
    #[serde(default)]
    pub memory: MemorySettings,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct TelegramSettings {
    pub allowed_users: Option<String>,
    pub allowed_groups: Option<String>,
    pub session_admin_persist: Option<bool>,
    pub group_policy: Option<String>,
    pub group_allow_from: Option<String>,
    pub require_mention: Option<bool>,
    pub groups: Option<HashMap<String, TelegramGroupSettings>>,
    pub admin_users: Option<String>,
    pub control_command_allow_from: Option<String>,
    pub admin_command_rules: Option<String>,
    pub slash_command_allow_from: Option<String>,
    pub slash_session_status_allow_from: Option<String>,
    pub slash_session_budget_allow_from: Option<String>,
    pub slash_session_memory_allow_from: Option<String>,
    pub slash_session_feedback_allow_from: Option<String>,
    pub slash_job_allow_from: Option<String>,
    pub slash_jobs_allow_from: Option<String>,
    pub slash_bg_allow_from: Option<String>,
    pub mode: Option<String>,
    pub webhook_bind: Option<String>,
    pub webhook_path: Option<String>,
    pub webhook_dedup_backend: Option<String>,
    pub webhook_dedup_ttl_secs: Option<u64>,
    pub webhook_dedup_key_prefix: Option<String>,
    pub max_tool_rounds: Option<u32>,
    pub session_partition: Option<String>,
    pub inbound_queue_capacity: Option<usize>,
    pub foreground_queue_capacity: Option<usize>,
    pub foreground_max_in_flight_messages: Option<usize>,
    pub foreground_turn_timeout_secs: Option<u64>,
    pub foreground_session_gate_backend: Option<String>,
    pub foreground_session_gate_key_prefix: Option<String>,
    pub foreground_session_gate_lease_ttl_secs: Option<u64>,
    pub foreground_session_gate_acquire_timeout_secs: Option<u64>,
    pub send_rate_limit_gate_key_prefix: Option<String>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct TelegramGroupSettings {
    pub enabled: Option<bool>,
    pub group_policy: Option<String>,
    pub allow_from: Option<String>,
    pub admin_users: Option<String>,
    pub require_mention: Option<bool>,
    pub topics: Option<HashMap<String, TelegramTopicSettings>>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct TelegramTopicSettings {
    pub enabled: Option<bool>,
    pub group_policy: Option<String>,
    pub allow_from: Option<String>,
    pub admin_users: Option<String>,
    pub require_mention: Option<bool>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct DiscordSettings {
    pub allowed_users: Option<String>,
    pub allowed_guilds: Option<String>,
    pub admin_users: Option<String>,
    pub control_command_allow_from: Option<String>,
    pub admin_command_rules: Option<String>,
    pub slash_command_allow_from: Option<String>,
    pub slash_session_status_allow_from: Option<String>,
    pub slash_session_budget_allow_from: Option<String>,
    pub slash_session_memory_allow_from: Option<String>,
    pub slash_session_feedback_allow_from: Option<String>,
    pub slash_job_allow_from: Option<String>,
    pub slash_jobs_allow_from: Option<String>,
    pub slash_bg_allow_from: Option<String>,
    pub ingress_bind: Option<String>,
    pub ingress_path: Option<String>,
    pub ingress_secret_token: Option<String>,
    pub session_partition: Option<String>,
    pub inbound_queue_capacity: Option<usize>,
    pub turn_timeout_secs: Option<u64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct McpSettings {
    pub agent_pool_size: Option<usize>,
    pub agent_handshake_timeout_secs: Option<u64>,
    pub agent_connect_retries: Option<u32>,
    pub agent_connect_retry_backoff_ms: Option<u64>,
    pub agent_tool_timeout_secs: Option<u64>,
    pub agent_list_tools_cache_ttl_ms: Option<u64>,
    pub agent_discover_cache_enabled: Option<bool>,
    pub agent_discover_cache_key_prefix: Option<String>,
    pub agent_discover_cache_ttl_secs: Option<u64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct SessionSettings {
    pub window_max_turns: Option<usize>,
    pub consolidation_threshold_turns: Option<usize>,
    pub consolidation_take_turns: Option<usize>,
    pub consolidation_async: Option<bool>,
    pub context_budget_tokens: Option<usize>,
    pub context_budget_reserve_tokens: Option<usize>,
    pub context_budget_strategy: Option<String>,
    pub summary_max_segments: Option<usize>,
    pub summary_max_chars: Option<usize>,
    pub valkey_url: Option<String>,
    pub redis_prefix: Option<String>,
    pub ttl_secs: Option<u64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct MemorySettings {
    pub path: Option<String>,
    pub persistence_backend: Option<String>,
    pub persistence_key_prefix: Option<String>,
    pub persistence_strict_startup: Option<bool>,
    pub recall_credit_enabled: Option<bool>,
    pub recall_credit_max_candidates: Option<usize>,
    pub decay_enabled: Option<bool>,
    pub decay_every_turns: Option<usize>,
    pub decay_factor: Option<f32>,
    pub gate_promote_threshold: Option<f32>,
    pub gate_obsolete_threshold: Option<f32>,
    pub gate_promote_min_usage: Option<u32>,
    pub gate_obsolete_min_usage: Option<u32>,
    pub gate_promote_failure_rate_ceiling: Option<f32>,
    pub gate_obsolete_failure_rate_floor: Option<f32>,
    pub gate_promote_min_ttl_score: Option<f32>,
    pub gate_obsolete_max_ttl_score: Option<f32>,
    pub stream_consumer_enabled: Option<bool>,
    pub stream_name: Option<String>,
    pub stream_consumer_group: Option<String>,
    pub stream_consumer_name_prefix: Option<String>,
    pub stream_consumer_batch_size: Option<usize>,
    pub stream_consumer_block_ms: Option<u64>,
}

#[derive(Debug, Clone, Default, Deserialize)]
pub struct EmbeddingSettings {
    pub model: Option<String>,
    pub litellm_model: Option<String>,
    pub dimension: Option<usize>,
    pub client_url: Option<String>,
}

impl RuntimeSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            mcp: self.mcp.merge(overlay.mcp),
            telegram: self.telegram.merge(overlay.telegram),
            discord: self.discord.merge(overlay.discord),
            session: self.session.merge(overlay.session),
            embedding: self.embedding.merge(overlay.embedding),
            memory: self.memory.merge(overlay.memory),
        }
    }
}

impl McpSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            agent_pool_size: overlay.agent_pool_size.or(self.agent_pool_size),
            agent_handshake_timeout_secs: overlay
                .agent_handshake_timeout_secs
                .or(self.agent_handshake_timeout_secs),
            agent_connect_retries: overlay.agent_connect_retries.or(self.agent_connect_retries),
            agent_connect_retry_backoff_ms: overlay
                .agent_connect_retry_backoff_ms
                .or(self.agent_connect_retry_backoff_ms),
            agent_tool_timeout_secs: overlay
                .agent_tool_timeout_secs
                .or(self.agent_tool_timeout_secs),
            agent_list_tools_cache_ttl_ms: overlay
                .agent_list_tools_cache_ttl_ms
                .or(self.agent_list_tools_cache_ttl_ms),
            agent_discover_cache_enabled: overlay
                .agent_discover_cache_enabled
                .or(self.agent_discover_cache_enabled),
            agent_discover_cache_key_prefix: overlay
                .agent_discover_cache_key_prefix
                .or(self.agent_discover_cache_key_prefix),
            agent_discover_cache_ttl_secs: overlay
                .agent_discover_cache_ttl_secs
                .or(self.agent_discover_cache_ttl_secs),
        }
    }
}

impl TelegramSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            allowed_users: overlay.allowed_users.or(self.allowed_users),
            allowed_groups: overlay.allowed_groups.or(self.allowed_groups),
            session_admin_persist: overlay.session_admin_persist.or(self.session_admin_persist),
            group_policy: overlay.group_policy.or(self.group_policy),
            group_allow_from: overlay.group_allow_from.or(self.group_allow_from),
            require_mention: overlay.require_mention.or(self.require_mention),
            groups: merge_telegram_groups(self.groups, overlay.groups),
            admin_users: overlay.admin_users.or(self.admin_users),
            control_command_allow_from: overlay
                .control_command_allow_from
                .or(self.control_command_allow_from),
            admin_command_rules: overlay.admin_command_rules.or(self.admin_command_rules),
            slash_command_allow_from: overlay
                .slash_command_allow_from
                .or(self.slash_command_allow_from),
            slash_session_status_allow_from: overlay
                .slash_session_status_allow_from
                .or(self.slash_session_status_allow_from),
            slash_session_budget_allow_from: overlay
                .slash_session_budget_allow_from
                .or(self.slash_session_budget_allow_from),
            slash_session_memory_allow_from: overlay
                .slash_session_memory_allow_from
                .or(self.slash_session_memory_allow_from),
            slash_session_feedback_allow_from: overlay
                .slash_session_feedback_allow_from
                .or(self.slash_session_feedback_allow_from),
            slash_job_allow_from: overlay.slash_job_allow_from.or(self.slash_job_allow_from),
            slash_jobs_allow_from: overlay.slash_jobs_allow_from.or(self.slash_jobs_allow_from),
            slash_bg_allow_from: overlay.slash_bg_allow_from.or(self.slash_bg_allow_from),
            mode: overlay.mode.or(self.mode),
            webhook_bind: overlay.webhook_bind.or(self.webhook_bind),
            webhook_path: overlay.webhook_path.or(self.webhook_path),
            webhook_dedup_backend: overlay.webhook_dedup_backend.or(self.webhook_dedup_backend),
            webhook_dedup_ttl_secs: overlay
                .webhook_dedup_ttl_secs
                .or(self.webhook_dedup_ttl_secs),
            webhook_dedup_key_prefix: overlay
                .webhook_dedup_key_prefix
                .or(self.webhook_dedup_key_prefix),
            max_tool_rounds: overlay.max_tool_rounds.or(self.max_tool_rounds),
            session_partition: overlay.session_partition.or(self.session_partition),
            inbound_queue_capacity: overlay
                .inbound_queue_capacity
                .or(self.inbound_queue_capacity),
            foreground_queue_capacity: overlay
                .foreground_queue_capacity
                .or(self.foreground_queue_capacity),
            foreground_max_in_flight_messages: overlay
                .foreground_max_in_flight_messages
                .or(self.foreground_max_in_flight_messages),
            foreground_turn_timeout_secs: overlay
                .foreground_turn_timeout_secs
                .or(self.foreground_turn_timeout_secs),
            foreground_session_gate_backend: overlay
                .foreground_session_gate_backend
                .or(self.foreground_session_gate_backend),
            foreground_session_gate_key_prefix: overlay
                .foreground_session_gate_key_prefix
                .or(self.foreground_session_gate_key_prefix),
            foreground_session_gate_lease_ttl_secs: overlay
                .foreground_session_gate_lease_ttl_secs
                .or(self.foreground_session_gate_lease_ttl_secs),
            foreground_session_gate_acquire_timeout_secs: overlay
                .foreground_session_gate_acquire_timeout_secs
                .or(self.foreground_session_gate_acquire_timeout_secs),
            send_rate_limit_gate_key_prefix: overlay
                .send_rate_limit_gate_key_prefix
                .or(self.send_rate_limit_gate_key_prefix),
        }
    }
}

impl TelegramGroupSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            enabled: overlay.enabled.or(self.enabled),
            group_policy: overlay.group_policy.or(self.group_policy),
            allow_from: overlay.allow_from.or(self.allow_from),
            admin_users: overlay.admin_users.or(self.admin_users),
            require_mention: overlay.require_mention.or(self.require_mention),
            topics: merge_telegram_topics(self.topics, overlay.topics),
        }
    }
}

impl TelegramTopicSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            enabled: overlay.enabled.or(self.enabled),
            group_policy: overlay.group_policy.or(self.group_policy),
            allow_from: overlay.allow_from.or(self.allow_from),
            admin_users: overlay.admin_users.or(self.admin_users),
            require_mention: overlay.require_mention.or(self.require_mention),
        }
    }
}

fn merge_telegram_groups(
    base: Option<HashMap<String, TelegramGroupSettings>>,
    overlay: Option<HashMap<String, TelegramGroupSettings>>,
) -> Option<HashMap<String, TelegramGroupSettings>> {
    match (base, overlay) {
        (None, None) => None,
        (Some(groups), None) => Some(groups),
        (None, Some(groups)) => Some(groups),
        (Some(mut groups), Some(overlay_groups)) => {
            for (group_id, override_group) in overlay_groups {
                groups
                    .entry(group_id)
                    .and_modify(|existing| {
                        *existing = existing.clone().merge(override_group.clone())
                    })
                    .or_insert(override_group);
            }
            Some(groups)
        }
    }
}

fn merge_telegram_topics(
    base: Option<HashMap<String, TelegramTopicSettings>>,
    overlay: Option<HashMap<String, TelegramTopicSettings>>,
) -> Option<HashMap<String, TelegramTopicSettings>> {
    match (base, overlay) {
        (None, None) => None,
        (Some(topics), None) => Some(topics),
        (None, Some(topics)) => Some(topics),
        (Some(mut topics), Some(overlay_topics)) => {
            for (topic_id, override_topic) in overlay_topics {
                topics
                    .entry(topic_id)
                    .and_modify(|existing| {
                        *existing = existing.clone().merge(override_topic.clone())
                    })
                    .or_insert(override_topic);
            }
            Some(topics)
        }
    }
}

impl SessionSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            window_max_turns: overlay.window_max_turns.or(self.window_max_turns),
            consolidation_threshold_turns: overlay
                .consolidation_threshold_turns
                .or(self.consolidation_threshold_turns),
            consolidation_take_turns: overlay
                .consolidation_take_turns
                .or(self.consolidation_take_turns),
            consolidation_async: overlay.consolidation_async.or(self.consolidation_async),
            context_budget_tokens: overlay.context_budget_tokens.or(self.context_budget_tokens),
            context_budget_reserve_tokens: overlay
                .context_budget_reserve_tokens
                .or(self.context_budget_reserve_tokens),
            context_budget_strategy: overlay
                .context_budget_strategy
                .or(self.context_budget_strategy),
            summary_max_segments: overlay.summary_max_segments.or(self.summary_max_segments),
            summary_max_chars: overlay.summary_max_chars.or(self.summary_max_chars),
            valkey_url: overlay.valkey_url.or(self.valkey_url),
            redis_prefix: overlay.redis_prefix.or(self.redis_prefix),
            ttl_secs: overlay.ttl_secs.or(self.ttl_secs),
        }
    }
}

impl DiscordSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            allowed_users: overlay.allowed_users.or(self.allowed_users),
            allowed_guilds: overlay.allowed_guilds.or(self.allowed_guilds),
            admin_users: overlay.admin_users.or(self.admin_users),
            control_command_allow_from: overlay
                .control_command_allow_from
                .or(self.control_command_allow_from),
            admin_command_rules: overlay.admin_command_rules.or(self.admin_command_rules),
            slash_command_allow_from: overlay
                .slash_command_allow_from
                .or(self.slash_command_allow_from),
            slash_session_status_allow_from: overlay
                .slash_session_status_allow_from
                .or(self.slash_session_status_allow_from),
            slash_session_budget_allow_from: overlay
                .slash_session_budget_allow_from
                .or(self.slash_session_budget_allow_from),
            slash_session_memory_allow_from: overlay
                .slash_session_memory_allow_from
                .or(self.slash_session_memory_allow_from),
            slash_session_feedback_allow_from: overlay
                .slash_session_feedback_allow_from
                .or(self.slash_session_feedback_allow_from),
            slash_job_allow_from: overlay.slash_job_allow_from.or(self.slash_job_allow_from),
            slash_jobs_allow_from: overlay.slash_jobs_allow_from.or(self.slash_jobs_allow_from),
            slash_bg_allow_from: overlay.slash_bg_allow_from.or(self.slash_bg_allow_from),
            ingress_bind: overlay.ingress_bind.or(self.ingress_bind),
            ingress_path: overlay.ingress_path.or(self.ingress_path),
            ingress_secret_token: overlay.ingress_secret_token.or(self.ingress_secret_token),
            session_partition: overlay.session_partition.or(self.session_partition),
            inbound_queue_capacity: overlay
                .inbound_queue_capacity
                .or(self.inbound_queue_capacity),
            turn_timeout_secs: overlay.turn_timeout_secs.or(self.turn_timeout_secs),
        }
    }
}

impl MemorySettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            path: overlay.path.or(self.path),
            persistence_backend: overlay.persistence_backend.or(self.persistence_backend),
            persistence_key_prefix: overlay
                .persistence_key_prefix
                .or(self.persistence_key_prefix),
            persistence_strict_startup: overlay
                .persistence_strict_startup
                .or(self.persistence_strict_startup),
            recall_credit_enabled: overlay.recall_credit_enabled.or(self.recall_credit_enabled),
            recall_credit_max_candidates: overlay
                .recall_credit_max_candidates
                .or(self.recall_credit_max_candidates),
            decay_enabled: overlay.decay_enabled.or(self.decay_enabled),
            decay_every_turns: overlay.decay_every_turns.or(self.decay_every_turns),
            decay_factor: overlay.decay_factor.or(self.decay_factor),
            gate_promote_threshold: overlay
                .gate_promote_threshold
                .or(self.gate_promote_threshold),
            gate_obsolete_threshold: overlay
                .gate_obsolete_threshold
                .or(self.gate_obsolete_threshold),
            gate_promote_min_usage: overlay
                .gate_promote_min_usage
                .or(self.gate_promote_min_usage),
            gate_obsolete_min_usage: overlay
                .gate_obsolete_min_usage
                .or(self.gate_obsolete_min_usage),
            gate_promote_failure_rate_ceiling: overlay
                .gate_promote_failure_rate_ceiling
                .or(self.gate_promote_failure_rate_ceiling),
            gate_obsolete_failure_rate_floor: overlay
                .gate_obsolete_failure_rate_floor
                .or(self.gate_obsolete_failure_rate_floor),
            gate_promote_min_ttl_score: overlay
                .gate_promote_min_ttl_score
                .or(self.gate_promote_min_ttl_score),
            gate_obsolete_max_ttl_score: overlay
                .gate_obsolete_max_ttl_score
                .or(self.gate_obsolete_max_ttl_score),
            stream_consumer_enabled: overlay
                .stream_consumer_enabled
                .or(self.stream_consumer_enabled),
            stream_name: overlay.stream_name.or(self.stream_name),
            stream_consumer_group: overlay.stream_consumer_group.or(self.stream_consumer_group),
            stream_consumer_name_prefix: overlay
                .stream_consumer_name_prefix
                .or(self.stream_consumer_name_prefix),
            stream_consumer_batch_size: overlay
                .stream_consumer_batch_size
                .or(self.stream_consumer_batch_size),
            stream_consumer_block_ms: overlay
                .stream_consumer_block_ms
                .or(self.stream_consumer_block_ms),
        }
    }
}

impl EmbeddingSettings {
    fn merge(self, overlay: Self) -> Self {
        Self {
            model: overlay.model.or(self.model),
            litellm_model: overlay.litellm_model.or(self.litellm_model),
            dimension: overlay.dimension.or(self.dimension),
            client_url: overlay.client_url.or(self.client_url),
        }
    }
}

/// Load merged runtime settings (user overrides system).
pub fn load_runtime_settings() -> RuntimeSettings {
    let (system_path, user_path) = runtime_settings_paths();
    load_runtime_settings_from_paths(&system_path, &user_path)
}

#[doc(hidden)]
pub fn runtime_settings_paths() -> (PathBuf, PathBuf) {
    let root = project_root();
    let system_path = root.join(DEFAULT_SYSTEM_SETTINGS_RELATIVE_PATH);
    let user_path = resolve_config_home(&root).join(DEFAULT_USER_SETTINGS_RELATIVE_PATH);
    (system_path, user_path)
}

#[doc(hidden)]
pub fn load_runtime_settings_from_paths(system: &Path, user: &Path) -> RuntimeSettings {
    load_one(system).merge(load_one(user))
}

fn load_one(path: &Path) -> RuntimeSettings {
    if !path.exists() {
        return RuntimeSettings::default();
    }
    let raw = match std::fs::read_to_string(path) {
        Ok(raw) => raw,
        Err(error) => {
            tracing::warn!(
                path = %path.display(),
                error = %error,
                "failed to read settings file; ignoring"
            );
            return RuntimeSettings::default();
        }
    };
    match serde_yaml::from_str::<RuntimeSettings>(&raw) {
        Ok(value) => value,
        Err(error) => {
            tracing::warn!(
                path = %path.display(),
                error = %error,
                "failed to parse settings yaml; ignoring file"
            );
            RuntimeSettings::default()
        }
    }
}

fn project_root() -> PathBuf {
    std::env::var("PRJ_ROOT")
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")))
}

/// Set config-home override (used by CLI `--conf`).
///
/// The path can be absolute, or relative to `PRJ_ROOT`/cwd.
pub fn set_config_home_override(path: impl Into<PathBuf>) {
    let path = path.into();
    if path.as_os_str().is_empty() {
        return;
    }
    if CONFIG_HOME_OVERRIDE.set(path.clone()).is_err()
        && let Some(current) = CONFIG_HOME_OVERRIDE.get()
        && current != &path
    {
        tracing::warn!(
            current = %current.display(),
            ignored = %path.display(),
            "config home override already set; ignoring subsequent value"
        );
    }
}

fn resolve_config_home(project_root: &Path) -> PathBuf {
    if let Some(path) = CONFIG_HOME_OVERRIDE.get() {
        return absolutize(project_root, path.clone());
    }

    let configured = std::env::var("PRJ_CONFIG_HOME")
        .ok()
        .map(|v| v.trim().to_string())
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| DEFAULT_CONFIG_HOME_RELATIVE_PATH.to_string());
    absolutize(project_root, PathBuf::from(configured))
}

fn absolutize(project_root: &Path, path: PathBuf) -> PathBuf {
    if path.is_absolute() {
        path
    } else {
        project_root.join(path)
    }
}
