//! Redis/Valkey-backed session persistence for multi-instance context sharing.

use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::{Context, Result};
use omni_window::TurnSlot;
use redis::FromRedisValue;
use serde::Deserialize;
use tokio::sync::Mutex;

use crate::config::load_runtime_settings;
use crate::observability::SessionEvent;

use super::message::ChatMessage;
use super::summary::SessionSummarySegment;

const DEFAULT_SESSION_KEY_PREFIX: &str = "omni-agent:session";
const DEFAULT_STREAM_MAX_LEN: usize = 10_000;
const SESSION_CONTEXT_BACKUP_META_PREFIX: &str = "__session_context_backup_meta__:";

#[derive(Debug, Deserialize)]
struct LegacySessionContextBackupMetadataPayload {
    #[allow(dead_code)]
    messages: usize,
    #[allow(dead_code)]
    summary_segments: usize,
    #[allow(dead_code)]
    saved_at_unix_ms: u64,
}

#[derive(Debug, Clone)]
pub(crate) struct RedisSessionConfig {
    pub(crate) url: String,
    pub(crate) key_prefix: String,
    pub(crate) ttl_secs: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct RedisSessionRuntimeSnapshot {
    pub(crate) url: String,
    pub(crate) key_prefix: String,
    pub(crate) ttl_secs: Option<u64>,
}

impl RedisSessionConfig {
    pub(crate) fn from_env() -> Option<Self> {
        let settings = load_runtime_settings();
        let url = std::env::var("VALKEY_URL")
            .ok()
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty())
            .or_else(|| {
                settings
                    .session
                    .valkey_url
                    .as_deref()
                    .map(str::trim)
                    .map(str::to_string)
                    .filter(|v| !v.is_empty())
            })?;
        let key_prefix = std::env::var("OMNI_AGENT_SESSION_VALKEY_PREFIX")
            .ok()
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty())
            .or_else(|| {
                settings
                    .session
                    .redis_prefix
                    .as_deref()
                    .map(str::trim)
                    .map(str::to_string)
                    .filter(|v| !v.is_empty())
            })
            .unwrap_or_else(|| DEFAULT_SESSION_KEY_PREFIX.to_string());
        let ttl_secs = match std::env::var("OMNI_AGENT_SESSION_TTL_SECS") {
            Ok(raw) => match raw.parse::<u64>() {
                Ok(v) if v > 0 => Some(v),
                _ => {
                    tracing::warn!(
                        env_var = "OMNI_AGENT_SESSION_TTL_SECS",
                        value = %raw,
                        "invalid session ttl env value; using settings/default"
                    );
                    settings.session.ttl_secs.filter(|v| *v > 0)
                }
            },
            Err(_) => settings.session.ttl_secs.filter(|v| *v > 0),
        };
        Some(Self {
            url,
            key_prefix,
            ttl_secs,
        })
    }
}

#[derive(Debug)]
pub(crate) struct RedisSessionBackend {
    client: redis::Client,
    url: String,
    key_prefix: String,
    ttl_secs: Option<u64>,
    connection: Arc<Mutex<Option<redis::aio::MultiplexedConnection>>>,
}

impl RedisSessionBackend {
    pub(crate) fn from_env() -> Option<Result<Self>> {
        let cfg = RedisSessionConfig::from_env()?;
        Some(Self::new(cfg))
    }

    pub(crate) fn new(cfg: RedisSessionConfig) -> Result<Self> {
        let client = redis::Client::open(cfg.url.as_str())
            .with_context(|| format!("invalid redis url for session backend: {}", cfg.url))?;
        Ok(Self {
            client,
            url: cfg.url,
            key_prefix: cfg.key_prefix,
            ttl_secs: cfg.ttl_secs,
            connection: Arc::new(Mutex::new(None)),
        })
    }

    pub(crate) fn new_from_parts(
        url: String,
        key_prefix: Option<String>,
        ttl_secs: Option<u64>,
    ) -> Result<Self> {
        let prefix = key_prefix
            .map(|v| v.trim().to_string())
            .filter(|v| !v.is_empty())
            .unwrap_or_else(|| DEFAULT_SESSION_KEY_PREFIX.to_string());
        Self::new(RedisSessionConfig {
            url,
            key_prefix: prefix,
            ttl_secs: ttl_secs.filter(|value| *value > 0),
        })
    }

