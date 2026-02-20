use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use std::collections::HashMap;

use super::Agent;
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

#[tokio::test]
async fn persist_and_load_memory_recall_feedback_roundtrip() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-feedback-roundtrip");

    agent
        .persist_memory_recall_feedback_bias(&session_id, -0.45)
        .await;
    let loaded = agent.load_memory_recall_feedback_bias(&session_id).await;
    assert_eq!(loaded, Some(-0.45));

    agent
        .persist_memory_recall_feedback_bias(&session_id, 0.72)
        .await;
    let loaded = agent.load_memory_recall_feedback_bias(&session_id).await;
    assert_eq!(loaded, Some(0.72));
    Ok(())
}

#[tokio::test]
async fn load_memory_recall_feedback_clamps_out_of_range_payload() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-feedback-clamp");
    let storage_session_id = format!("__session_memory_recall_feedback__:{session_id}");

    let payload = r#"{"bias":9.9,"updated_at_unix_ms":1739900000000}"#.to_string();
    agent
        .session
        .append(
            &storage_session_id,
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some(payload),
                tool_calls: None,
                tool_call_id: None,
                name: Some("agent.memory.recall.feedback".to_string()),
            }],
        )
        .await?;

    assert_eq!(
        agent.load_memory_recall_feedback_bias(&session_id).await,
        Some(1.0)
    );
    Ok(())
}

#[tokio::test]
async fn load_memory_recall_feedback_ignores_invalid_payload() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("memory-recall-feedback-invalid");
    let storage_session_id = format!("__session_memory_recall_feedback__:{session_id}");

    agent
        .session
        .append(
            &storage_session_id,
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some("not-json".to_string()),
                tool_calls: None,
                tool_call_id: None,
                name: Some("agent.memory.recall.feedback".to_string()),
            }],
        )
        .await?;
    assert!(
        agent
            .load_memory_recall_feedback_bias(&session_id)
            .await
            .is_none()
    );
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn memory_recall_feedback_is_shared_across_agent_instances_with_valkey() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };

    let key_prefix = unique_id("memory-recall-feedback-cross-instance");
    let session_id = unique_id("memory-recall-feedback-shared");
    let agent_a = build_agent_with_shared_redis(&redis_url, &key_prefix).await?;
    let agent_b = build_agent_with_shared_redis(&redis_url, &key_prefix).await?;

    agent_a
        .persist_memory_recall_feedback_bias(&session_id, -0.33)
        .await;
    assert_eq!(
        agent_b.load_memory_recall_feedback_bias(&session_id).await,
        Some(-0.33)
    );
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn persist_memory_recall_feedback_publishes_stream_event() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };
    let key_prefix = unique_id("memory-recall-feedback-stream");
    let session_id = unique_id("memory-recall-feedback-stream-session");
    let agent = build_agent_with_shared_redis(&redis_url, &key_prefix).await?;

    agent
        .persist_memory_recall_feedback_bias(&session_id, 0.42)
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
            .get("kind:recall_feedback_bias_updated")
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
            .get("kind:recall_feedback_bias_updated")
            .map(String::as_str),
        Some("1")
    );
    Ok(())
}
