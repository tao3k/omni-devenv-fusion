use std::collections::HashMap;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use redis::Value;
use tokio::time::{Duration, sleep};

use crate::agent::logging::should_surface_repeated_failure;

use super::{
    MemoryStreamConsumerRuntimeConfig, StreamReadErrorKind, ack_and_record_metrics,
    build_consumer_name, classify_stream_read_error, compute_retry_backoff_ms,
    ensure_consumer_group, parse_xreadgroup_reply, read_stream_events,
    stream_consumer_connection_config, stream_consumer_response_timeout,
};

fn unique_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{prefix}-{nanos}")
}

fn live_redis_url() -> Option<String> {
    for key in ["VALKEY_URL"] {
        if let Ok(url) = std::env::var(key)
            && !url.trim().is_empty()
        {
            return Some(url);
        }
    }
    None
}

#[test]
fn parse_xreadgroup_reply_nil_returns_empty() -> Result<()> {
    let events = parse_xreadgroup_reply(Value::Nil)?;
    assert!(events.is_empty());
    Ok(())
}

#[test]
fn parse_xreadgroup_reply_array_extracts_events() -> Result<()> {
    let reply = Value::Array(vec![Value::Array(vec![
        Value::BulkString(b"omni-agent:stream:memory.events".to_vec()),
        Value::Array(vec![
            Value::Array(vec![
                Value::BulkString(b"1740000000000-0".to_vec()),
                Value::Array(vec![
                    Value::BulkString(b"kind".to_vec()),
                    Value::BulkString(b"turn_stored".to_vec()),
                    Value::BulkString(b"session_id".to_vec()),
                    Value::BulkString(b"telegram:1:1".to_vec()),
                ]),
            ]),
            Value::Array(vec![
                Value::BulkString(b"1740000000001-0".to_vec()),
                Value::Array(vec![
                    Value::BulkString(b"kind".to_vec()),
                    Value::BulkString(b"consolidation_stored".to_vec()),
                ]),
            ]),
        ]),
    ])]);

    let events = parse_xreadgroup_reply(reply)?;
    assert_eq!(events.len(), 2);
    assert_eq!(events[0].id, "1740000000000-0");
    assert_eq!(
        events[0].fields.get("kind").map(String::as_str),
        Some("turn_stored")
    );
    assert_eq!(
        events[0].fields.get("session_id").map(String::as_str),
        Some("telegram:1:1")
    );
    assert_eq!(events[1].id, "1740000000001-0");
    assert_eq!(
        events[1].fields.get("kind").map(String::as_str),
        Some("consolidation_stored")
    );
    Ok(())
}

#[test]
fn parse_xreadgroup_reply_map_extracts_events() -> Result<()> {
    let reply = Value::Map(vec![(
        Value::BulkString(b"omni-agent:stream:memory.events".to_vec()),
        Value::Array(vec![Value::Array(vec![
            Value::BulkString(b"1740000001000-0".to_vec()),
            Value::Map(vec![
                (
                    Value::BulkString(b"kind".to_vec()),
                    Value::BulkString(b"recall_snapshot_updated".to_vec()),
                ),
                (
                    Value::BulkString(b"session_id".to_vec()),
                    Value::BulkString(b"telegram:9:9".to_vec()),
                ),
            ]),
        ])]),
    )]);

    let events = parse_xreadgroup_reply(reply)?;
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].id, "1740000001000-0");
    assert_eq!(
        events[0].fields.get("kind").map(String::as_str),
        Some("recall_snapshot_updated")
    );
    assert_eq!(
        events[0].fields.get("session_id").map(String::as_str),
        Some("telegram:9:9")
    );
    Ok(())
}

#[test]
fn build_consumer_name_keeps_prefix() {
    let name = build_consumer_name("agent-test");
    assert!(name.starts_with("agent-test-"));
}

#[test]
fn classify_stream_read_error_detects_missing_group() {
    let error = anyhow::anyhow!("xreadgroup failed for stream_id=>: NOGROUP No such key");
    let kind = classify_stream_read_error(&error);
    assert_eq!(kind, StreamReadErrorKind::MissingConsumerGroup);
}

#[test]
fn classify_stream_read_error_detects_transport() {
    let error =
        anyhow::anyhow!("xreadgroup failed for stream_id=>: Connection reset by peer while read");
    let kind = classify_stream_read_error(&error);
    assert_eq!(kind, StreamReadErrorKind::Transport);
}

#[test]
fn classify_stream_read_error_falls_back_to_other() {
    let error = anyhow::anyhow!("xreadgroup failed for stream_id=>: some unknown parser issue");
    let kind = classify_stream_read_error(&error);
    assert_eq!(kind, StreamReadErrorKind::Other);
}

#[test]
fn classify_stream_read_error_uses_error_chain() {
    let error = anyhow::anyhow!("timed out while waiting for redis reply")
        .context("xreadgroup failed for stream_id=>");
    let kind = classify_stream_read_error(&error);
    assert_eq!(kind, StreamReadErrorKind::Transport);
}

