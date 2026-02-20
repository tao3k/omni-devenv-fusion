//! Webhook idempotency store for Telegram update deduplication.

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use async_trait::async_trait;
use tokio::sync::Mutex;

use crate::observability::SessionEvent;

/// Default Redis key prefix for Telegram webhook deduplication.
pub const DEFAULT_REDIS_KEY_PREFIX: &str = "omni-agent:telegram:webhook:update";

/// Backend options for Telegram webhook update deduplication.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WebhookDedupBackend {
    /// In-process hash map with TTL.
    Memory,
    /// Redis key-value store using atomic `SET EX NX`.
    Redis {
        /// Valkey URL using Redis protocol (for example `redis://<valkey-host>:6379/0`).
        url: String,
        /// Key namespace prefix.
        key_prefix: String,
    },
}

/// Runtime config for webhook deduplication.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WebhookDedupConfig {
    /// Backend mode.
    pub backend: WebhookDedupBackend,
    /// Dedup key TTL in seconds.
    pub ttl_secs: u64,
}

impl Default for WebhookDedupConfig {
    fn default() -> Self {
        Self {
            backend: WebhookDedupBackend::Memory,
            ttl_secs: 600,
        }
    }
}

impl WebhookDedupConfig {
    /// Return a sanitized config with safe defaults.
    pub fn normalized(mut self) -> Self {
        self.ttl_secs = self.ttl_secs.max(1);
        if let WebhookDedupBackend::Redis { key_prefix, .. } = &mut self.backend
            && key_prefix.trim().is_empty()
        {
            *key_prefix = DEFAULT_REDIS_KEY_PREFIX.to_string();
        }
        self
    }

    /// Build a deduplicator from this config.
    pub fn build_store(&self) -> Result<Arc<dyn UpdateDeduplicator>> {
        let normalized = self.clone().normalized();
        match normalized.backend {
            WebhookDedupBackend::Memory => {
                tracing::info!(
                    event = SessionEvent::DedupBackendInitialized.as_str(),
                    backend = "memory",
                    ttl_secs = normalized.ttl_secs,
                    "telegram webhook dedup backend initialized"
                );
                Ok(Arc::new(MemoryUpdateDeduplicator::new(normalized.ttl_secs)))
            }
            WebhookDedupBackend::Redis { url, key_prefix } => {
                tracing::info!(
                    event = SessionEvent::DedupBackendInitialized.as_str(),
                    backend = "valkey",
                    ttl_secs = normalized.ttl_secs,
                    key_prefix = %key_prefix,
                    "telegram webhook dedup backend initialized"
                );
                Ok(Arc::new(RedisUpdateDeduplicator::new(
                    url,
                    key_prefix,
                    normalized.ttl_secs,
                )?))
            }
        }
    }

    /// Human-readable backend name for logs.
    pub fn backend_name(&self) -> &'static str {
        match self.backend {
            WebhookDedupBackend::Memory => "memory",
            WebhookDedupBackend::Redis { .. } => "valkey",
        }
    }
}

/// Abstraction for at-most-once webhook update processing.
#[async_trait]
pub trait UpdateDeduplicator: Send + Sync {
    /// Return `true` when this update ID has already been seen inside TTL.
    async fn is_duplicate(&self, update_id: i64) -> Result<bool>;
}

/// In-memory update deduplicator (single process only).
struct MemoryUpdateDeduplicator {
    ttl: Duration,
    seen: Mutex<HashMap<i64, Instant>>,
}

impl MemoryUpdateDeduplicator {
    fn new(ttl_secs: u64) -> Self {
        Self {
            ttl: Duration::from_secs(ttl_secs.max(1)),
            seen: Mutex::new(HashMap::new()),
        }
    }
}

#[async_trait]
impl UpdateDeduplicator for MemoryUpdateDeduplicator {
    async fn is_duplicate(&self, update_id: i64) -> Result<bool> {
        let now = Instant::now();
        let mut seen = self.seen.lock().await;
        seen.retain(|_, at| now.duration_since(*at) < self.ttl);
        if seen.contains_key(&update_id) {
            tracing::debug!(
                event = SessionEvent::DedupDuplicateDetected.as_str(),
                backend = "memory",
                update_id,
                tracked_ids = seen.len(),
                "telegram webhook duplicate update detected"
            );
            return Ok(true);
        }
        seen.insert(update_id, now);
        tracing::debug!(
            event = SessionEvent::DedupUpdateAccepted.as_str(),
            backend = "memory",
            update_id,
            tracked_ids = seen.len(),
            "telegram webhook update accepted"
        );
        Ok(false)
    }
}

