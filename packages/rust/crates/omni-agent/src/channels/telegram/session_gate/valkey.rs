use anyhow::{Context, Result, bail};
use redis::FromRedisValue;
use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::{Mutex, oneshot};

use crate::observability::SessionEvent;

pub(super) const DEFAULT_GATE_RETRY_INTERVAL_MS: u64 = 25;

static NEXT_LEASE_OWNER_ID: AtomicU64 = AtomicU64::new(1);

#[derive(Clone)]
pub(super) struct ValkeySessionGateBackend {
    client: redis::Client,
    key_prefix: String,
    lease_ttl_ms: u64,
    acquire_timeout: Option<Duration>,
    retry_interval: Duration,
    connection: Arc<Mutex<Option<redis::aio::MultiplexedConnection>>>,
}

pub(super) struct DistributedLeaseGuard {
    backend: Arc<ValkeySessionGateBackend>,
    lock_key: String,
    owner_token: String,
    stop_tx: Option<oneshot::Sender<()>>,
}

impl Drop for DistributedLeaseGuard {
    fn drop(&mut self) {
        if let Some(stop_tx) = self.stop_tx.take() {
            let _ = stop_tx.send(());
        }

        let Ok(handle) = tokio::runtime::Handle::try_current() else {
            return;
        };
        let backend = Arc::clone(&self.backend);
        let lock_key = self.lock_key.clone();
        let owner_token = self.owner_token.clone();
        handle.spawn(async move {
            match backend.release_lease(&lock_key, &owner_token).await {
                Ok(released) => {
                    tracing::debug!(
                        event = SessionEvent::SessionGateLeaseReleased.as_str(),
                        key = %lock_key,
                        released,
                        "valkey session gate lease release attempted"
                    );
                }
                Err(error) => {
                    tracing::warn!(
                        event = SessionEvent::SessionGateLeaseReleased.as_str(),
                        key = %lock_key,
                        error = %error,
                        "valkey session gate lease release failed"
                    );
                }
            }
        });
    }
}

impl ValkeySessionGateBackend {
    pub(super) fn new(
        valkey_url: &str,
        key_prefix: &str,
        lease_ttl_secs: u64,
        acquire_timeout_secs: Option<u64>,
    ) -> Result<Self> {
        let client = redis::Client::open(valkey_url).with_context(|| {
            format!("invalid valkey url for session gate backend: {valkey_url}")
        })?;
        Ok(Self {
            client,
            key_prefix: key_prefix.to_string(),
            lease_ttl_ms: lease_ttl_secs.saturating_mul(1000),
            acquire_timeout: acquire_timeout_secs
                .filter(|value| *value > 0)
                .map(Duration::from_secs),
            retry_interval: Duration::from_millis(DEFAULT_GATE_RETRY_INTERVAL_MS),
            connection: Arc::new(Mutex::new(None)),
        })
    }

    pub(super) async fn acquire_lease(
        self: &Arc<Self>,
        session_id: &str,
    ) -> Result<DistributedLeaseGuard> {
        let lock_key = format!("{}:lock:{}", self.key_prefix, session_id);
        let owner_token = next_lease_owner_token(session_id);
        let started = Instant::now();
        loop {
            if self.try_acquire_lease(&lock_key, &owner_token).await? {
                break;
            }

            if let Some(timeout) = self.acquire_timeout
                && started.elapsed() >= timeout
            {
                tracing::warn!(
                    event = SessionEvent::SessionGateLeaseAcquireTimeout.as_str(),
                    session_id,
                    wait_ms = started.elapsed().as_millis(),
                    timeout_ms = timeout.as_millis(),
                    "timed out waiting for distributed session gate lease"
                );
                bail!(
                    "timed out waiting {}ms for distributed session gate lease",
                    timeout.as_millis()
                );
            }
            tokio::time::sleep(self.retry_interval).await;
        }

        let wait_ms = started.elapsed().as_millis();
        tracing::debug!(
            event = SessionEvent::SessionGateLeaseAcquired.as_str(),
            session_id,
            wait_ms,
            lease_ttl_ms = self.lease_ttl_ms,
            "distributed session gate lease acquired"
        );

        let (stop_tx, stop_rx) = oneshot::channel::<()>();
        self.spawn_lease_renew_task(lock_key.clone(), owner_token.clone(), stop_rx);
        Ok(DistributedLeaseGuard {
            backend: Arc::clone(self),
            lock_key,
            owner_token,
            stop_tx: Some(stop_tx),
        })
    }

