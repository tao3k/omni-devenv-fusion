use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use serde_json::json;
use std::collections::HashMap;

use super::{
    Agent, EMBEDDING_SOURCE_EMBEDDING, EMBEDDING_SOURCE_EMBEDDING_REPAIRED,
    EMBEDDING_SOURCE_UNKNOWN, MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME, SessionMemoryRecallDecision,
    SessionMemoryRecallSnapshot, snapshot_session_id,
};
use crate::config::AgentConfig;
use crate::session::{ChatMessage, SessionStore};

fn unique_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{prefix}-{nanos}")
}

async fn build_agent() -> Result<Agent> {
    let mut config = AgentConfig::default();
    config.inference_url = "http://127.0.0.1:4000/v1/chat/completions".to_string();
    config.memory = None;
    config.window_max_turns = None;
    config.consolidation_threshold_turns = None;
    Agent::from_config(config).await
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

async fn build_agent_with_shared_redis(redis_url: &str, key_prefix: &str) -> Result<Agent> {
    let mut config = AgentConfig::default();
    config.inference_url = "http://127.0.0.1:4000/v1/chat/completions".to_string();
    config.memory = None;
    config.window_max_turns = None;
    config.consolidation_threshold_turns = None;

    let session = SessionStore::new_with_redis(
        redis_url.to_string(),
        Some(key_prefix.to_string()),
        Some(120),
    )?;

    Agent::from_config_with_session_backends_for_test(config, session, None).await
}

async fn stream_len(redis_url: &str, key_prefix: &str, stream_name: &str) -> Result<usize> {
    let client = redis::Client::open(redis_url)?;
    let mut conn = client.get_multiplexed_async_connection().await?;
    let key = format!("{key_prefix}:stream:{stream_name}");
    let len: usize = redis::cmd("XLEN").arg(key).query_async(&mut conn).await?;
    Ok(len)
}

async fn stream_metrics(
    redis_url: &str,
    key_prefix: &str,
    stream_name: &str,
    session_id: Option<&str>,
) -> Result<HashMap<String, String>> {
    let client = redis::Client::open(redis_url)?;
    let mut conn = client.get_multiplexed_async_connection().await?;
    let key = match session_id {
        Some(id) if !id.trim().is_empty() => {
            format!("{key_prefix}:metrics:{stream_name}:session:{}", id.trim())
        }
        _ => format!("{key_prefix}:metrics:{stream_name}"),
    };
    let metrics: HashMap<String, String> = redis::cmd("HGETALL")
        .arg(key)
        .query_async(&mut conn)
        .await?;
    Ok(metrics)
}

fn sample_snapshot(created_at_unix_ms: u64) -> SessionMemoryRecallSnapshot {
    SessionMemoryRecallSnapshot {
        created_at_unix_ms,
        query_tokens: 12,
        recall_feedback_bias: -0.18,
        embedding_source: EMBEDDING_SOURCE_EMBEDDING,
        k1: 10,
        k2: 3,
        lambda: 0.35,
        min_score: 0.10,
        max_context_chars: 1024,
        budget_pressure: 0.48,
        window_pressure: 0.62,
        effective_budget_tokens: Some(4096),
        active_turns_estimate: 15,
        summary_segment_count: 1,
        recalled_total: 8,
        recalled_selected: 3,
        recalled_injected: 2,
        context_chars_injected: 480,
        best_score: Some(0.82),
        weakest_score: Some(0.21),
        pipeline_duration_ms: 17,
        decision: SessionMemoryRecallDecision::Injected,
    }
}

#[tokio::test]
async fn record_and_inspect_memory_recall_snapshot_roundtrip() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-roundtrip");

    let first = sample_snapshot(1_739_900_000_100);
    let second = SessionMemoryRecallSnapshot {
        created_at_unix_ms: 1_739_900_000_200,
        decision: SessionMemoryRecallDecision::Skipped,
        recalled_injected: 0,
        context_chars_injected: 0,
        ..first
    };

    agent
        .record_memory_recall_snapshot(&session_id, first)
        .await;
    agent
        .record_memory_recall_snapshot(&session_id, second)
        .await;

    let inspected = agent
        .inspect_memory_recall_snapshot(&session_id)
        .await
        .expect("snapshot should be persisted");
    assert_eq!(inspected, second);

    let storage_messages = agent
        .session
        .get(&snapshot_session_id(&session_id))
        .await
        .expect("storage session should be readable");
    assert_eq!(
        storage_messages.len(),
        1,
        "storage should keep only latest snapshot"
    );

    Ok(())
}