/// Redis-backed update deduplicator (multi-node safe).
struct RedisUpdateDeduplicator {
    client: redis::Client,
    key_prefix: String,
    ttl_secs: u64,
    connection: Mutex<Option<redis::aio::MultiplexedConnection>>,
}

impl RedisUpdateDeduplicator {
    fn new(url: String, key_prefix: String, ttl_secs: u64) -> Result<Self> {
        let client = redis::Client::open(url.clone())
            .with_context(|| format!("invalid redis url for webhook dedup: {url}"))?;
        Ok(Self {
            client,
            key_prefix,
            ttl_secs: ttl_secs.max(1),
            connection: Mutex::new(None),
        })
    }

    async fn ensure_connection(
        &self,
        connection: &mut Option<redis::aio::MultiplexedConnection>,
    ) -> Result<()> {
        if connection.is_some() {
            return Ok(());
        }
        *connection = Some(
            self.client
                .get_multiplexed_async_connection()
                .await
                .context("failed to open redis connection for webhook dedup")?,
        );
        tracing::debug!(
            event = SessionEvent::DedupValkeyConnected.as_str(),
            backend = "valkey",
            key_prefix = %self.key_prefix,
            "telegram webhook dedup connected to valkey"
        );
        Ok(())
    }

    async fn run_set_nx(&self, key: &str) -> Result<Option<String>> {
        // Try once with current connection, then reconnect and retry once.
        let mut last_err: Option<anyhow::Error> = None;
        for attempt in 0..2 {
            let mut conn_guard = self.connection.lock().await;
            self.ensure_connection(&mut conn_guard).await?;
            let conn = conn_guard
                .as_mut()
                .ok_or_else(|| anyhow::anyhow!("redis connection unavailable for webhook dedup"))?;

            let result: redis::RedisResult<Option<String>> = redis::cmd("SET")
                .arg(key)
                .arg("1")
                .arg("EX")
                .arg(self.ttl_secs)
                .arg("NX")
                .query_async(conn)
                .await;
            match result {
                Ok(value) => {
                    if attempt > 0 {
                        tracing::debug!(
                            event = SessionEvent::DedupSetNxRetrySucceeded.as_str(),
                            backend = "valkey",
                            attempt = attempt + 1,
                            "telegram webhook dedup SET NX succeeded after retry"
                        );
                    }
                    return Ok(value);
                }
                Err(err) => {
                    tracing::warn!(
                        event = SessionEvent::DedupSetNxRetryFailed.as_str(),
                        backend = "valkey",
                        attempt = attempt + 1,
                        error = %err,
                        "telegram webhook dedup SET NX failed; reconnecting"
                    );
                    // Drop stale connection so next attempt uses a fresh socket.
                    *conn_guard = None;
                    last_err = Some(
                        anyhow::anyhow!(err).context("redis SET NX EX failed for webhook dedup"),
                    );
                    if attempt == 0 {
                        continue;
                    }
                }
            }
        }

        Err(last_err.unwrap_or_else(|| {
            anyhow::anyhow!("redis dedup failed after retry for unknown reason")
        }))
    }
}

#[async_trait]
impl UpdateDeduplicator for RedisUpdateDeduplicator {
    async fn is_duplicate(&self, update_id: i64) -> Result<bool> {
        let key = format!("{}:{update_id}", self.key_prefix);
        let set_result = self.run_set_nx(&key).await?;
        let duplicate = set_result.is_none();
        if duplicate {
            tracing::debug!(
                event = SessionEvent::DedupDuplicateDetected.as_str(),
                backend = "valkey",
                update_id,
                ttl_secs = self.ttl_secs,
                "telegram webhook duplicate update detected"
            );
        } else {
            tracing::debug!(
                event = SessionEvent::DedupUpdateAccepted.as_str(),
                backend = "valkey",
                update_id,
                ttl_secs = self.ttl_secs,
                "telegram webhook update accepted"
            );
        }
        tracing::debug!(
            event = SessionEvent::DedupEvaluated.as_str(),
            backend = "valkey",
            update_id,
            duplicate,
            ttl_secs = self.ttl_secs,
            "telegram webhook dedup evaluated update"
        );
        Ok(duplicate)
    }
}