    pub(crate) fn key_prefix(&self) -> &str {
        &self.key_prefix
    }

    pub(crate) fn ttl_secs(&self) -> Option<u64> {
        self.ttl_secs
    }

    pub(crate) fn runtime_snapshot(&self) -> RedisSessionRuntimeSnapshot {
        RedisSessionRuntimeSnapshot {
            url: self.url.clone(),
            key_prefix: self.key_prefix.clone(),
            ttl_secs: self.ttl_secs,
        }
    }

    fn messages_key(&self, session_id: &str) -> String {
        format!("{}:messages:{}", self.key_prefix, session_id)
    }

    fn window_key(&self, session_id: &str) -> String {
        format!("{}:window:{}", self.key_prefix, session_id)
    }

    fn summary_key(&self, session_id: &str) -> String {
        format!("{}:summary:{}", self.key_prefix, session_id)
    }

    fn stream_key(&self, stream_name: &str) -> String {
        format!("{}:stream:{}", self.key_prefix, stream_name)
    }

    fn stream_metrics_global_key(&self, stream_name: &str) -> String {
        format!("{}:metrics:{}", self.key_prefix, stream_name)
    }

    fn stream_metrics_session_key(&self, stream_name: &str, session_id: &str) -> String {
        format!(
            "{}:metrics:{}:session:{}",
            self.key_prefix, stream_name, session_id
        )
    }