#[tokio::test]
async fn inspect_memory_recall_snapshot_normalizes_unknown_embedding_source() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-unknown-embedding");
    let storage_session_id = snapshot_session_id(&session_id);

    let payload = json!({
        "created_at_unix_ms": 1739900000888u64,
        "query_tokens": 7,
        "recall_feedback_bias": 0.12,
        "embedding_source": "vendor-x",
        "k1": 8,
        "k2": 2,
        "lambda": 0.44,
        "min_score": 0.15,
        "max_context_chars": 700,
        "budget_pressure": 1.08,
        "window_pressure": 0.23,
        "effective_budget_tokens": 3200,
        "active_turns_estimate": 20,
        "summary_segment_count": 0,
        "recalled_total": 5,
        "recalled_selected": 2,
        "recalled_injected": 1,
        "context_chars_injected": 120,
        "best_score": 0.51,
        "weakest_score": 0.14,
        "pipeline_duration_ms": 9,
        "decision": "injected"
    })
    .to_string();

    agent
        .session
        .append(
            &storage_session_id,
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some(payload),
                tool_calls: None,
                tool_call_id: None,
                name: Some(MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME.to_string()),
            }],
        )
        .await?;

    let inspected = agent
        .inspect_memory_recall_snapshot(&session_id)
        .await
        .expect("snapshot should parse from persisted payload");
    assert_eq!(inspected.embedding_source, EMBEDDING_SOURCE_UNKNOWN);
    assert_eq!(inspected.decision, SessionMemoryRecallDecision::Injected);

    Ok(())
}

#[tokio::test]
async fn inspect_memory_recall_snapshot_keeps_embedding_repaired_source() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-embedding-repaired");
    let storage_session_id = snapshot_session_id(&session_id);

    let payload = json!({
        "created_at_unix_ms": 1739900001888u64,
        "query_tokens": 9,
        "recall_feedback_bias": -0.35,
        "embedding_source": "embedding_repaired",
        "k1": 8,
        "k2": 2,
        "lambda": 0.40,
        "min_score": 0.12,
        "max_context_chars": 900,
        "budget_pressure": 0.75,
        "window_pressure": 0.31,
        "effective_budget_tokens": 3600,
        "active_turns_estimate": 24,
        "summary_segment_count": 0,
        "recalled_total": 6,
        "recalled_selected": 2,
        "recalled_injected": 1,
        "context_chars_injected": 180,
        "best_score": 0.61,
        "weakest_score": 0.22,
        "pipeline_duration_ms": 11,
        "decision": "injected"
    })
    .to_string();

    agent
        .session
        .append(
            &storage_session_id,
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some(payload),
                tool_calls: None,
                tool_call_id: None,
                name: Some(MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME.to_string()),
            }],
        )
        .await?;

    let inspected = agent
        .inspect_memory_recall_snapshot(&session_id)
        .await
        .expect("snapshot should parse from persisted payload");
    assert_eq!(
        inspected.embedding_source,
        EMBEDDING_SOURCE_EMBEDDING_REPAIRED
    );

    Ok(())
}

#[tokio::test]
async fn inspect_memory_recall_snapshot_ignores_invalid_payload() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-invalid");
    let storage_session_id = snapshot_session_id(&session_id);

    agent
        .session
        .append(
            &storage_session_id,
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some("not-json".to_string()),
                tool_calls: None,
                tool_call_id: None,
                name: Some(MEMORY_RECALL_SNAPSHOT_MESSAGE_NAME.to_string()),
            }],
        )
        .await?;

    assert!(
        agent
            .inspect_memory_recall_snapshot(&session_id)
            .await
            .is_none(),
        "invalid snapshot payload should not panic and should be treated as absent"
    );

    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn memory_recall_snapshot_is_shared_across_agent_instances_with_valkey() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };

    let key_prefix = unique_id("memory-recall-cross-instance");
    let session_id = unique_id("memory-recall-shared-session");
    let agent_a = build_agent_with_shared_redis(&redis_url, &key_prefix).await?;
    let agent_b = build_agent_with_shared_redis(&redis_url, &key_prefix).await?;

    let snapshot = sample_snapshot(1_739_900_111_222);
    agent_a
        .record_memory_recall_snapshot(&session_id, snapshot)
        .await;

    let inspected = agent_b
        .inspect_memory_recall_snapshot(&session_id)
        .await
        .expect("second agent instance should load snapshot via shared valkey backend");
    assert_eq!(inspected, snapshot);

    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn record_memory_recall_snapshot_publishes_stream_event() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };

    let key_prefix = unique_id("memory-recall-stream");
    let session_id = unique_id("memory-recall-stream-session");
    let agent = build_agent_with_shared_redis(&redis_url, &key_prefix).await?;
    let snapshot = sample_snapshot(1_739_900_123_456);
    agent
        .record_memory_recall_snapshot(&session_id, snapshot)
        .await;

    assert_eq!(
        stream_len(&redis_url, &key_prefix, "memory.events").await?,
        1
    );
    let global_metrics = stream_metrics(&redis_url, &key_prefix, "memory.events", None).await?;
    assert_eq!(
        global_metrics.get("events_total").map(String::as_str),
        Some("1")
    );
    assert_eq!(
        global_metrics
            .get("kind:recall_snapshot_updated")
            .map(String::as_str),
        Some("1")
    );
    let scoped_metrics =
        stream_metrics(&redis_url, &key_prefix, "memory.events", Some(&session_id)).await?;
    assert_eq!(
        scoped_metrics.get("events_total").map(String::as_str),
        Some("1")
    );
    assert_eq!(
        scoped_metrics
            .get("kind:recall_snapshot_updated")
            .map(String::as_str),
        Some("1")
    );
    Ok(())
}