    fn spawn_lease_renew_task(
        self: &Arc<Self>,
        lock_key: String,
        owner_token: String,
        mut stop_rx: oneshot::Receiver<()>,
    ) {
        let backend = Arc::clone(self);
        let renew_interval_ms = (backend.lease_ttl_ms / 3).max(200);
        tokio::spawn(async move {
            let mut ticker = tokio::time::interval(Duration::from_millis(renew_interval_ms));
            loop {
                tokio::select! {
                    _ = &mut stop_rx => break,
                    _ = ticker.tick() => {
                        match backend.renew_lease(&lock_key, &owner_token).await {
                            Ok(true) => {
                                tracing::debug!(
                                    event = SessionEvent::SessionGateLeaseRenewed.as_str(),
                                    key = %lock_key,
                                    renew_interval_ms,
                                    "distributed session gate lease renewed"
                                );
                            }
                            Ok(false) => {
                                tracing::warn!(
                                    event = SessionEvent::SessionGateLeaseRenewalFailed.as_str(),
                                    key = %lock_key,
                                    "distributed session gate lease lost before renewal"
                                );
                                break;
                            }
                            Err(error) => {
                                tracing::warn!(
                                    event = SessionEvent::SessionGateLeaseRenewalFailed.as_str(),
                                    key = %lock_key,
                                    error = %error,
                                    "distributed session gate lease renewal failed"
                                );
                            }
                        }
                    }
                }
            }
        });
    }

    async fn try_acquire_lease(&self, lock_key: &str, owner_token: &str) -> Result<bool> {
        let acquired = self
            .run_command::<Option<String>, _>("session_gate_try_acquire", || {
                let mut cmd = redis::cmd("SET");
                cmd.arg(lock_key)
                    .arg(owner_token)
                    .arg("NX")
                    .arg("PX")
                    .arg(self.lease_ttl_ms);
                cmd
            })
            .await?;
        Ok(acquired.is_some())
    }

    async fn renew_lease(&self, lock_key: &str, owner_token: &str) -> Result<bool> {
        let script = r#"
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
  return 0
end
"#;
        let renewed = self
            .run_command::<i64, _>("session_gate_renew_lease", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(1)
                    .arg(lock_key)
                    .arg(owner_token)
                    .arg(self.lease_ttl_ms);
                cmd
            })
            .await?;
        Ok(renewed == 1)
    }

    async fn release_lease(&self, lock_key: &str, owner_token: &str) -> Result<bool> {
        let script = r#"
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
else
  return 0
end
"#;
        let released = self
            .run_command::<i64, _>("session_gate_release_lease", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script).arg(1).arg(lock_key).arg(owner_token);
                cmd
            })
            .await?;
        Ok(released == 1)
    }

    async fn run_command<T, F>(&self, operation: &'static str, build: F) -> Result<T>
    where
        T: FromRedisValue + Send,
        F: Fn() -> redis::Cmd,
    {
        let mut last_err: Option<anyhow::Error> = None;
        for attempt in 0..2 {
            let mut conn_guard = self.connection.lock().await;
            self.ensure_connection(&mut conn_guard).await?;
            let conn = conn_guard
                .as_mut()
                .ok_or_else(|| anyhow::anyhow!("session gate valkey connection unavailable"))?;
            let cmd = build();
            let result: redis::RedisResult<T> = cmd.query_async(conn).await;
            match result {
                Ok(value) => {
                    if attempt > 0 {
                        tracing::debug!(
                            event = SessionEvent::SessionValkeyCommandRetrySucceeded.as_str(),
                            operation,
                            attempt = attempt + 1,
                            "session gate valkey command succeeded after retry"
                        );
                    }
                    return Ok(value);
                }
                Err(err) => {
                    tracing::warn!(
                        event = SessionEvent::SessionValkeyCommandRetryFailed.as_str(),
                        operation,
                        attempt = attempt + 1,
                        error = %err,
                        "session gate valkey command failed; reconnecting"
                    );
                    *conn_guard = None;
                    last_err =
                        Some(anyhow::anyhow!(err).context("session gate valkey command failed"));
                    if attempt == 0 {
                        continue;
                    }
                }
            }
        }
        tracing::warn!(
            event = SessionEvent::SessionValkeyCommandRetryFailed.as_str(),
            operation,
            "session gate valkey command failed after retry"
        );
        Err(last_err
            .unwrap_or_else(|| anyhow::anyhow!("session gate valkey command failed unexpectedly")))
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
                .context("failed to open valkey connection for session gate")?,
        );
        tracing::debug!(
            event = SessionEvent::SessionValkeyConnected.as_str(),
            key_prefix = %self.key_prefix,
            "valkey session gate backend connected"
        );
        Ok(())
    }
}

fn next_lease_owner_token(session_id: &str) -> String {
    let now_ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    let seq = NEXT_LEASE_OWNER_ID.fetch_add(1, Ordering::Relaxed);
    format!("{session_id}:{}:{now_ms}:{seq}", std::process::id())
}
