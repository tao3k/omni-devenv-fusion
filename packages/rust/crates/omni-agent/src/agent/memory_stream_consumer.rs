use anyhow::{Context, Result, bail};
use redis::Value;
use std::collections::HashMap;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::task::JoinHandle;
use tokio::time::sleep;

use crate::agent::logging::should_surface_repeated_failure;
use crate::config::MemoryConfig;
use crate::observability::SessionEvent;
use crate::session::RedisSessionRuntimeSnapshot;

const DEFAULT_STREAM_NAME: &str = "memory.events";
const DEFAULT_CONSUMER_GROUP: &str = "omni-agent-memory";
const DEFAULT_CONSUMER_PREFIX: &str = "agent";
const RECONNECT_BACKOFF_MS: u64 = 500;
const MAX_RECONNECT_BACKOFF_MS: u64 = 30_000;
const STREAM_CONSUMER_RESPONSE_TIMEOUT_GRACE_MS: u64 = 500;

#[derive(Debug, Clone, PartialEq, Eq)]
struct MemoryStreamEvent {
    id: String,
    fields: HashMap<String, String>,
}

#[derive(Debug, Clone)]
struct MemoryStreamConsumerRuntimeConfig {
    redis_url: String,
    stream_name: String,
    stream_key: String,
    stream_consumer_group: String,
    stream_consumer_name: String,
    stream_consumer_batch_size: usize,
    stream_consumer_block_ms: u64,
    metrics_global_key: String,
    metrics_session_prefix: String,
    ttl_secs: Option<u64>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum StreamReadErrorKind {
    MissingConsumerGroup,
    Transport,
    Other,
}

pub(super) fn spawn_memory_stream_consumer(
    memory_cfg: &MemoryConfig,
    session_redis: Option<RedisSessionRuntimeSnapshot>,
) -> Option<JoinHandle<()>> {
    if !memory_cfg.stream_consumer_enabled {
        tracing::info!(
            event = SessionEvent::MemoryStreamConsumerDisabled.as_str(),
            reason = "disabled_by_config",
            "memory stream consumer disabled"
        );
        return None;
    }

    let Some(session_redis) = session_redis else {
        tracing::info!(
            event = SessionEvent::MemoryStreamConsumerDisabled.as_str(),
            reason = "session_valkey_backend_unavailable",
            "memory stream consumer disabled"
        );
        return None;
    };

    let stream_name = non_empty_string(Some(memory_cfg.stream_name.clone()))
        .unwrap_or_else(|| DEFAULT_STREAM_NAME.to_string());
    let stream_consumer_group = non_empty_string(Some(memory_cfg.stream_consumer_group.clone()))
        .unwrap_or_else(|| DEFAULT_CONSUMER_GROUP.to_string());
    let stream_consumer_name_prefix =
        non_empty_string(Some(memory_cfg.stream_consumer_name_prefix.clone()))
            .unwrap_or_else(|| DEFAULT_CONSUMER_PREFIX.to_string());
    let stream_consumer_name = build_consumer_name(&stream_consumer_name_prefix);
    let stream_consumer_batch_size = memory_cfg.stream_consumer_batch_size.max(1);
    let stream_consumer_block_ms = memory_cfg.stream_consumer_block_ms.max(1);

    let runtime_cfg = MemoryStreamConsumerRuntimeConfig {
        redis_url: session_redis.url,
        stream_key: format!("{}:stream:{stream_name}", session_redis.key_prefix),
        stream_name: stream_name.clone(),
        stream_consumer_group,
        stream_consumer_name,
        stream_consumer_batch_size,
        stream_consumer_block_ms,
        metrics_global_key: format!(
            "{}:metrics:{stream_name}:consumer",
            session_redis.key_prefix
        ),
        metrics_session_prefix: format!(
            "{}:metrics:{stream_name}:consumer:session:",
            session_redis.key_prefix
        ),
        ttl_secs: session_redis.ttl_secs,
    };

    tracing::info!(
        event = SessionEvent::MemoryStreamConsumerStarted.as_str(),
        stream_name = %runtime_cfg.stream_name,
        stream_key = %runtime_cfg.stream_key,
        stream_consumer_group = %runtime_cfg.stream_consumer_group,
        stream_consumer_name = %runtime_cfg.stream_consumer_name,
        stream_consumer_batch_size = runtime_cfg.stream_consumer_batch_size,
        stream_consumer_block_ms = runtime_cfg.stream_consumer_block_ms,
        "memory stream consumer task starting"
    );

    Some(tokio::spawn(async move {
        run_consumer_loop(runtime_cfg).await;
    }))
}

async fn run_consumer_loop(config: MemoryStreamConsumerRuntimeConfig) {
    let client = match redis::Client::open(config.redis_url.as_str()) {
        Ok(client) => client,
        Err(error) => {
            tracing::warn!(
                event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                stream_name = %config.stream_name,
                error = %error,
                "memory stream consumer disabled due to invalid redis url"
            );
            return;
        }
    };
    let connection_config = stream_consumer_connection_config(config.stream_consumer_block_ms);
    let response_timeout_ms = stream_consumer_response_timeout(config.stream_consumer_block_ms)
        .as_millis()
        .min(u128::from(u64::MAX)) as u64;

    let mut connect_failure_streak = 0_u32;
    let mut ensure_group_failure_streak = 0_u32;
    let mut read_failure_streak = 0_u32;
    loop {
        let mut connection = match client
            .get_multiplexed_async_connection_with_config(&connection_config)
            .await
        {
            Ok(connection) => {
                connect_failure_streak = 0;
                connection
            }
            Err(error) => {
                connect_failure_streak = connect_failure_streak.saturating_add(1);
                let retry_backoff_ms =
                    compute_retry_backoff_ms(RECONNECT_BACKOFF_MS, connect_failure_streak);
                if should_surface_repeated_failure(connect_failure_streak) {
                    tracing::warn!(
                        event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                        stream_name = %config.stream_name,
                        failure_streak = connect_failure_streak,
                        retry_backoff_ms,
                        response_timeout_ms,
                        error = %error,
                        "memory stream consumer failed to connect to valkey; retrying"
                    );
                } else {
                    tracing::trace!(
                        event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                        stream_name = %config.stream_name,
                        failure_streak = connect_failure_streak,
                        retry_backoff_ms,
                        response_timeout_ms,
                        error = %error,
                        "memory stream consumer failed to connect to valkey; retrying"
                    );
                }
                sleep(Duration::from_millis(retry_backoff_ms)).await;
                continue;
            }
        };

        if let Err(error) = ensure_consumer_group(&mut connection, &config).await {
            ensure_group_failure_streak = ensure_group_failure_streak.saturating_add(1);
            let retry_backoff_ms =
                compute_retry_backoff_ms(RECONNECT_BACKOFF_MS, ensure_group_failure_streak);
            if should_surface_repeated_failure(ensure_group_failure_streak) {
                tracing::warn!(
                    event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                    stream_name = %config.stream_name,
                    stream_consumer_group = %config.stream_consumer_group,
                    failure_streak = ensure_group_failure_streak,
                    retry_backoff_ms,
                    error = %error,
                    "memory stream consumer failed to ensure consumer group; retrying"
                );
            } else {
                tracing::trace!(
                    event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                    stream_name = %config.stream_name,
                    stream_consumer_group = %config.stream_consumer_group,
                    failure_streak = ensure_group_failure_streak,
                    retry_backoff_ms,
                    error = %error,
                    "memory stream consumer failed to ensure consumer group; retrying"
                );
            }
            sleep(Duration::from_millis(retry_backoff_ms)).await;
            continue;
        }
        ensure_group_failure_streak = 0;

        let mut read_pending = true;
        loop {
            let stream_id = if read_pending { "0" } else { ">" };
            match read_stream_events(&mut connection, &config, stream_id).await {
                Ok(events) => {
                    read_failure_streak = 0;
                    if events.is_empty() {
                        if read_pending {
                            read_pending = false;
                        }
                        continue;
                    }
                    for event in events {
                        let kind = field_value_or_default(&event.fields, "kind", "unknown");
                        let session_id = non_empty_string(event.fields.get("session_id").cloned());
                        match ack_and_record_metrics(
                            &mut connection,
                            &config,
                            &event.id,
                            &kind,
                            session_id.as_deref(),
                        )
                        .await
                        {
                            Ok(acked) => {
                                tracing::debug!(
                                    event = SessionEvent::MemoryStreamConsumerEventProcessed
                                        .as_str(),
                                    stream_name = %config.stream_name,
                                    stream_consumer_group = %config.stream_consumer_group,
                                    stream_consumer_name = %config.stream_consumer_name,
                                    event_id = %event.id,
                                    kind = %kind,
                                    session_id = session_id.as_deref().unwrap_or(""),
                                    acked,
                                    "memory stream event processed"
                                );
                            }
                            Err(error) => {
                                read_failure_streak = read_failure_streak.saturating_add(1);
                                let retry_backoff_ms = compute_retry_backoff_ms(
                                    RECONNECT_BACKOFF_MS,
                                    read_failure_streak,
                                );
                                if should_surface_repeated_failure(read_failure_streak) {
                                    tracing::warn!(
                                        event = SessionEvent::MemoryStreamConsumerReadFailed
                                            .as_str(),
                                        stream_name = %config.stream_name,
                                        stream_consumer_group = %config.stream_consumer_group,
                                        stream_consumer_name = %config.stream_consumer_name,
                                        event_id = %event.id,
                                        kind = %kind,
                                        session_id = session_id.as_deref().unwrap_or(""),
                                        failure_streak = read_failure_streak,
                                        retry_backoff_ms,
                                        error = %error,
                                        "memory stream consumer failed to ack/record event"
                                    );
                                } else {
                                    tracing::trace!(
                                        event = SessionEvent::MemoryStreamConsumerReadFailed
                                            .as_str(),
                                        stream_name = %config.stream_name,
                                        stream_consumer_group = %config.stream_consumer_group,
                                        stream_consumer_name = %config.stream_consumer_name,
                                        event_id = %event.id,
                                        kind = %kind,
                                        session_id = session_id.as_deref().unwrap_or(""),
                                        failure_streak = read_failure_streak,
                                        retry_backoff_ms,
                                        error = %error,
                                        "memory stream consumer failed to ack/record event"
                                    );
                                }
                                break;
                            }
                        }
                    }
                }
                Err(error) => {
                    read_failure_streak = read_failure_streak.saturating_add(1);
                    let retry_backoff_ms =
                        compute_retry_backoff_ms(RECONNECT_BACKOFF_MS, read_failure_streak);
                    let error_kind = classify_stream_read_error(&error);
                    let warn = should_surface_repeated_failure(read_failure_streak);
                    match error_kind {
                        StreamReadErrorKind::MissingConsumerGroup => {
                            if warn {
                                tracing::info!(
                                    event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                                    stream_name = %config.stream_name,
                                    stream_consumer_group = %config.stream_consumer_group,
                                    stream_consumer_name = %config.stream_consumer_name,
                                    stream_id,
                                    error_kind = "missing_consumer_group",
                                    failure_streak = read_failure_streak,
                                    retry_backoff_ms,
                                    error = %error,
                                    "memory stream consumer detected missing consumer group; attempting recovery"
                                );
                            } else {
                                tracing::trace!(
                                    event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                                    stream_name = %config.stream_name,
                                    stream_consumer_group = %config.stream_consumer_group,
                                    stream_consumer_name = %config.stream_consumer_name,
                                    stream_id,
                                    error_kind = "missing_consumer_group",
                                    failure_streak = read_failure_streak,
                                    retry_backoff_ms,
                                    error = %error,
                                    "memory stream consumer detected missing consumer group; attempting recovery"
                                );
                            }
                            match ensure_consumer_group(&mut connection, &config).await {
                                Ok(()) => {
                                    read_pending = true;
                                    sleep(Duration::from_millis(retry_backoff_ms)).await;
                                    continue;
                                }
                                Err(ensure_error) => {
                                    if warn {
                                        tracing::warn!(
                                            event = SessionEvent::MemoryStreamConsumerReadFailed
                                                .as_str(),
                                            stream_name = %config.stream_name,
                                            stream_consumer_group = %config.stream_consumer_group,
                                            stream_consumer_name = %config.stream_consumer_name,
                                            stream_id,
                                            error_kind = "missing_consumer_group_recovery_failed",
                                            failure_streak = read_failure_streak,
                                            retry_backoff_ms,
                                            error = %error,
                                            ensure_error = %ensure_error,
                                            "memory stream consumer group recovery failed; reconnecting"
                                        );
                                    } else {
                                        tracing::trace!(
                                            event = SessionEvent::MemoryStreamConsumerReadFailed
                                                .as_str(),
                                            stream_name = %config.stream_name,
                                            stream_consumer_group = %config.stream_consumer_group,
                                            stream_consumer_name = %config.stream_consumer_name,
                                            stream_id,
                                            error_kind = "missing_consumer_group_recovery_failed",
                                            failure_streak = read_failure_streak,
                                            retry_backoff_ms,
                                            error = %error,
                                            ensure_error = %ensure_error,
                                            "memory stream consumer group recovery failed; reconnecting"
                                        );
                                    }
                                    break;
                                }
                            }
                        }
                        StreamReadErrorKind::Transport | StreamReadErrorKind::Other => {
                            if warn {
                                tracing::warn!(
                                    event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                                    stream_name = %config.stream_name,
                                    stream_consumer_group = %config.stream_consumer_group,
                                    stream_consumer_name = %config.stream_consumer_name,
                                    stream_id,
                                    error_kind = ?error_kind,
                                    failure_streak = read_failure_streak,
                                    retry_backoff_ms,
                                    error = %error,
                                    "memory stream consumer read failed; reconnecting"
                                );
                            } else {
                                tracing::trace!(
                                    event = SessionEvent::MemoryStreamConsumerReadFailed.as_str(),
                                    stream_name = %config.stream_name,
                                    stream_consumer_group = %config.stream_consumer_group,
                                    stream_consumer_name = %config.stream_consumer_name,
                                    stream_id,
                                    error_kind = ?error_kind,
                                    failure_streak = read_failure_streak,
                                    retry_backoff_ms,
                                    error = %error,
                                    "memory stream consumer read failed; reconnecting"
                                );
                            }
                            break;
                        }
                    }
                }
            }
        }

        let reconnect_backoff_ms =
            compute_retry_backoff_ms(RECONNECT_BACKOFF_MS, read_failure_streak.max(1));
        sleep(Duration::from_millis(reconnect_backoff_ms)).await;
    }
}

async fn ensure_consumer_group(
    connection: &mut redis::aio::MultiplexedConnection,
    config: &MemoryStreamConsumerRuntimeConfig,
) -> Result<()> {
    let create_result: redis::RedisResult<String> = redis::cmd("XGROUP")
        .arg("CREATE")
        .arg(&config.stream_key)
        .arg(&config.stream_consumer_group)
        .arg("0")
        .arg("MKSTREAM")
        .query_async(connection)
        .await;

    match create_result {
        Ok(_) => {
            tracing::info!(
                event = SessionEvent::MemoryStreamConsumerGroupReady.as_str(),
                stream_name = %config.stream_name,
                stream_key = %config.stream_key,
                stream_consumer_group = %config.stream_consumer_group,
                created = true,
                "memory stream consumer group created"
            );
            Ok(())
        }
        Err(error) if is_busy_group_error(&error) => {
            tracing::trace!(
                event = SessionEvent::MemoryStreamConsumerGroupReady.as_str(),
                stream_name = %config.stream_name,
                stream_key = %config.stream_key,
                stream_consumer_group = %config.stream_consumer_group,
                created = false,
                "memory stream consumer group already exists"
            );
            Ok(())
        }
        Err(error) => Err(anyhow::anyhow!(error).context("xgroup create failed")),
    }
}

async fn read_stream_events(
    connection: &mut redis::aio::MultiplexedConnection,
    config: &MemoryStreamConsumerRuntimeConfig,
    stream_id: &str,
) -> Result<Vec<MemoryStreamEvent>> {
    let mut command = redis::cmd("XREADGROUP");
    command
        .arg("GROUP")
        .arg(&config.stream_consumer_group)
        .arg(&config.stream_consumer_name)
        .arg("COUNT")
        .arg(config.stream_consumer_batch_size);
    if stream_id == ">" {
        command.arg("BLOCK").arg(config.stream_consumer_block_ms);
    }
    command
        .arg("STREAMS")
        .arg(&config.stream_key)
        .arg(stream_id);
    let response: Value = command
        .query_async(connection)
        .await
        .with_context(|| format!("xreadgroup failed for stream_id={stream_id}"))?;

    parse_xreadgroup_reply(response)
}

async fn ack_and_record_metrics(
    connection: &mut redis::aio::MultiplexedConnection,
    config: &MemoryStreamConsumerRuntimeConfig,
    event_id: &str,
    kind: &str,
    session_id: Option<&str>,
) -> Result<u64> {
    let session_id = session_id.unwrap_or_default();
    let session_metrics_key = format!("{}{}", config.metrics_session_prefix, session_id);
    let ttl_secs = config.ttl_secs.unwrap_or(0);
    let now_unix_ms = now_unix_ms();
    let script = r#"
local stream_key = KEYS[1]
local global_metrics_key = KEYS[2]
local session_metrics_key = KEYS[3]

local consumer_group = ARGV[1]
local event_id = ARGV[2]
local kind = ARGV[3]
local session_id = ARGV[4]
local now_unix_ms = ARGV[5]
local ttl_secs = tonumber(ARGV[6]) or 0
local consumer_name = ARGV[7]

local acked = redis.call("XACK", stream_key, consumer_group, event_id)
if acked > 0 then
  redis.call("HINCRBY", global_metrics_key, "processed_total", acked)
  redis.call("HINCRBY", global_metrics_key, "processed_kind:" .. kind, acked)
  redis.call(
    "HSET",
    global_metrics_key,
    "last_processed_event_id",
    event_id,
    "last_processed_kind",
    kind,
    "last_processed_session_id",
    session_id,
    "last_processed_consumer",
    consumer_name,
    "last_processed_at_unix_ms",
    now_unix_ms
  )
  if session_id ~= "" then
    redis.call("HINCRBY", session_metrics_key, "processed_total", acked)
    redis.call("HINCRBY", session_metrics_key, "processed_kind:" .. kind, acked)
    redis.call(
      "HSET",
      session_metrics_key,
      "last_processed_event_id",
      event_id,
      "last_processed_kind",
      kind,
      "last_processed_consumer",
      consumer_name,
      "last_processed_at_unix_ms",
      now_unix_ms
    )
  end
  if ttl_secs > 0 then
    redis.call("EXPIRE", global_metrics_key, ttl_secs)
    if session_id ~= "" then
      redis.call("EXPIRE", session_metrics_key, ttl_secs)
    end
  end
end
return acked
"#;

    let acked: u64 = redis::cmd("EVAL")
        .arg(script)
        .arg(3)
        .arg(&config.stream_key)
        .arg(&config.metrics_global_key)
        .arg(&session_metrics_key)
        .arg(&config.stream_consumer_group)
        .arg(event_id)
        .arg(kind)
        .arg(session_id)
        .arg(now_unix_ms)
        .arg(ttl_secs)
        .arg(&config.stream_consumer_name)
        .query_async(connection)
        .await
        .context("failed to ack memory stream event and update consumer metrics")?;

    Ok(acked)
}

fn parse_xreadgroup_reply(reply: Value) -> Result<Vec<MemoryStreamEvent>> {
    match reply {
        Value::Nil => Ok(Vec::new()),
        Value::Array(streams) => parse_streams_array(streams),
        Value::Map(streams) => parse_streams_map(streams),
        other => bail!("unexpected xreadgroup reply value type: {other:?}"),
    }
}

fn parse_streams_array(streams: Vec<Value>) -> Result<Vec<MemoryStreamEvent>> {
    let mut events = Vec::new();
    for stream in streams {
        let Value::Array(stream_entry) = stream else {
            continue;
        };
        if stream_entry.len() < 2 {
            continue;
        }
        events.extend(parse_event_entries(stream_entry.get(1))?);
    }
    Ok(events)
}

fn parse_streams_map(streams: Vec<(Value, Value)>) -> Result<Vec<MemoryStreamEvent>> {
    let mut events = Vec::new();
    for (_, stream_entries) in streams {
        events.extend(parse_event_entries(Some(&stream_entries))?);
    }
    Ok(events)
}

fn parse_event_entries(entries: Option<&Value>) -> Result<Vec<MemoryStreamEvent>> {
    let Some(entries) = entries else {
        return Ok(Vec::new());
    };
    let Value::Array(entries) = entries else {
        return Ok(Vec::new());
    };
    let mut events = Vec::with_capacity(entries.len());
    for entry in entries {
        let Value::Array(parts) = entry else {
            continue;
        };
        if parts.len() < 2 {
            continue;
        }
        let Some(event_id) = value_to_string(parts.first()) else {
            continue;
        };
        let fields = parse_fields(parts.get(1))?;
        events.push(MemoryStreamEvent {
            id: event_id,
            fields,
        });
    }
    Ok(events)
}

fn parse_fields(value: Option<&Value>) -> Result<HashMap<String, String>> {
    let Some(value) = value else {
        return Ok(HashMap::new());
    };

    match value {
        Value::Map(entries) => {
            let mut fields = HashMap::with_capacity(entries.len());
            for (field, field_value) in entries {
                let Some(field_name) = value_to_string(Some(field)) else {
                    continue;
                };
                let value = value_to_string(Some(field_value)).unwrap_or_default();
                fields.insert(field_name, value);
            }
            Ok(fields)
        }
        Value::Array(parts) => {
            let mut fields = HashMap::with_capacity(parts.len() / 2);
            for pair in parts.chunks(2) {
                let Some(field_name) = value_to_string(pair.first()) else {
                    continue;
                };
                let value = value_to_string(pair.get(1)).unwrap_or_default();
                fields.insert(field_name, value);
            }
            Ok(fields)
        }
        _ => Ok(HashMap::new()),
    }
}

fn value_to_string(value: Option<&Value>) -> Option<String> {
    match value? {
        Value::BulkString(bytes) => Some(String::from_utf8_lossy(bytes).to_string()),
        Value::SimpleString(value) => Some(value.clone()),
        Value::Okay => Some("OK".to_string()),
        Value::Int(value) => Some(value.to_string()),
        Value::Double(value) => Some(value.to_string()),
        Value::Boolean(value) => Some(value.to_string()),
        _ => None,
    }
}

fn field_value_or_default(fields: &HashMap<String, String>, key: &str, default: &str) -> String {
    fields
        .get(key)
        .map(|value| value.trim())
        .filter(|value| !value.is_empty())
        .map(ToString::to_string)
        .unwrap_or_else(|| default.to_string())
}

fn non_empty_string(value: Option<String>) -> Option<String> {
    value
        .map(|raw| raw.trim().to_string())
        .filter(|raw| !raw.is_empty())
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

fn build_consumer_name(prefix: &str) -> String {
    let pid = std::process::id();
    format!("{prefix}-{pid}-{}", now_unix_ms())
}

fn is_busy_group_error(error: &redis::RedisError) -> bool {
    error.to_string().to_ascii_uppercase().contains("BUSYGROUP")
}

fn classify_stream_read_error(error: &anyhow::Error) -> StreamReadErrorKind {
    let message = error_chain_message(error).to_ascii_uppercase();
    if message.contains("NOGROUP") {
        return StreamReadErrorKind::MissingConsumerGroup;
    }
    if [
        "CONNECTION",
        "BROKEN PIPE",
        "RESET BY PEER",
        "TIMED OUT",
        "TIMEOUT",
        "IO ERROR",
        "SOCKET",
        "EOF",
    ]
    .iter()
    .any(|needle| message.contains(needle))
    {
        return StreamReadErrorKind::Transport;
    }
    StreamReadErrorKind::Other
}

fn error_chain_message(error: &anyhow::Error) -> String {
    let mut parts = Vec::new();
    for cause in error.chain() {
        let cause_text = cause.to_string();
        if cause_text.is_empty() {
            continue;
        }
        parts.push(cause_text);
    }
    if parts.is_empty() {
        error.to_string()
    } else {
        parts.join(": ")
    }
}

fn stream_consumer_response_timeout(block_ms: u64) -> Duration {
    Duration::from_millis(
        block_ms
            .max(1)
            .saturating_add(STREAM_CONSUMER_RESPONSE_TIMEOUT_GRACE_MS),
    )
}

fn stream_consumer_connection_config(block_ms: u64) -> redis::AsyncConnectionConfig {
    redis::AsyncConnectionConfig::new()
        .set_response_timeout(Some(stream_consumer_response_timeout(block_ms)))
}

fn compute_retry_backoff_ms(base_ms: u64, failure_streak: u32) -> u64 {
    if failure_streak <= 1 {
        return base_ms.max(1);
    }
    let shift = failure_streak.saturating_sub(1).min(12);
    base_ms
        .max(1)
        .saturating_mul(1u64 << shift)
        .min(MAX_RECONNECT_BACKOFF_MS)
}

#[cfg(test)]
#[path = "../../tests/agent/memory_stream_consumer.rs"]
mod tests;
