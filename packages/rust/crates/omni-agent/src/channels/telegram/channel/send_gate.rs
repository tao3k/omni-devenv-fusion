use anyhow::{Context, Result, bail};
use redis::FromRedisValue;
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;

use crate::config::load_runtime_settings;

const TELEGRAM_SEND_GATE_KEY_PREFIX_ENV: &str =
    "OMNI_AGENT_TELEGRAM_SEND_RATE_LIMIT_GATE_KEY_PREFIX";
const DEFAULT_SEND_GATE_KEY_PREFIX: &str = "omni-agent:telegram:send-gate";

#[derive(Debug, Default)]
pub(super) struct TelegramSendRateLimitGateState {
    pub(super) until: Option<Instant>,
    pub(super) spread_slots_issued: u32,
}

#[derive(Clone)]
pub(super) enum TelegramSendRateLimitBackend {
    Memory,
    Valkey(Arc<ValkeyTelegramSendRateLimitBackend>),
}

#[derive(Debug, Clone)]
struct TelegramSendRateLimitRuntimeConfig {
    valkey_url: Option<String>,
    key_prefix: String,
}

#[derive(Clone)]
pub(super) struct ValkeyTelegramSendRateLimitBackend {
    client: redis::Client,
    rate_key: String,
    spread_key: String,
    connection: Arc<Mutex<Option<redis::aio::MultiplexedConnection>>>,
}

impl TelegramSendRateLimitBackend {
    pub(super) fn from_env() -> Self {
        let runtime_config = match TelegramSendRateLimitRuntimeConfig::from_env() {
            Ok(config) => config,
            Err(error) => {
                tracing::warn!(
                    event = "telegram.send_gate.backend.init_failed",
                    error = %error,
                    "failed to resolve telegram send gate runtime settings; falling back to memory backend"
                );
                return Self::Memory;
            }
        };
        Self::from_runtime_config(runtime_config)
    }

    pub(super) fn new_valkey_for_test(valkey_url: &str, key_prefix: &str) -> Result<Self> {
        let backend = ValkeyTelegramSendRateLimitBackend::new(valkey_url, key_prefix)?;
        Ok(Self::Valkey(Arc::new(backend)))
    }

    pub(super) fn valkey(&self) -> Option<&Arc<ValkeyTelegramSendRateLimitBackend>> {
        match self {
            Self::Memory => None,
            Self::Valkey(backend) => Some(backend),
        }
    }

    fn from_runtime_config(config: TelegramSendRateLimitRuntimeConfig) -> Self {
        let Some(valkey_url) = config.valkey_url.as_deref() else {
            tracing::warn!(
                event = "telegram.send_gate.backend.init_failed",
                backend = "memory",
                reason = "missing_valkey_url",
                "telegram send gate has no Valkey URL configured; falling back to memory backend"
            );
            return Self::Memory;
        };

        match ValkeyTelegramSendRateLimitBackend::new(valkey_url, config.key_prefix.as_str()) {
            Ok(backend) => {
                tracing::info!(
                    event = "telegram.send_gate.backend.initialized",
                    backend = "valkey",
                    key_prefix = %config.key_prefix,
                    "telegram send rate-limit gate backend initialized"
                );
                Self::Valkey(Arc::new(backend))
            }
            Err(error) => {
                tracing::warn!(
                    event = "telegram.send_gate.backend.init_failed",
                    backend = "valkey",
                    error = %error,
                    "failed to initialize valkey send gate backend; falling back to memory backend"
                );
                Self::Memory
            }
        }
    }
}

impl TelegramSendRateLimitRuntimeConfig {
    fn from_env() -> Result<Self> {
        let settings = load_runtime_settings();
        let valkey_url = non_empty_env("VALKEY_URL")
            .or_else(|| settings.session.valkey_url.clone())
            .and_then(non_empty_string);

        let key_prefix = non_empty_env(TELEGRAM_SEND_GATE_KEY_PREFIX_ENV)
            .or_else(|| settings.telegram.send_rate_limit_gate_key_prefix.clone())
            .and_then(non_empty_string)
            .unwrap_or_else(|| DEFAULT_SEND_GATE_KEY_PREFIX.to_string());

        Ok(Self {
            valkey_url,
            key_prefix,
        })
    }
}

