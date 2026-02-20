#![allow(missing_docs)]

use std::collections::HashMap;
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use omni_agent::{Agent, AgentConfig, MemoryConfig, SessionStore};
use omni_memory::{Episode, MemoryGatePolicy, MemoryGateVerdict, MemoryUtilityLedger};

fn base_agent_config(memory: MemoryConfig) -> AgentConfig {
    AgentConfig {
        inference_url: "http://127.0.0.1:4000/v1/chat/completions".to_string(),
        model: "test-model".to_string(),
        memory: Some(memory),
        ..AgentConfig::default()
    }
}

fn state_paths(memory_path: &str, table_name: &str) -> (std::path::PathBuf, std::path::PathBuf) {
    let root = Path::new(memory_path);
    (
        root.join(format!("{table_name}.episodes.json")),
        root.join(format!("{table_name}.q_table.json")),
    )
}

fn read_episodes(path: &Path) -> Vec<Episode> {
    let raw = std::fs::read_to_string(path).expect("episodes snapshot should exist");
    serde_json::from_str(&raw).expect("episodes snapshot should be valid json")
}

fn read_q_table(path: &Path) -> HashMap<String, f32> {
    let raw = std::fs::read_to_string(path).expect("q-table snapshot should exist");
    serde_json::from_str(&raw).expect("q-table snapshot should be valid json")
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

fn unique_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{prefix}-{nanos}")
}

async fn build_agent_with_shared_redis(
    memory: MemoryConfig,
    redis_url: &str,
    key_prefix: &str,
) -> Result<Agent> {
    let config = base_agent_config(memory);
    let session = SessionStore::new_with_redis(
        redis_url.to_string(),
        Some(key_prefix.to_string()),
        Some(120),
    )?;
    Agent::from_config_with_session_backends_for_test(config, session, None).await
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
async fn repeated_success_turns_reuse_episode_and_reach_promote_threshold() -> Result<()> {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "memory_gate_promote".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "local".to_string(),
        ..MemoryConfig::default()
    };
    let expected_gate_promote_threshold = memory.gate_promote_threshold;
    let expected_gate_obsolete_threshold = memory.gate_obsolete_threshold;
    let expected_gate_promote_min_usage = memory.gate_promote_min_usage;
    let expected_gate_obsolete_min_usage = memory.gate_obsolete_min_usage;
    let (episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    let agent = Agent::from_config(base_agent_config(memory))
        .await
        .expect("agent should initialize");

    let session_id = "memory-gate-promote-session";
    for _ in 0..4 {
        agent
            .append_turn_with_tool_count_for_session(
                session_id,
                "compare valkey and postgres tradeoffs",
                "analysis completed successfully",
                6,
            )
            .await
            .expect("append turn should succeed");
    }

    let status = agent.inspect_memory_runtime_status();
    assert_eq!(
        status.episodes_total,
        Some(1),
        "same intent in one session should reuse a single episode for stable gate utility"
    );
    assert_eq!(
        status.q_values_total,
        Some(1),
        "reused episode should keep one q-table entry"
    );
    assert_eq!(
        status.gate_promote_threshold,
        Some(expected_gate_promote_threshold)
    );
    assert_eq!(
        status.gate_obsolete_threshold,
        Some(expected_gate_obsolete_threshold)
    );
    assert_eq!(
        status.gate_promote_min_usage,
        Some(expected_gate_promote_min_usage)
    );
    assert_eq!(
        status.gate_obsolete_min_usage,
        Some(expected_gate_obsolete_min_usage)
    );

    let episodes = read_episodes(&episodes_path);
    assert_eq!(episodes.len(), 1);
    let episode = &episodes[0];
    assert_eq!(episode.scope_key(), session_id);
    assert!(episode.success_count >= 4);
    assert!(episode.failure_count == 0);

    let ledger = MemoryUtilityLedger::from_episode(episode, 0.96, 0.64, 0.78);
    let decision = MemoryGatePolicy::default().evaluate(&ledger, vec![], vec![], vec![]);
    assert_eq!(
        decision.verdict,
        MemoryGateVerdict::Promote,
        "reused successful episode should cross promotion threshold"
    );

    let q_values = read_q_table(&q_path);
    assert_eq!(q_values.len(), 1);
    Ok(())
}

#[tokio::test]
async fn repeated_failure_turns_trigger_obsolete_and_purge_episode() -> Result<()> {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "memory_gate_obsolete".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "local".to_string(),
        ..MemoryConfig::default()
    };
    let (episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    let agent = Agent::from_config(base_agent_config(memory))
        .await
        .expect("agent should initialize");

    let session_id = "memory-gate-obsolete-session";
    let user_intent = "sync valuecell repo";
    let assistant_failure = "error: timed out while fetching remote";

    agent
        .append_turn_with_tool_count_for_session(session_id, user_intent, assistant_failure, 0)
        .await
        .expect("first failure turn should succeed");
    let after_first = agent.inspect_memory_runtime_status();
    assert_eq!(after_first.episodes_total, Some(1));
    assert_eq!(after_first.q_values_total, Some(1));

    agent
        .append_turn_with_tool_count_for_session(session_id, user_intent, assistant_failure, 0)
        .await
        .expect("second failure turn should succeed");
    let after_second = agent.inspect_memory_runtime_status();
    assert_eq!(
        after_second.episodes_total,
        Some(0),
        "gate obsolete decision should purge repeatedly failing episode"
    );
    assert_eq!(
        after_second.q_values_total,
        Some(0),
        "purged episode should also remove q-table entry"
    );

    let episodes = read_episodes(&episodes_path);
    assert!(
        episodes.is_empty(),
        "persisted episodes should be empty after purge"
    );
    let q_values = read_q_table(&q_path);
    assert!(
        q_values.is_empty(),
        "persisted q-table should be empty after purge"
    );
    Ok(())
}

#[tokio::test]
async fn custom_gate_policy_can_purge_after_single_failure_turn() -> Result<()> {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "memory_gate_custom_single_failure_purge".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "local".to_string(),
        gate_obsolete_threshold: 1.0,
        gate_obsolete_min_usage: 1,
        gate_obsolete_failure_rate_floor: 0.0,
        gate_obsolete_max_ttl_score: 1.0,
        ..MemoryConfig::default()
    };
    let agent = Agent::from_config(base_agent_config(memory))
        .await
        .expect("agent should initialize");

    agent
        .append_turn_with_tool_count_for_session(
            "memory-gate-custom-single-failure",
            "investigate flaky webhook timeout",
            "error: upstream request timed out",
            0,
        )
        .await?;

    let status = agent.inspect_memory_runtime_status();
    assert_eq!(
        status.episodes_total,
        Some(0),
        "custom gate policy should allow obsolete purge after first failure turn"
    );
    assert_eq!(status.q_values_total, Some(0));
    assert_eq!(status.gate_obsolete_threshold, Some(1.0));
    assert_eq!(status.gate_obsolete_min_usage, Some(1));
    assert_eq!(status.gate_obsolete_failure_rate_floor, Some(0.0));
    assert_eq!(status.gate_obsolete_max_ttl_score, Some(1.0));
    Ok(())
}