#[test]
fn stream_consumer_response_timeout_exceeds_block_timeout() {
    let timeout = stream_consumer_response_timeout(1_000);
    assert_eq!(timeout.as_millis(), 1_500);
}

#[test]
fn compute_retry_backoff_ms_exponential_and_capped() {
    assert_eq!(compute_retry_backoff_ms(500, 1), 500);
    assert_eq!(compute_retry_backoff_ms(500, 2), 1_000);
    assert_eq!(compute_retry_backoff_ms(500, 3), 2_000);
    assert_eq!(compute_retry_backoff_ms(500, 20), 30_000);
}

#[test]
fn should_surface_repeated_failure_throttles_noise() {
    assert!(should_surface_repeated_failure(1));
    assert!(should_surface_repeated_failure(2));
    assert!(!should_surface_repeated_failure(3));
    assert!(should_surface_repeated_failure(4));
    assert!(!should_surface_repeated_failure(19));
    assert!(should_surface_repeated_failure(20));
}

#[tokio::test]
#[ignore = "requires running Valkey/Redis on VALKEY_URL"]
async fn memory_stream_consumer_acks_and_tracks_metrics() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        return Ok(());
    };

    let key_prefix = unique_id("omni-agent-memory-stream-consumer");
    let stream_name = "memory.events".to_string();
    let stream_key = format!("{key_prefix}:stream:{stream_name}");
    let stream_consumer_group = "omni-agent-memory-test".to_string();
    let stream_consumer_name = build_consumer_name("agent-test");
    let metrics_global_key = format!("{key_prefix}:metrics:{stream_name}:consumer");
    let metrics_session_prefix = format!("{key_prefix}:metrics:{stream_name}:consumer:session:");
    let config = MemoryStreamConsumerRuntimeConfig {
        redis_url: redis_url.clone(),
        stream_name: stream_name.clone(),
        stream_key: stream_key.clone(),
        stream_consumer_group: stream_consumer_group.clone(),
        stream_consumer_name: stream_consumer_name.clone(),
        stream_consumer_batch_size: 16,
        stream_consumer_block_ms: 100,
        metrics_global_key: metrics_global_key.clone(),
        metrics_session_prefix: metrics_session_prefix.clone(),
        ttl_secs: Some(120),
    };

    let client = redis::Client::open(redis_url.as_str())?;
    let mut connection = client.get_multiplexed_async_connection().await?;
    ensure_consumer_group(&mut connection, &config).await?;

    let event_id: String = redis::cmd("XADD")
        .arg(&stream_key)
        .arg("*")
        .arg("kind")
        .arg("turn_stored")
        .arg("session_id")
        .arg("telegram:test:1")
        .query_async(&mut connection)
        .await?;

    let events = read_stream_events(&mut connection, &config, ">").await?;
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].id, event_id);

    let acked = ack_and_record_metrics(
        &mut connection,
        &config,
        &events[0].id,
        events[0]
            .fields
            .get("kind")
            .map(String::as_str)
            .unwrap_or("unknown"),
        events[0].fields.get("session_id").map(String::as_str),
    )
    .await?;
    assert_eq!(acked, 1);

    let duplicate_ack: u64 = redis::cmd("XACK")
        .arg(&stream_key)
        .arg(&stream_consumer_group)
        .arg(&event_id)
        .query_async(&mut connection)
        .await?;
    assert_eq!(duplicate_ack, 0);

    let global_metrics: HashMap<String, String> = redis::cmd("HGETALL")
        .arg(&metrics_global_key)
        .query_async(&mut connection)
        .await?;
    assert_eq!(
        global_metrics.get("processed_total").map(String::as_str),
        Some("1")
    );
    assert_eq!(
        global_metrics
            .get("processed_kind:turn_stored")
            .map(String::as_str),
        Some("1")
    );

    let session_metrics_key = format!("{metrics_session_prefix}telegram:test:1");
    let session_metrics: HashMap<String, String> = redis::cmd("HGETALL")
        .arg(&session_metrics_key)
        .query_async(&mut connection)
        .await?;
    assert_eq!(
        session_metrics.get("processed_total").map(String::as_str),
        Some("1")
    );
    assert_eq!(
        session_metrics
            .get("processed_kind:turn_stored")
            .map(String::as_str),
        Some("1")
    );

    let _: () = redis::pipe()
        .cmd("DEL")
        .arg(&stream_key)
        .ignore()
        .cmd("DEL")
        .arg(&metrics_global_key)
        .ignore()
        .cmd("DEL")
        .arg(&session_metrics_key)
        .ignore()
        .query_async(&mut connection)
        .await?;

    Ok(())
}