impl ValkeyTelegramSendRateLimitBackend {
    fn new(valkey_url: &str, key_prefix: &str) -> Result<Self> {
        let client = redis::Client::open(valkey_url).with_context(|| {
            format!("invalid valkey url for telegram send gate backend: {valkey_url}")
        })?;
        let trimmed_prefix = key_prefix.trim();
        if trimmed_prefix.is_empty() {
            bail!("telegram send gate key prefix must not be empty");
        }
        Ok(Self {
            client,
            rate_key: format!("{trimmed_prefix}:rate_limit"),
            spread_key: format!("{trimmed_prefix}:spread_slot"),
            connection: Arc::new(Mutex::new(None)),
        })
    }

    pub(super) async fn current_window_with_spread_slot(&self) -> Result<Option<(Duration, u64)>> {
        let script = r#"
local ttl = redis.call("PTTL", KEYS[1])
if ttl <= 0 then
  return {0, 0}
end
local slot = redis.call("INCR", KEYS[2])
if slot == 1 then
  redis.call("PEXPIRE", KEYS[2], ttl)
else
  local spread_ttl = redis.call("PTTL", KEYS[2])
  if spread_ttl < ttl then
    redis.call("PEXPIRE", KEYS[2], ttl)
  end
end
return {ttl, slot}
"#;
        let (ttl_ms, slot): (i64, i64) = self
            .run_command("send_gate_current_window_with_spread_slot", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(2)
                    .arg(self.rate_key.as_str())
                    .arg(self.spread_key.as_str());
                cmd
            })
            .await?;
        if ttl_ms <= 0 || slot <= 0 {
            return Ok(None);
        }
        Ok(Some((
            Duration::from_millis(ttl_ms as u64),
            (slot - 1) as u64,
        )))
    }

    pub(super) async fn extend_window(
        &self,
        requested_delay: Duration,
    ) -> Result<Option<Duration>> {
        let requested_ms = requested_delay.as_millis();
        if requested_ms == 0 {
            return Ok(None);
        }
        let script = r#"
local requested = tonumber(ARGV[1])
if not requested or requested <= 0 then
  return 0
end
local ttl = redis.call("PTTL", KEYS[1])
if ttl < requested then
  redis.call("SET", KEYS[1], "1", "PX", requested)
  redis.call("DEL", KEYS[2])
  return requested
end
return ttl
"#;
        let effective_ttl_ms: i64 = self
            .run_command("send_gate_extend_window", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(2)
                    .arg(self.rate_key.as_str())
                    .arg(self.spread_key.as_str())
                    .arg(requested_ms as u64);
                cmd
            })
            .await?;
        if effective_ttl_ms <= 0 {
            return Ok(None);
        }
        Ok(Some(Duration::from_millis(effective_ttl_ms as u64)))
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
            let conn = conn_guard.as_mut().ok_or_else(|| {
                anyhow::anyhow!("telegram send gate valkey connection unavailable")
            })?;
            let cmd = build();
            let result: redis::RedisResult<T> = cmd.query_async(conn).await;
            match result {
                Ok(value) => {
                    if attempt > 0 {
                        tracing::debug!(
                            event = "telegram.send_gate.valkey.command.retry_succeeded",
                            operation,
                            attempt = attempt + 1,
                            "telegram send gate valkey command succeeded after retry"
                        );
                    }
                    return Ok(value);
                }
                Err(error) => {
                    tracing::warn!(
                        event = "telegram.send_gate.valkey.command.retry_failed",
                        operation,
                        attempt = attempt + 1,
                        error = %error,
                        "telegram send gate valkey command failed; reconnecting"
                    );
                    *conn_guard = None;
                    last_err = Some(
                        anyhow::anyhow!(error).context("telegram send gate valkey command failed"),
                    );
                    if attempt == 0 {
                        continue;
                    }
                }
            }
        }
        Err(last_err.unwrap_or_else(|| {
            anyhow::anyhow!("telegram send gate valkey command failed unexpectedly")
        }))
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
                .context("failed to open valkey connection for telegram send gate")?,
        );
        tracing::debug!(
            event = "telegram.send_gate.valkey.connected",
            rate_key = %self.rate_key,
            "telegram send gate valkey backend connected"
        );
        Ok(())
    }
}

fn non_empty_env(name: &str) -> Option<String> {
    std::env::var(name).ok().and_then(non_empty_string)
}

fn non_empty_string(value: String) -> Option<String> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed.to_string())
    }
}
