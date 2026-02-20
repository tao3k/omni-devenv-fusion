//! Memory state persistence backends.

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

use anyhow::Result;

use crate::store::{EpisodeStore, StoreConfig};

/// Persistence abstraction for memory state (episodes + Q-values).
pub trait MemoryStateStore: Send + Sync {
    /// Backend identifier for logs and metrics.
    fn backend_name(&self) -> &'static str;

    /// Whether startup should fail if loading state fails.
    fn strict_startup(&self) -> bool {
        false
    }

    /// Load state into `store`.
    fn load(&self, store: &EpisodeStore) -> Result<()>;

    /// Save state from `store`.
    fn save(&self, store: &EpisodeStore) -> Result<()>;
}

/// Local JSON-backed memory state store.
#[derive(Debug, Default, Clone, Copy)]
pub struct LocalMemoryStateStore;

impl LocalMemoryStateStore {
    /// Create a local filesystem-backed memory state store.
    #[must_use]
    pub fn new() -> Self {
        Self
    }
}

impl MemoryStateStore for LocalMemoryStateStore {
    fn backend_name(&self) -> &'static str {
        "local"
    }

    fn load(&self, store: &EpisodeStore) -> Result<()> {
        store.load_state()
    }

    fn save(&self, store: &EpisodeStore) -> Result<()> {
        store.save_state()
    }
}

/// Build a deterministic Valkey key from prefix + store identity.
#[must_use]
pub fn default_valkey_state_key(prefix: &str, store_config: &StoreConfig) -> String {
    let mut hasher = DefaultHasher::new();
    store_config.path.hash(&mut hasher);
    let path_fingerprint = hasher.finish();
    format!("{prefix}:{path_fingerprint}:{}", store_config.table_name)
}

#[cfg(feature = "valkey")]
mod valkey {
    use anyhow::{Context, Result};
    use redis::Commands;

    use super::{EpisodeStore, MemoryStateStore};
    use crate::MemoryStateSnapshot;

    /// Valkey-backed memory state store (single snapshot payload).
    pub struct ValkeyMemoryStateStore {
        client: redis::Client,
        key: String,
        strict_startup: bool,
    }

    impl ValkeyMemoryStateStore {
        /// Create a Valkey memory state store.
        pub fn new(
            redis_url: impl AsRef<str>,
            key: impl Into<String>,
            strict_startup: bool,
        ) -> Result<Self> {
            let redis_url = redis_url.as_ref();
            let client = redis::Client::open(redis_url).with_context(|| {
                format!("invalid redis url for memory persistence: {redis_url}")
            })?;
            Ok(Self {
                client,
                key: key.into(),
                strict_startup,
            })
        }
    }

    impl MemoryStateStore for ValkeyMemoryStateStore {
        fn backend_name(&self) -> &'static str {
            "valkey"
        }

        fn strict_startup(&self) -> bool {
            self.strict_startup
        }

        fn load(&self, store: &EpisodeStore) -> Result<()> {
            let mut connection = self
                .client
                .get_connection()
                .context("failed to open valkey connection for memory load")?;
            let payload: Option<String> = connection
                .get(&self.key)
                .context("failed to read memory state from valkey")?;
            let Some(payload) = payload else {
                return Ok(());
            };
            let snapshot: MemoryStateSnapshot = serde_json::from_str(&payload)
                .context("failed to decode valkey memory snapshot")?;
            store.restore_snapshot(snapshot);
            Ok(())
        }

        fn save(&self, store: &EpisodeStore) -> Result<()> {
            let snapshot = store.snapshot();
            let payload = serde_json::to_string(&snapshot)
                .context("failed to encode memory state snapshot for valkey")?;
            let mut connection = self
                .client
                .get_connection()
                .context("failed to open valkey connection for memory save")?;
            connection
                .set::<_, _, ()>(&self.key, payload)
                .context("failed to write memory state snapshot to valkey")?;
            Ok(())
        }
    }
}

#[cfg(feature = "valkey")]
pub use valkey::ValkeyMemoryStateStore;
