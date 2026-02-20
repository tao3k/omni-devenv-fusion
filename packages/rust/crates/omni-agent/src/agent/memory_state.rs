use anyhow::{Result, bail};
use omni_memory::{
    EpisodeStore, LocalMemoryStateStore, MemoryStateStore, StoreConfig, ValkeyMemoryStateStore,
    default_valkey_state_key,
};

use super::Agent;
use crate::config::MemoryConfig;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum PersistenceBackendMode {
    Auto,
    Local,
    Valkey,
}

pub(super) enum MemoryStateBackend {
    Local(LocalMemoryStateStore),
    Valkey(ValkeyMemoryStateStore),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) enum MemoryStateLoadStatus {
    NotConfigured,
    Loaded,
    LoadFailedContinue,
}

impl MemoryStateLoadStatus {
    pub(super) fn as_str(self) -> &'static str {
        match self {
            Self::NotConfigured => "not_configured",
            Self::Loaded => "loaded",
            Self::LoadFailedContinue => "load_failed_continue",
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct MemoryRuntimeStatusSnapshot {
    pub enabled: bool,
    pub configured_backend: Option<String>,
    pub active_backend: Option<&'static str>,
    pub strict_startup: Option<bool>,
    pub startup_load_status: &'static str,
    pub store_path: Option<String>,
    pub table_name: Option<String>,
    pub gate_promote_threshold: Option<f32>,
    pub gate_obsolete_threshold: Option<f32>,
    pub gate_promote_min_usage: Option<u32>,
    pub gate_obsolete_min_usage: Option<u32>,
    pub gate_promote_failure_rate_ceiling: Option<f32>,
    pub gate_obsolete_failure_rate_floor: Option<f32>,
    pub gate_promote_min_ttl_score: Option<f32>,
    pub gate_obsolete_max_ttl_score: Option<f32>,
    pub episodes_total: Option<usize>,
    pub q_values_total: Option<usize>,
}

impl MemoryStateBackend {
    pub(super) fn from_config(memory_cfg: &MemoryConfig) -> Result<Self> {
        let mode = resolve_mode(&memory_cfg.persistence_backend)?;
        let redis_url = non_empty_env("VALKEY_URL")
            .or_else(|| non_empty_string(memory_cfg.persistence_valkey_url.clone()));
        let strict_startup_override =
            parse_bool_env("OMNI_AGENT_MEMORY_PERSISTENCE_STRICT_STARTUP")
                .or(memory_cfg.persistence_strict_startup);
        let key_prefix = non_empty_env("OMNI_AGENT_MEMORY_VALKEY_KEY_PREFIX")
            .or_else(|| non_empty_string(Some(memory_cfg.persistence_key_prefix.clone())))
            .unwrap_or_else(|| "omni-agent:memory".to_string());

        let store_config = StoreConfig {
            path: memory_cfg.path.clone(),
            embedding_dim: memory_cfg.embedding_dim,
            table_name: memory_cfg.table_name.clone(),
        };

        match mode {
            PersistenceBackendMode::Local => Ok(Self::Local(LocalMemoryStateStore::new())),
            PersistenceBackendMode::Valkey => {
                let redis_url = redis_url.ok_or_else(|| {
                    anyhow::anyhow!(
                        "memory persistence backend=valkey requires valkey url (VALKEY_URL or session.valkey_url)"
                    )
                })?;
                let key = default_valkey_state_key(&key_prefix, &store_config);
                let strict_startup = strict_startup_override.unwrap_or(true);
                Ok(Self::Valkey(ValkeyMemoryStateStore::new(
                    redis_url,
                    key,
                    strict_startup,
                )?))
            }
            PersistenceBackendMode::Auto => {
                if let Some(redis_url) = redis_url {
                    let key = default_valkey_state_key(&key_prefix, &store_config);
                    let strict_startup = strict_startup_override.unwrap_or(true);
                    Ok(Self::Valkey(ValkeyMemoryStateStore::new(
                        redis_url,
                        key,
                        strict_startup,
                    )?))
                } else {
                    Ok(Self::Local(LocalMemoryStateStore::new()))
                }
            }
        }
    }

    fn as_store(&self) -> &dyn MemoryStateStore {
        match self {
            Self::Local(store) => store,
            Self::Valkey(store) => store,
        }
    }

    pub(super) fn backend_name(&self) -> &'static str {
        self.as_store().backend_name()
    }

    pub(super) fn strict_startup(&self) -> bool {
        self.as_store().strict_startup()
    }

    pub(super) fn load(&self, store: &EpisodeStore) -> Result<()> {
        self.as_store().load(store)
    }

    pub(super) fn save(&self, store: &EpisodeStore) -> Result<()> {
        self.as_store().save(store)
    }
}

fn resolve_mode(raw: &str) -> Result<PersistenceBackendMode> {
    match raw.trim().to_ascii_lowercase().as_str() {
        "auto" => Ok(PersistenceBackendMode::Auto),
        "local" => Ok(PersistenceBackendMode::Local),
        "valkey" => Ok(PersistenceBackendMode::Valkey),
        other => bail!("invalid memory persistence backend `{other}`; expected auto|local|valkey"),
    }
}

fn non_empty_env(name: &str) -> Option<String> {
    std::env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn non_empty_string(value: Option<String>) -> Option<String> {
    value
        .map(|raw| raw.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn parse_bool_env(name: &str) -> Option<bool> {
    let raw = std::env::var(name).ok()?;
    match raw.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => {
            tracing::warn!(
                env_var = %name,
                value = %raw,
                "invalid boolean env value"
            );
            None
        }
    }
}

impl Agent {
    pub fn inspect_memory_runtime_status(&self) -> MemoryRuntimeStatusSnapshot {
        let (episodes_total, q_values_total) = self
            .memory_store
            .as_ref()
            .map(|store| {
                let stats = store.stats();
                (Some(stats.total_episodes), Some(stats.q_table_size))
            })
            .unwrap_or((None, None));

        MemoryRuntimeStatusSnapshot {
            enabled: self.config.memory.is_some(),
            configured_backend: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.persistence_backend.clone()),
            active_backend: self
                .memory_state_backend
                .as_ref()
                .map(|backend| backend.backend_name()),
            strict_startup: self
                .memory_state_backend
                .as_ref()
                .map(|backend| backend.strict_startup()),
            startup_load_status: self.memory_state_load_status.as_str(),
            store_path: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.path.clone()),
            table_name: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.table_name.clone()),
            gate_promote_threshold: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_promote_threshold),
            gate_obsolete_threshold: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_obsolete_threshold),
            gate_promote_min_usage: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_promote_min_usage),
            gate_obsolete_min_usage: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_obsolete_min_usage),
            gate_promote_failure_rate_ceiling: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_promote_failure_rate_ceiling),
            gate_obsolete_failure_rate_floor: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_obsolete_failure_rate_floor),
            gate_promote_min_ttl_score: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_promote_min_ttl_score),
            gate_obsolete_max_ttl_score: self
                .config
                .memory
                .as_ref()
                .map(|memory_cfg| memory_cfg.gate_obsolete_max_ttl_score),
            episodes_total,
            q_values_total,
        }
    }
}