#[tokio::test]
#[ignore = "requires running Valkey/Redis on VALKEY_URL"]
async fn memory_stream_consumer_read_empty_stream_returns_empty() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        return Ok(());
    };

    let key_prefix = unique_id("omni-agent-memory-stream-empty");
    let stream_name = "memory.events".to_string();
    let stream_key = format!("{key_prefix}:stream:{stream_name}");
    let stream_consumer_group = "omni-agent-memory-test".to_string();
    let stream_consumer_name = build_consumer_name("agent-test");
    let config = MemoryStreamConsumerRuntimeConfig {
        redis_url: redis_url.clone(),
        stream_name: stream_name.clone(),
        stream_key: stream_key.clone(),
        stream_consumer_group: stream_consumer_group.clone(),
        stream_consumer_name,
        stream_consumer_batch_size: 8,
        stream_consumer_block_ms: 1_000,
        metrics_global_key: format!("{key_prefix}:metrics:{stream_name}:consumer"),
        metrics_session_prefix: format!("{key_prefix}:metrics:{stream_name}:consumer:session:"),
        ttl_secs: Some(120),
    };

    let client = redis::Client::open(redis_url.as_str())?;
    let connection_config = stream_consumer_connection_config(config.stream_consumer_block_ms);
    let mut connection = client
        .get_multiplexed_async_connection_with_config(&connection_config)
        .await?;
    ensure_consumer_group(&mut connection, &config).await?;

    let events = read_stream_events(&mut connection, &config, ">").await?;
    assert!(events.is_empty(), "expected empty read from idle stream");

    let _: () = redis::cmd("DEL")
        .arg(&stream_key)
        .query_async(&mut connection)
        .await?;

    Ok(())
}

#[tokio::test]
#[ignore = "requires running Valkey/Redis on VALKEY_URL"]
async fn memory_stream_consumer_recovers_after_stream_key_expired() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        return Ok(());
    };

    let key_prefix = unique_id("omni-agent-memory-stream-expired");
    let stream_name = "memory.events".to_string();
    let stream_key = format!("{key_prefix}:stream:{stream_name}");
    let stream_consumer_group = "omni-agent-memory-test".to_string();
    let stream_consumer_name = build_consumer_name("agent-test");
    let metrics_global_key = format!("{key_prefix}:metrics:{stream_name}:consumer");
    let metrics_session_prefix = format!("{key_prefix}:metrics:{stream_name}:consumer:session:");
    let config = MemoryStreamConsumerRuntimeConfig {
        redis_url: redis_url.clone(),
        stream_name: stream_name.clone(),
        stream_key: stream_key.clone(),
        stream_consumer_group: stream_consumer_group.clone(),
        stream_consumer_name: stream_consumer_name.clone(),
        stream_consumer_batch_size: 16,
        stream_consumer_block_ms: 50,
        metrics_global_key: metrics_global_key.clone(),
        metrics_session_prefix: metrics_session_prefix.clone(),
        ttl_secs: Some(120),
    };

    let client = redis::Client::open(redis_url.as_str())?;
    let mut connection = client.get_multiplexed_async_connection().await?;

    ensure_consumer_group(&mut connection, &config).await?;

    let first_event_id: String = redis::cmd("XADD")
        .arg(&stream_key)
        .arg("*")
        .arg("kind")
        .arg("turn_stored")
        .arg("session_id")
        .arg("telegram:test:expire")
        .query_async(&mut connection)
        .await?;

    let first_events = read_stream_events(&mut connection, &config, ">").await?;
    assert_eq!(first_events.len(), 1);
    assert_eq!(first_events[0].id, first_event_id);

    let _: bool = redis::cmd("EXPIRE")
        .arg(&stream_key)
        .arg(1)
        .query_async(&mut connection)
        .await?;
    sleep(Duration::from_millis(1_200)).await;

    let exists_after_expire: i64 = redis::cmd("EXISTS")
        .arg(&stream_key)
        .query_async(&mut connection)
        .await?;
    assert_eq!(exists_after_expire, 0);

    let expired_read_error = read_stream_events(&mut connection, &config, ">")
        .await
        .expect_err("expected NOGROUP after stream key expiration");
    assert_eq!(
        classify_stream_read_error(&expired_read_error),
        StreamReadErrorKind::MissingConsumerGroup
    );

    ensure_consumer_group(&mut connection, &config).await?;

    let recovered_event_id: String = redis::cmd("XADD")
        .arg(&stream_key)
        .arg("*")
        .arg("kind")
        .arg("turn_stored")
        .arg("session_id")
        .arg("telegram:test:expire")
        .query_async(&mut connection)
        .await?;
    let recovered_events = read_stream_events(&mut connection, &config, ">").await?;
    assert_eq!(recovered_events.len(), 1);
    assert_eq!(recovered_events[0].id, recovered_event_id);

    let _: () = redis::pipe()
        .cmd("DEL")
        .arg(&stream_key)
        .ignore()
        .cmd("DEL")
        .arg(&metrics_global_key)
        .ignore()
        .query_async(&mut connection)
        .await?;

    Ok(())
}