    fn now_unix_ms() -> u64 {
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_millis() as u64)
            .unwrap_or(0)
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
                .context("failed to open redis connection for session backend")?,
        );
        tracing::debug!(
            event = SessionEvent::SessionValkeyConnected.as_str(),
            key_prefix = %self.key_prefix,
            "valkey session backend connected"
        );
        Ok(())
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
                .ok_or_else(|| anyhow::anyhow!("redis session backend connection unavailable"))?;
            let cmd = build();
            let result: redis::RedisResult<T> = cmd.query_async(conn).await;
            match result {
                Ok(value) => {
                    if attempt > 0 {
                        tracing::debug!(
                            event = SessionEvent::SessionValkeyCommandRetrySucceeded.as_str(),
                            operation,
                            attempt = attempt + 1,
                            "valkey command succeeded after retry"
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
                        "valkey command attempt failed; reconnecting"
                    );
                    *conn_guard = None;
                    last_err = Some(
                        anyhow::anyhow!(err).context("redis command failed for session backend"),
                    );
                    if attempt == 0 {
                        continue;
                    }
                }
            }
        }
        tracing::warn!(
            event = SessionEvent::SessionValkeyCommandRetryFailed.as_str(),
            operation,
            "valkey command failed after retry"
        );
        Err(last_err.unwrap_or_else(|| anyhow::anyhow!("redis command failed for unknown reason")))
    }

    async fn run_pipeline<T, F>(&self, operation: &'static str, build: F) -> Result<T>
    where
        T: FromRedisValue + Send,
        F: Fn() -> redis::Pipeline,
    {
        let mut last_err: Option<anyhow::Error> = None;
        for attempt in 0..2 {
            let mut conn_guard = self.connection.lock().await;
            self.ensure_connection(&mut conn_guard).await?;
            let conn = conn_guard
                .as_mut()
                .ok_or_else(|| anyhow::anyhow!("redis session backend connection unavailable"))?;
            let pipe = build();
            let result: redis::RedisResult<T> = pipe.query_async(conn).await;
            match result {
                Ok(value) => {
                    if attempt > 0 {
                        tracing::debug!(
                            event = SessionEvent::SessionValkeyPipelineRetrySucceeded.as_str(),
                            operation,
                            attempt = attempt + 1,
                            "valkey pipeline succeeded after retry"
                        );
                    }
                    return Ok(value);
                }
                Err(err) => {
                    tracing::warn!(
                        event = SessionEvent::SessionValkeyPipelineRetryFailed.as_str(),
                        operation,
                        attempt = attempt + 1,
                        error = %err,
                        "valkey pipeline attempt failed; reconnecting"
                    );
                    *conn_guard = None;
                    last_err = Some(
                        anyhow::anyhow!(err).context("redis pipeline failed for session backend"),
                    );
                    if attempt == 0 {
                        continue;
                    }
                }
            }
        }
        tracing::warn!(
            event = SessionEvent::SessionValkeyPipelineRetryFailed.as_str(),
            operation,
            "valkey pipeline failed after retry"
        );
        Err(last_err.unwrap_or_else(|| anyhow::anyhow!("redis pipeline failed for unknown reason")))
    }

    pub(crate) async fn append_messages(
        &self,
        session_id: &str,
        messages: &[ChatMessage],
    ) -> Result<()> {
        if messages.is_empty() {
            return Ok(());
        }
        let key = self.messages_key(session_id);
        let encoded: Vec<String> = messages
            .iter()
            .map(serde_json::to_string)
            .collect::<std::result::Result<Vec<_>, _>>()
            .context("failed to encode chat messages for redis")?;
        let ttl_secs = self.ttl_secs;

        self.run_pipeline::<(), _>("append_messages", || {
            let mut pipe = redis::pipe();
            pipe.atomic();
            pipe.cmd("RPUSH").arg(&key);
            for payload in &encoded {
                pipe.arg(payload);
            }
            pipe.ignore();
            if let Some(ttl) = ttl_secs {
                pipe.cmd("EXPIRE").arg(&key).arg(ttl).ignore();
            }
            pipe
        })
        .await?;
        tracing::debug!(
            event = SessionEvent::SessionMessagesAppended.as_str(),
            session_id,
            appended_messages = encoded.len(),
            ttl_secs = ?ttl_secs,
            "valkey session messages appended"
        );
        Ok(())
    }

    pub(crate) async fn replace_messages(
        &self,
        session_id: &str,
        messages: &[ChatMessage],
    ) -> Result<usize> {
        let key = self.messages_key(session_id);
        let encoded: Vec<String> = messages
            .iter()
            .map(serde_json::to_string)
            .collect::<std::result::Result<Vec<_>, _>>()
            .context("failed to encode chat messages for redis replace")?;
        let ttl_secs = self.ttl_secs.unwrap_or(0);
        let message_count = encoded.len();
        let message_count_i64 = i64::try_from(message_count)
            .context("message count overflow while replacing redis session messages")?;
        let script = r#"
local key = KEYS[1]
local ttl = tonumber(ARGV[1]) or 0
local count = tonumber(ARGV[2]) or 0
redis.call("DEL", key)
if count > 0 then
  for i = 1, count do
    redis.call("RPUSH", key, ARGV[2 + i])
  end
  if ttl > 0 then
    redis.call("EXPIRE", key, ttl)
  end
end
return count
"#;

        let replaced_count = self
            .run_command::<usize, _>("replace_messages", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(1)
                    .arg(&key)
                    .arg(ttl_secs)
                    .arg(message_count_i64);
                for payload in &encoded {
                    cmd.arg(payload);
                }
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionMessagesReplaced.as_str(),
            session_id,
            replaced_messages = replaced_count,
            ttl_secs = ?self.ttl_secs,
            "valkey session messages replaced atomically"
        );
        Ok(replaced_count)
    }

    pub(crate) async fn get_messages(&self, session_id: &str) -> Result<Vec<ChatMessage>> {
        let key = self.messages_key(session_id);
        let payloads = self
            .run_command::<Vec<String>, _>("get_messages", || {
                let mut cmd = redis::cmd("LRANGE");
                cmd.arg(&key).arg(0).arg(-1);
                cmd
            })
            .await?;
        let mut out = Vec::with_capacity(payloads.len());
        let mut invalid_payloads = 0usize;
        for payload in payloads {
            match decode_chat_message_payload(session_id, &payload) {
                Ok(message) => out.push(message),
                Err(error) => {
                    invalid_payloads += 1;
                    tracing::warn!(
                        event = SessionEvent::SessionMessagesLoaded.as_str(),
                        session_id,
                        error = %error,
                        "invalid chat message payload in redis session store"
                    );
                }
            }
        }
        tracing::debug!(
            event = SessionEvent::SessionMessagesLoaded.as_str(),
            session_id,
            loaded_messages = out.len(),
            invalid_payloads,
            "valkey session messages loaded"
        );
        Ok(out)
    }

    pub(crate) async fn get_messages_len(&self, session_id: &str) -> Result<usize> {
        let key = self.messages_key(session_id);
        let message_count = self
            .run_command::<usize, _>("get_messages_len", || {
                let mut cmd = redis::cmd("LLEN");
                cmd.arg(&key);
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionMessagesLoaded.as_str(),
            session_id,
            loaded_messages = message_count,
            count_only = true,
            "valkey session message count loaded"
        );
        Ok(message_count)
    }

    pub(crate) async fn clear_messages(&self, session_id: &str) -> Result<()> {
        let key = self.messages_key(session_id);
        let _ = self
            .run_command::<i64, _>("clear_messages", || {
                let mut cmd = redis::cmd("DEL");
                cmd.arg(&key);
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionMessagesCleared.as_str(),
            session_id,
            "valkey session messages cleared"
        );
        Ok(())
    }

    pub(crate) async fn publish_stream_event(
        &self,
        stream_name: &str,
        fields: &[(String, String)],
    ) -> Result<String> {
        if stream_name.trim().is_empty() {
            anyhow::bail!("stream_name must not be empty");
        }
        if fields.is_empty() {
            anyhow::bail!("stream event fields must not be empty");
        }
        let stream_key = self.stream_key(stream_name);
        let global_metrics_key = self.stream_metrics_global_key(stream_name);
        let kind = fields
            .iter()
            .find_map(|(field, value)| (field == "kind").then_some(value.clone()))
            .unwrap_or_else(|| "unknown".to_string());
        let session_id = fields
            .iter()
            .find_map(|(field, value)| (field == "session_id").then_some(value.clone()))
            .unwrap_or_default();
        let session_metrics_key = if session_id.is_empty() {
            self.stream_metrics_session_key(stream_name, "__none__")
        } else {
            self.stream_metrics_session_key(stream_name, &session_id)
        };
        let ttl_secs = self.ttl_secs.unwrap_or(0);
        let now_unix_ms = Self::now_unix_ms();
        let field_count = i64::try_from(fields.len())
            .context("stream event fields count overflow for valkey stream publish")?;
        let script = r#"
local stream_key = KEYS[1]
local global_metrics_key = KEYS[2]
local session_metrics_key = KEYS[3]

local max_len = tonumber(ARGV[1]) or 10000
local ttl_secs = tonumber(ARGV[2]) or 0
local updated_at_unix_ms = tostring(ARGV[3])
local kind = ARGV[4]
local session_id = ARGV[5]
local field_count = tonumber(ARGV[6]) or 0

if field_count <= 0 then
  return redis.error_reply("stream event fields must not be empty")
end

local entries = {}
for i = 1, field_count do
  local offset = 6 + ((i - 1) * 2)
  entries[(i - 1) * 2 + 1] = ARGV[offset + 1]
  entries[(i - 1) * 2 + 2] = ARGV[offset + 2]
end

local event_id = redis.call("XADD", stream_key, "MAXLEN", "~", max_len, "*", unpack(entries))
redis.call("HINCRBY", global_metrics_key, "events_total", 1)
redis.call("HINCRBY", global_metrics_key, "kind:" .. kind, 1)
redis.call(
  "HSET",
  global_metrics_key,
  "last_event_id",
  event_id,
  "last_kind",
  kind,
  "updated_at_unix_ms",
  updated_at_unix_ms
)

if session_id ~= "" then
  redis.call("HINCRBY", session_metrics_key, "events_total", 1)
  redis.call("HINCRBY", session_metrics_key, "kind:" .. kind, 1)
  redis.call(
    "HSET",
    session_metrics_key,
    "last_event_id",
    event_id,
    "last_kind",
    kind,
    "updated_at_unix_ms",
    updated_at_unix_ms
  )
end

if ttl_secs > 0 then
  redis.call("EXPIRE", stream_key, ttl_secs)
  redis.call("EXPIRE", global_metrics_key, ttl_secs)
  if session_id ~= "" then
    redis.call("EXPIRE", session_metrics_key, ttl_secs)
  end
end

return event_id
"#;
        let event_id = self
            .run_command::<String, _>("publish_stream_event", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(3)
                    .arg(&stream_key)
                    .arg(&global_metrics_key)
                    .arg(&session_metrics_key)
                    .arg(DEFAULT_STREAM_MAX_LEN)
                    .arg(ttl_secs)
                    .arg(now_unix_ms)
                    .arg(&kind)
                    .arg(&session_id)
                    .arg(field_count);
                for (field, value) in fields {
                    cmd.arg(field).arg(value);
                }
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionStreamEventPublished.as_str(),
            stream_name,
            stream_key = %stream_key,
            global_metrics_key = %global_metrics_key,
            session_metrics_key = %session_metrics_key,
            kind = %kind,
            session_id = %session_id,
            event_id = %event_id,
            fields = fields.len(),
            "valkey stream event published"
        );
        Ok(event_id)
    }

    pub(crate) async fn append_window_slots(
        &self,
        session_id: &str,
        max_slots: usize,
        slots: &[TurnSlot],
    ) -> Result<()> {
        if slots.is_empty() {
            return Ok(());
        }
        let key = self.window_key(session_id);
        let encoded: Vec<String> = slots
            .iter()
            .map(serde_json::to_string)
            .collect::<std::result::Result<Vec<_>, _>>()
            .context("failed to encode window slots for redis")?;
        let max_slots_i64 = max_slots.max(1) as i64;
        let ttl_secs = self.ttl_secs;

        self.run_pipeline::<(), _>("append_window_slots", || {
            let mut pipe = redis::pipe();
            pipe.atomic();
            pipe.cmd("RPUSH").arg(&key);
            for payload in &encoded {
                pipe.arg(payload);
            }
            pipe.ignore();
            pipe.cmd("LTRIM")
                .arg(&key)
                .arg(-max_slots_i64)
                .arg(-1)
                .ignore();
            if let Some(ttl) = ttl_secs {
                pipe.cmd("EXPIRE").arg(&key).arg(ttl).ignore();
            }
            pipe
        })
        .await?;
        tracing::debug!(
            event = SessionEvent::SessionWindowSlotsAppended.as_str(),
            session_id,
            appended_slots = encoded.len(),
            max_slots = max_slots_i64,
            ttl_secs = ?ttl_secs,
            "valkey session window slots appended"
        );
        Ok(())
    }

    pub(crate) async fn get_recent_window_slots(
        &self,
        session_id: &str,
        limit: usize,
    ) -> Result<Vec<TurnSlot>> {
        if limit == 0 {
            return Ok(Vec::new());
        }
        let key = self.window_key(session_id);
        let limit_i64 = limit as i64;
        let payloads = self
            .run_command::<Vec<String>, _>("get_recent_window_slots", || {
                let mut cmd = redis::cmd("LRANGE");
                cmd.arg(&key).arg(-limit_i64).arg(-1);
                cmd
            })
            .await?;
        let mut out = Vec::with_capacity(payloads.len());
        let mut invalid_payloads = 0usize;
        for payload in payloads {
            match serde_json::from_str::<TurnSlot>(&payload) {
                Ok(slot) => out.push(slot),
                Err(error) => {
                    invalid_payloads += 1;
                    tracing::warn!(
                        event = SessionEvent::SessionWindowSlotsLoaded.as_str(),
                        session_id,
                        error = %error,
                        "invalid turn slot payload in redis session window"
                    );
                }
            }
        }
        tracing::debug!(
            event = SessionEvent::SessionWindowSlotsLoaded.as_str(),
            session_id,
            requested_limit = limit,
            loaded_slots = out.len(),
            invalid_payloads,
            "valkey session window slots loaded"
        );
        Ok(out)
    }

    pub(crate) async fn get_window_stats(
        &self,
        session_id: &str,
    ) -> Result<Option<(u64, u64, usize)>> {
        let key = self.window_key(session_id);
        let len = self
            .run_command::<usize, _>("get_window_stats_len", || {
                let mut cmd = redis::cmd("LLEN");
                cmd.arg(&key);
                cmd
            })
            .await?;
        if len == 0 {
            return Ok(None);
        }
        let payloads = self
            .run_command::<Vec<String>, _>("get_window_stats_payload", || {
                let mut cmd = redis::cmd("LRANGE");
                cmd.arg(&key).arg(0).arg(-1);
                cmd
            })
            .await?;
        let mut total_tool_calls: u64 = 0;
        for payload in payloads {
            if let Ok(slot) = serde_json::from_str::<TurnSlot>(&payload) {
                total_tool_calls = total_tool_calls.saturating_add(u64::from(slot.tool_count));
            }
        }
        tracing::debug!(
            event = SessionEvent::SessionWindowStatsLoaded.as_str(),
            session_id,
            slots = len,
            total_tool_calls,
            "valkey session window stats loaded"
        );
        Ok(Some((len as u64, total_tool_calls, len)))
    }

    pub(crate) async fn clear_window(&self, session_id: &str) -> Result<()> {
        let key = self.window_key(session_id);
        let _ = self
            .run_command::<i64, _>("clear_window", || {
                let mut cmd = redis::cmd("DEL");
                cmd.arg(&key);
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionWindowCleared.as_str(),
            session_id,
            "valkey session window cleared"
        );
        Ok(())
    }

    pub(crate) async fn append_summary_segment(
        &self,
        session_id: &str,
        max_segments: usize,
        segment: &SessionSummarySegment,
    ) -> Result<()> {
        let key = self.summary_key(session_id);
        let encoded =
            serde_json::to_string(segment).context("failed to encode summary segment for redis")?;
        let max_segments_i64 = max_segments.max(1) as i64;
        let ttl_secs = self.ttl_secs;

        self.run_pipeline::<(), _>("append_summary_segment", || {
            let mut pipe = redis::pipe();
            pipe.atomic();
            pipe.cmd("RPUSH").arg(&key).arg(&encoded).ignore();
            pipe.cmd("LTRIM")
                .arg(&key)
                .arg(-max_segments_i64)
                .arg(-1)
                .ignore();
            if let Some(ttl) = ttl_secs {
                pipe.cmd("EXPIRE").arg(&key).arg(ttl).ignore();
            }
            pipe
        })
        .await?;
        tracing::debug!(
            event = SessionEvent::SessionSummarySegmentAppended.as_str(),
            session_id,
            max_segments,
            ttl_secs = ?ttl_secs,
            "valkey session summary segment appended"
        );
        Ok(())
    }

    pub(crate) async fn get_recent_summary_segments(
        &self,
        session_id: &str,
        limit: usize,
    ) -> Result<Vec<SessionSummarySegment>> {
        if limit == 0 {
            return Ok(Vec::new());
        }
        let key = self.summary_key(session_id);
        let limit_i64 = limit as i64;
        let payloads = self
            .run_command::<Vec<String>, _>("get_recent_summary_segments", || {
                let mut cmd = redis::cmd("LRANGE");
                cmd.arg(&key).arg(-limit_i64).arg(-1);
                cmd
            })
            .await?;
        let mut out = Vec::with_capacity(payloads.len());
        let mut invalid_payloads = 0usize;
        for payload in payloads {
            match serde_json::from_str::<SessionSummarySegment>(&payload) {
                Ok(segment) => out.push(segment),
                Err(error) => {
                    invalid_payloads += 1;
                    tracing::warn!(
                        event = SessionEvent::SessionSummarySegmentsLoaded.as_str(),
                        session_id,
                        error = %error,
                        "invalid session summary payload in redis"
                    );
                }
            }
        }
        tracing::debug!(
            event = SessionEvent::SessionSummarySegmentsLoaded.as_str(),
            session_id,
            requested_limit = limit,
            loaded_segments = out.len(),
            invalid_payloads,
            "valkey session summary segments loaded"
        );
        Ok(out)
    }

    pub(crate) async fn get_summary_len(&self, session_id: &str) -> Result<usize> {
        let key = self.summary_key(session_id);
        let segment_count = self
            .run_command::<usize, _>("get_summary_len", || {
                let mut cmd = redis::cmd("LLEN");
                cmd.arg(&key);
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionSummarySegmentsLoaded.as_str(),
            session_id,
            loaded_segments = segment_count,
            count_only = true,
            "valkey session summary segment count loaded"
        );
        Ok(segment_count)
    }

    pub(crate) async fn clear_summary(&self, session_id: &str) -> Result<()> {
        let key = self.summary_key(session_id);
        let _ = self
            .run_command::<i64, _>("clear_summary", || {
                let mut cmd = redis::cmd("DEL");
                cmd.arg(&key);
                cmd
            })
            .await?;
        tracing::debug!(
            event = SessionEvent::SessionSummaryCleared.as_str(),
            session_id,
            "valkey session summary cleared"
        );
        Ok(())
    }

    pub(crate) async fn drain_oldest_window_slots(
        &self,
        session_id: &str,
        n: usize,
    ) -> Result<Vec<TurnSlot>> {
        if n == 0 {
            return Ok(Vec::new());
        }
        let key = self.window_key(session_id);
        let mut drained = Vec::new();
        for _ in 0..n {
            let popped = self
                .run_command::<Option<String>, _>("drain_oldest_window_slots", || {
                    let mut cmd = redis::cmd("LPOP");
                    cmd.arg(&key);
                    cmd
                })
                .await?;
            let Some(payload) = popped else {
                break;
            };
            match serde_json::from_str::<TurnSlot>(&payload) {
                Ok(slot) => drained.push(slot),
                Err(error) => {
                    tracing::warn!(
                        event = SessionEvent::SessionWindowSlotsDrained.as_str(),
                        session_id,
                        error = %error,
                        "invalid drained turn slot payload from redis"
                    );
                }
            }
        }
        tracing::debug!(
            event = SessionEvent::SessionWindowSlotsDrained.as_str(),
            session_id,
            requested_slots = n,
            drained_slots = drained.len(),
            "valkey session window slots drained"
        );
        Ok(drained)
    }

    pub(crate) async fn atomic_reset_bounded_snapshot(
        &self,
        session_id: &str,
        backup_session_id: &str,
        metadata_session_id: &str,
        saved_at_unix_ms: u64,
    ) -> Result<(usize, usize)> {
        let src_window = self.window_key(session_id);
        let src_summary = self.summary_key(session_id);
        let dst_window = self.window_key(backup_session_id);
        let dst_summary = self.summary_key(backup_session_id);
        let metadata_key = self.messages_key(metadata_session_id);
        let ttl_secs = self.ttl_secs.unwrap_or(0);

        let script = r#"
local src_window = KEYS[1]
local src_summary = KEYS[2]
local dst_window = KEYS[3]
local dst_summary = KEYS[4]
local metadata_key = KEYS[5]
local saved_at = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])

redis.call("DEL", dst_window, dst_summary, metadata_key)

local window_len = redis.call("LLEN", src_window)
local summary_len = redis.call("LLEN", src_summary)

if window_len > 0 then
  redis.call("RENAME", src_window, dst_window)
end
if summary_len > 0 then
  redis.call("RENAME", src_summary, dst_summary)
end

if window_len > 0 or summary_len > 0 then
  local metadata_payload = cjson.encode({
    messages = window_len,
    summary_segments = summary_len,
    saved_at_unix_ms = saved_at
  })
  local chat_message_payload = cjson.encode({
    role = "system",
    content = metadata_payload
  })
  redis.call("RPUSH", metadata_key, chat_message_payload)
  if ttl > 0 then
    redis.call("EXPIRE", metadata_key, ttl)
  end
end

return {window_len, summary_len}
"#;

        let result = self
            .run_command::<(usize, usize), _>("atomic_reset_bounded_snapshot", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(5)
                    .arg(&src_window)
                    .arg(&src_summary)
                    .arg(&dst_window)
                    .arg(&dst_summary)
                    .arg(&metadata_key)
                    .arg(saved_at_unix_ms)
                    .arg(ttl_secs);
                cmd
            })
            .await?;

        tracing::debug!(
            event = SessionEvent::ContextWindowReset.as_str(),
            session_id,
            backup_session_id,
            messages = result.0,
            summary_segments = result.1,
            backend = "valkey",
            "atomic bounded context snapshot reset completed"
        );
        Ok(result)
    }

    pub(crate) async fn atomic_resume_bounded_snapshot(
        &self,
        session_id: &str,
        backup_session_id: &str,
        metadata_session_id: &str,
    ) -> Result<Option<(usize, usize)>> {
        let src_window = self.window_key(backup_session_id);
        let src_summary = self.summary_key(backup_session_id);
        let dst_window = self.window_key(session_id);
        let dst_summary = self.summary_key(session_id);
        let metadata_key = self.messages_key(metadata_session_id);

        let script = r#"
local src_window = KEYS[1]
local src_summary = KEYS[2]
local dst_window = KEYS[3]
local dst_summary = KEYS[4]
local metadata_key = KEYS[5]

local window_len = redis.call("LLEN", src_window)
local summary_len = redis.call("LLEN", src_summary)
if window_len == 0 and summary_len == 0 then
  redis.call("DEL", metadata_key)
  return {0, 0, 0}
end

redis.call("DEL", dst_window, dst_summary)
if window_len > 0 then
  redis.call("RENAME", src_window, dst_window)
end
if summary_len > 0 then
  redis.call("RENAME", src_summary, dst_summary)
end
redis.call("DEL", metadata_key)

return {1, window_len, summary_len}
"#;

        let (restored, window_len, summary_len) = self
            .run_command::<(i64, usize, usize), _>("atomic_resume_bounded_snapshot", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(5)
                    .arg(&src_window)
                    .arg(&src_summary)
                    .arg(&dst_window)
                    .arg(&dst_summary)
                    .arg(&metadata_key);
                cmd
            })
            .await?;

        if restored == 0 {
            tracing::debug!(
                event = SessionEvent::ContextWindowResumeMissing.as_str(),
                session_id,
                backup_session_id,
                backend = "valkey",
                "atomic bounded context resume skipped: no snapshot"
            );
            return Ok(None);
        }

        tracing::debug!(
            event = SessionEvent::ContextWindowResumed.as_str(),
            session_id,
            backup_session_id,
            messages = window_len,
            summary_segments = summary_len,
            backend = "valkey",
            "atomic bounded context snapshot resumed"
        );
        Ok(Some((window_len, summary_len)))
    }

    pub(crate) async fn atomic_drop_bounded_snapshot(
        &self,
        backup_session_id: &str,
        metadata_session_id: &str,
    ) -> Result<bool> {
        let backup_window = self.window_key(backup_session_id);
        let backup_summary = self.summary_key(backup_session_id);
        let metadata_key = self.messages_key(metadata_session_id);
        let script = r#"
local backup_window = KEYS[1]
local backup_summary = KEYS[2]
local metadata_key = KEYS[3]

local window_len = redis.call("LLEN", backup_window)
local summary_len = redis.call("LLEN", backup_summary)
redis.call("DEL", backup_window, backup_summary, metadata_key)
if window_len > 0 or summary_len > 0 then
  return 1
end
return 0
"#;

        let dropped = self
            .run_command::<i64, _>("atomic_drop_bounded_snapshot", || {
                let mut cmd = redis::cmd("EVAL");
                cmd.arg(script)
                    .arg(3)
                    .arg(&backup_window)
                    .arg(&backup_summary)
                    .arg(&metadata_key);
                cmd
            })
            .await?;

        Ok(dropped == 1)
    }
}

fn decode_chat_message_payload(
    session_id: &str,
    payload: &str,
) -> std::result::Result<ChatMessage, serde_json::Error> {
    match serde_json::from_str::<ChatMessage>(payload) {
        Ok(message) => Ok(message),
        Err(chat_message_error) if session_id.starts_with(SESSION_CONTEXT_BACKUP_META_PREFIX) => {
            match serde_json::from_str::<LegacySessionContextBackupMetadataPayload>(payload) {
                Ok(_) => Ok(ChatMessage {
                    role: "system".to_string(),
                    content: Some(payload.to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                }),
                Err(_) => Err(chat_message_error),
            }
        }
        Err(chat_message_error) => Err(chat_message_error),
    }
}