#[tokio::test]
async fn custom_gate_policy_can_delay_obsolete_after_repeated_failures() -> Result<()> {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "memory_gate_custom_delay_obsolete".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "local".to_string(),
        gate_obsolete_min_usage: 8,
        ..MemoryConfig::default()
    };
    let agent = Agent::from_config(base_agent_config(memory))
        .await
        .expect("agent should initialize");

    let session_id = "memory-gate-custom-delay";
    for _ in 0..2 {
        agent
            .append_turn_with_tool_count_for_session(
                session_id,
                "sync indexer snapshots",
                "error: embedding service unavailable",
                0,
            )
            .await?;
    }

    let status = agent.inspect_memory_runtime_status();
    assert_eq!(
        status.episodes_total,
        Some(1),
        "high obsolete_min_usage should keep failing episode until enough evidence accumulates"
    );
    assert_eq!(status.q_values_total, Some(1));
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn memory_gate_events_are_emitted_into_valkey_stream_metrics() -> Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };

    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = unique_id("memory_gate_stream");
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "local".to_string(),
        ..MemoryConfig::default()
    };

    let key_prefix = unique_id("memory-gate-stream");
    let session_id = unique_id("memory-gate-stream-session");
    let agent = build_agent_with_shared_redis(memory, &redis_url, &key_prefix)
        .await
        .expect("agent should initialize with shared valkey session backend");

    agent
        .append_turn_with_tool_count_for_session(
            &session_id,
            "retry flaky pipeline",
            "error: timed out while calling upstream",
            0,
        )
        .await?;
    agent
        .append_turn_with_tool_count_for_session(
            &session_id,
            "retry flaky pipeline",
            "error: timed out while calling upstream",
            0,
        )
        .await?;

    let global_metrics = stream_metrics(&redis_url, &key_prefix, "memory.events", None).await?;
    assert_eq!(
        global_metrics
            .get("kind:memory_gate_event")
            .map(String::as_str),
        Some("2"),
        "memory gate evaluation should emit one stream event per turn"
    );
    assert_eq!(
        global_metrics.get("kind:turn_stored").map(String::as_str),
        Some("2"),
        "turn store events should remain observable for memory gate debugging"
    );

    let scoped_metrics =
        stream_metrics(&redis_url, &key_prefix, "memory.events", Some(&session_id)).await?;
    assert_eq!(
        scoped_metrics
            .get("kind:memory_gate_event")
            .map(String::as_str),
        Some("2")
    );
    assert_eq!(
        scoped_metrics.get("kind:turn_stored").map(String::as_str),
        Some("2")
    );
    Ok(())
}
