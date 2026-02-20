//! In-memory session store: session_id → chat messages.

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

use anyhow::{Context, Result};

use crate::observability::SessionEvent;

use super::message::ChatMessage;
use super::redis_backend::{RedisSessionBackend, RedisSessionRuntimeSnapshot};

/// In-memory store: session_id → list of messages.
pub struct SessionStore {
    inner: Arc<RwLock<HashMap<String, Vec<ChatMessage>>>>,
    redis: Option<Arc<RedisSessionBackend>>,
}

impl SessionStore {
    fn from_redis_backend(redis: Option<Arc<RedisSessionBackend>>) -> Self {
        Self {
            inner: Arc::new(RwLock::new(HashMap::new())),
            redis,
        }
    }

    /// Create a new empty session store.
    pub fn new() -> Result<Self> {
        let redis = match RedisSessionBackend::from_env() {
            Some(Ok(backend)) => {
                tracing::info!(
                    event = SessionEvent::SessionBackendEnabled.as_str(),
                    key_prefix = %backend.key_prefix(),
                    ttl_secs = ?backend.ttl_secs(),
                    "session store backend enabled: valkey"
                );
                Some(Arc::new(backend))
            }
            Some(Err(error)) => {
                return Err(error).context("failed to initialize valkey session store");
            }
            None => None,
        };
        Ok(Self::from_redis_backend(redis))
    }

    /// Create a store with explicit Valkey backend parameters.
    pub fn new_with_redis(
        redis_url: impl Into<String>,
        key_prefix: Option<String>,
        ttl_secs: Option<u64>,
    ) -> Result<Self> {
        let backend = RedisSessionBackend::new_from_parts(redis_url.into(), key_prefix, ttl_secs)?;
        Ok(Self::from_redis_backend(Some(Arc::new(backend))))
    }

    /// Append messages for a session.
    pub async fn append(&self, session_id: &str, messages: Vec<ChatMessage>) -> Result<()> {
        if messages.is_empty() {
            return Ok(());
        }
        if let Some(ref redis) = self.redis {
            redis
                .append_messages(session_id, &messages)
                .await
                .with_context(|| {
                    format!("valkey session append failed for session_id={session_id}")
                })?;
            tracing::debug!(
                event = SessionEvent::SessionMessagesAppended.as_str(),
                session_id,
                appended_messages = messages.len(),
                backend = "valkey",
                "session messages appended"
            );
            return Ok(());
        }
        let mut g = self.inner.write().await;
        let entry = g.entry(session_id.to_string()).or_default();
        entry.extend(messages);
        tracing::debug!(
            event = SessionEvent::SessionMessagesAppended.as_str(),
            session_id,
            total_messages = entry.len(),
            backend = "memory",
            "session messages appended"
        );
        Ok(())
    }

    /// Get a copy of the message history for a session.
    pub async fn get(&self, session_id: &str) -> Result<Vec<ChatMessage>> {
        if let Some(ref redis) = self.redis {
            let messages = redis.get_messages(session_id).await.with_context(|| {
                format!("valkey session read failed for session_id={session_id}")
            })?;
            tracing::debug!(
                event = SessionEvent::SessionMessagesLoaded.as_str(),
                session_id,
                loaded_messages = messages.len(),
                backend = "valkey",
                "session messages loaded"
            );
            return Ok(messages);
        }
        let g = self.inner.read().await;
        let messages = g.get(session_id).cloned().unwrap_or_default();
        tracing::debug!(
            event = SessionEvent::SessionMessagesLoaded.as_str(),
            session_id,
            loaded_messages = messages.len(),
            backend = "memory",
            "session messages loaded"
        );
        Ok(messages)
    }

    /// Replace full history for a session atomically.
    pub async fn replace(&self, session_id: &str, messages: Vec<ChatMessage>) -> Result<()> {
        if let Some(ref redis) = self.redis {
            let replaced_count = redis
                .replace_messages(session_id, &messages)
                .await
                .with_context(|| {
                    format!("valkey session replace failed for session_id={session_id}")
                })?;
            tracing::debug!(
                event = SessionEvent::SessionMessagesReplaced.as_str(),
                session_id,
                replaced_messages = replaced_count,
                backend = "valkey",
                "session messages replaced"
            );
            return Ok(());
        }
        let mut g = self.inner.write().await;
        if messages.is_empty() {
            g.remove(session_id);
        } else {
            g.insert(session_id.to_string(), messages);
        }
        let replaced_messages = g.get(session_id).map_or(0, Vec::len);
        tracing::debug!(
            event = SessionEvent::SessionMessagesReplaced.as_str(),
            session_id,
            replaced_messages,
            backend = "memory",
            "session messages replaced"
        );
        Ok(())
    }

    /// Get message count for a session without loading the full payload.
    pub async fn len(&self, session_id: &str) -> Result<usize> {
        if let Some(ref redis) = self.redis {
            let message_count = redis.get_messages_len(session_id).await.with_context(|| {
                format!("valkey session length read failed for session_id={session_id}")
            })?;
            tracing::debug!(
                event = SessionEvent::SessionMessagesLoaded.as_str(),
                session_id,
                loaded_messages = message_count,
                backend = "valkey",
                count_only = true,
                "session message count loaded"
            );
            return Ok(message_count);
        }

        let g = self.inner.read().await;
        let message_count = g.get(session_id).map_or(0, Vec::len);
        tracing::debug!(
            event = SessionEvent::SessionMessagesLoaded.as_str(),
            session_id,
            loaded_messages = message_count,
            backend = "memory",
            count_only = true,
            "session message count loaded"
        );
        Ok(message_count)
    }

    /// Clear history for a session.
    pub async fn clear(&self, session_id: &str) -> Result<()> {
        if let Some(ref redis) = self.redis {
            redis.clear_messages(session_id).await.with_context(|| {
                format!("valkey session clear failed for session_id={session_id}")
            })?;
            tracing::debug!(
                event = SessionEvent::SessionMessagesCleared.as_str(),
                session_id,
                backend = "valkey",
                "session messages cleared"
            );
            return Ok(());
        }
        let mut g = self.inner.write().await;
        g.remove(session_id);
        tracing::debug!(
            event = SessionEvent::SessionMessagesCleared.as_str(),
            session_id,
            backend = "memory",
            "session messages cleared"
        );
        Ok(())
    }

    /// Publish a structured event into Valkey stream backend.
    ///
    /// Returns `Ok(None)` when Valkey backend is disabled.
    pub(crate) async fn publish_stream_event(
        &self,
        stream_name: &str,
        fields: Vec<(String, String)>,
    ) -> Result<Option<String>> {
        if let Some(ref redis) = self.redis {
            let event_id = redis
                .publish_stream_event(stream_name, &fields)
                .await
                .with_context(|| {
                    format!("valkey stream publish failed for stream_name={stream_name}")
                })?;
            return Ok(Some(event_id));
        }
        Ok(None)
    }

    pub(crate) fn redis_runtime_snapshot(&self) -> Option<RedisSessionRuntimeSnapshot> {
        self.redis
            .as_ref()
            .map(|backend| backend.runtime_snapshot())
    }
}
