#![allow(missing_docs)]

use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use omni_agent::{BoundedSessionStore, ChatMessage, SessionStore};
use serde::Deserialize;

fn live_redis_url() -> Option<String> {
    if let Ok(url) = std::env::var("VALKEY_URL")
        && !url.trim().is_empty()
    {
        return Some(url);
    }
    None
}

fn unique_prefix() -> Result<String> {
    let suffix = SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros();
    Ok(format!("omni-agent:test:session:{suffix}"))
}

#[derive(Debug, Deserialize)]
struct BackupMetadataPayload {
    messages: usize,
    summary_segments: usize,
    saved_at_unix_ms: u64,
}

fn backup_session_id(session_id: &str) -> String {
    format!("__session_context_backup__:{session_id}")
}

fn backup_metadata_session_id(session_id: &str) -> String {
    format!("__session_context_backup_meta__:{session_id}")
}

fn metadata_messages_key(prefix: &str, metadata_session_id: &str) -> String {
    format!("{prefix}:messages:{metadata_session_id}")
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn redis_session_store_roundtrip_across_instances() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };
    let prefix = unique_prefix()?;
    let session_id = "s-live-roundtrip";

    let store_a = SessionStore::new_with_redis(redis_url.clone(), Some(prefix.clone()), Some(120))?;
    store_a
        .append(
            session_id,
            vec![
                ChatMessage {
                    role: "user".to_string(),
                    content: Some("hello".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
                ChatMessage {
                    role: "assistant".to_string(),
                    content: Some("world".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
            ],
        )
        .await?;

    let store_b = SessionStore::new_with_redis(redis_url, Some(prefix), Some(120))?;
    let messages = store_b.get(session_id).await?;
    assert_eq!(messages.len(), 2);
    assert_eq!(messages[0].content.as_deref(), Some("hello"));
    assert_eq!(messages[1].content.as_deref(), Some("world"));
    store_b.clear(session_id).await?;
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn redis_session_store_replace_is_atomic_across_instances() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };
    let prefix = unique_prefix()?;
    let session_id = "s-live-replace";

    let store_a = SessionStore::new_with_redis(redis_url.clone(), Some(prefix.clone()), Some(120))?;
    store_a
        .append(
            session_id,
            vec![
                ChatMessage {
                    role: "user".to_string(),
                    content: Some("before-1".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
                ChatMessage {
                    role: "assistant".to_string(),
                    content: Some("before-2".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
            ],
        )
        .await?;
    store_a
        .replace(
            session_id,
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some("after-replace".to_string()),
                tool_calls: None,
                tool_call_id: None,
                name: Some("replace".to_string()),
            }],
        )
        .await?;

    let store_b = SessionStore::new_with_redis(redis_url, Some(prefix), Some(120))?;
    let messages = store_b.get(session_id).await?;
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].content.as_deref(), Some("after-replace"));
    store_b.clear(session_id).await?;
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn redis_bounded_store_roundtrip_and_drain() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };
    let prefix = unique_prefix()?;
    let session_id = "s-live-window";

    let store_a =
        BoundedSessionStore::new_with_redis(8, redis_url.clone(), Some(prefix.clone()), Some(120))?;
    store_a.append_turn(session_id, "u1", "a1", 1).await?;
    store_a.append_turn(session_id, "u2", "a2", 2).await?;

    let store_b = BoundedSessionStore::new_with_redis(8, redis_url, Some(prefix), Some(120))?;
    let recent = store_b.get_recent_messages(session_id, 8).await?;
    assert_eq!(recent.len(), 4);
    assert_eq!(recent[0].content.as_deref(), Some("u1"));
    assert_eq!(recent[3].content.as_deref(), Some("a2"));

    let stats_before = store_b.get_stats(session_id).await?.expect("stats");
    assert_eq!(stats_before.0, 2);
    assert_eq!(stats_before.1, 3);

    let drained = store_b.drain_oldest_turns(session_id, 2).await?;
    assert_eq!(drained.len(), 4);
    assert_eq!(drained[0].1, "u1");
    assert_eq!(drained[1].1, "a1");

    let stats_after = store_b.get_stats(session_id).await?.expect("stats");
    assert_eq!(stats_after.0, 0);
    store_b.clear(session_id).await?;
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn redis_atomic_reset_snapshot_stores_metadata_as_chat_message_payload() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };
    let prefix = unique_prefix()?;
    let session_id = "s-live-reset-metadata-envelope";
    let backup_session_id = backup_session_id(session_id);
    let metadata_session_id = backup_metadata_session_id(session_id);
    let saved_at_unix_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;

    let bounded =
        BoundedSessionStore::new_with_redis(8, redis_url.clone(), Some(prefix.clone()), Some(120))?;
    bounded.append_turn(session_id, "u1", "a1", 0).await?;

    let stats = bounded
        .atomic_reset_snapshot(
            session_id,
            &backup_session_id,
            &metadata_session_id,
            saved_at_unix_ms,
        )
        .await?;
    assert_eq!(stats, Some((2, 0)));

    let store = SessionStore::new_with_redis(redis_url, Some(prefix), Some(120))?;
    let metadata_messages = store.get(&metadata_session_id).await?;
    assert_eq!(metadata_messages.len(), 1);
    assert_eq!(metadata_messages[0].role, "system");

    let metadata_json = metadata_messages[0]
        .content
        .as_deref()
        .expect("metadata message must include JSON content");
    let metadata: BackupMetadataPayload = serde_json::from_str(metadata_json)?;
    assert_eq!(metadata.messages, 2);
    assert_eq!(metadata.summary_segments, 0);
    assert!(metadata.saved_at_unix_ms >= saved_at_unix_ms);

    store.clear(&metadata_session_id).await?;
    bounded.clear(&backup_session_id).await?;
    bounded.clear(session_id).await?;
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn redis_session_store_reads_legacy_backup_metadata_payload_without_dropping_it() -> Result<()>
{
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };
    let prefix = unique_prefix()?;
    let session_id = "s-live-legacy-metadata-read";
    let metadata_session_id = backup_metadata_session_id(session_id);
    let metadata_key = metadata_messages_key(&prefix, &metadata_session_id);
    let legacy_payload = r#"{"messages":4,"summary_segments":1,"saved_at_unix_ms":1771623456789}"#;

    let client = redis::Client::open(redis_url.as_str())?;
    let mut conn = client.get_multiplexed_async_connection().await?;
    let _: () = redis::cmd("DEL")
        .arg(&metadata_key)
        .query_async(&mut conn)
        .await?;
    let _: () = redis::cmd("RPUSH")
        .arg(&metadata_key)
        .arg(legacy_payload)
        .query_async(&mut conn)
        .await?;

    let store = SessionStore::new_with_redis(redis_url, Some(prefix), Some(120))?;
    let metadata_messages = store.get(&metadata_session_id).await?;
    assert_eq!(metadata_messages.len(), 1);
    assert_eq!(metadata_messages[0].role, "system");

    let metadata_json = metadata_messages[0]
        .content
        .as_deref()
        .expect("legacy payload should be preserved as message content");
    let metadata: BackupMetadataPayload = serde_json::from_str(metadata_json)?;
    assert_eq!(metadata.messages, 4);
    assert_eq!(metadata.summary_segments, 1);
    assert_eq!(metadata.saved_at_unix_ms, 1_771_623_456_789);

    store.clear(&metadata_session_id).await?;
    Ok(())
}
