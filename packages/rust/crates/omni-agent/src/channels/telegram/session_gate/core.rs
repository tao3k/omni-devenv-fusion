use anyhow::{Context, Result};
use std::collections::HashMap;
use std::sync::Arc;
use std::sync::Mutex as StdMutex;
use std::sync::atomic::Ordering;

use crate::observability::SessionEvent;

use super::config::{SessionGateBackendMode, SessionGateRuntimeConfig};
use super::types::{
    SessionGate, SessionGateBackend, SessionGateEntry, SessionGuard, SessionPermit,
};
use super::valkey::ValkeySessionGateBackend;

impl Default for SessionGate {
    fn default() -> Self {
        Self {
            inner: Arc::new(StdMutex::new(HashMap::new())),
            backend: SessionGateBackend::Memory,
        }
    }
}

impl SessionGate {
    pub fn from_env() -> Result<Self> {
        Self::from_runtime_config(SessionGateRuntimeConfig::from_env()?)
    }

    #[doc(hidden)]
    pub fn new_with_valkey_for_test(
        valkey_url: impl Into<String>,
        key_prefix: impl Into<String>,
        lease_ttl_secs: u64,
        acquire_timeout_secs: Option<u64>,
    ) -> Result<Self> {
        let config = SessionGateRuntimeConfig {
            backend_mode: SessionGateBackendMode::Valkey,
            valkey_url: Some(valkey_url.into()),
            key_prefix: key_prefix.into(),
            lease_ttl_secs,
            acquire_timeout_secs,
        };
        Self::from_runtime_config(config)
    }

    pub fn backend_name(&self) -> &'static str {
        match self.backend {
            SessionGateBackend::Memory => "memory",
            SessionGateBackend::Valkey(_) => "valkey",
        }
    }

    pub async fn acquire(&self, session_id: &str) -> Result<SessionGuard> {
        let entry = {
            let mut guard = self
                .inner
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            guard
                .entry(session_id.to_string())
                .or_insert_with(|| Arc::new(SessionGateEntry::default()))
                .clone()
        };

        entry.permits.fetch_add(1, Ordering::AcqRel);
        let lock_guard = entry.lock.clone().lock_owned().await;
        let distributed_lease = match &self.backend {
            SessionGateBackend::Memory => None,
            SessionGateBackend::Valkey(backend) => {
                Some(backend.acquire_lease(session_id).await.with_context(|| {
                    format!(
                        "failed to acquire distributed session gate lease for session={session_id}"
                    )
                })?)
            }
        };
        Ok(SessionGuard {
            _distributed_lease: distributed_lease,
            _lock_guard: lock_guard,
            _permit: SessionPermit {
                session_id: session_id.to_string(),
                inner: Arc::clone(&self.inner),
                entry,
            },
        })
    }

    #[doc(hidden)]
    pub fn active_sessions(&self) -> usize {
        self.inner
            .lock()
            .unwrap_or_else(std::sync::PoisonError::into_inner)
            .len()
    }

    fn from_runtime_config(config: SessionGateRuntimeConfig) -> Result<Self> {
        let mut gate = Self::default();
        let resolved_mode = if config.backend_mode == SessionGateBackendMode::Auto {
            if config.valkey_url.is_some() {
                SessionGateBackendMode::Valkey
            } else {
                SessionGateBackendMode::Memory
            }
        } else {
            config.backend_mode
        };

        match resolved_mode {
            SessionGateBackendMode::Memory | SessionGateBackendMode::Auto => {
                tracing::info!(
                    event = SessionEvent::SessionGateBackendInitialized.as_str(),
                    backend = "memory",
                    "session gate backend initialized"
                );
            }
            SessionGateBackendMode::Valkey => {
                let valkey_url = config.valkey_url.as_deref().ok_or_else(|| {
                    anyhow::anyhow!(
                        "telegram session gate backend=valkey requires valkey url (VALKEY_URL or session.valkey_url)"
                    )
                })?;
                let backend = ValkeySessionGateBackend::new(
                    valkey_url,
                    &config.key_prefix,
                    config.lease_ttl_secs,
                    config.acquire_timeout_secs,
                )?;
                tracing::info!(
                    event = SessionEvent::SessionGateBackendInitialized.as_str(),
                    backend = "valkey",
                    key_prefix = %config.key_prefix,
                    lease_ttl_secs = config.lease_ttl_secs,
                    acquire_timeout_secs = ?config.acquire_timeout_secs,
                    "session gate backend initialized"
                );
                gate.backend = SessionGateBackend::Valkey(Arc::new(backend));
            }
        }
        Ok(gate)
    }
}
