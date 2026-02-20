#![allow(missing_docs)]

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use omni_agent::{Agent, AgentConfig, MemoryConfig};

fn base_agent_config(memory: MemoryConfig) -> AgentConfig {
    AgentConfig {
        inference_url: "http://127.0.0.1:4000/v1/chat/completions".to_string(),
        model: "test-model".to_string(),
        memory: Some(memory),
        ..AgentConfig::default()
    }
}

async fn build_agent_with_optional_session_valkey_url(
    mut memory: MemoryConfig,
    session_valkey_url: Option<&str>,
) -> anyhow::Result<Agent> {
    if let Some(url) = session_valkey_url {
        memory.persistence_valkey_url = Some(url.to_string());
    }
    let config = base_agent_config(memory);
    Agent::from_config(config).await
}

fn state_paths(memory_path: &str, table_name: &str) -> (PathBuf, PathBuf) {
    let root = Path::new(memory_path);
    (
        root.join(format!("{table_name}.episodes.json")),
        root.join(format!("{table_name}.q_table.json")),
    )
}

#[tokio::test]
async fn local_memory_backend_initializes_without_valkey() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        persistence_backend: "local".to_string(),
        ..MemoryConfig::default()
    };
    let agent = build_agent_with_optional_session_valkey_url(memory, None).await;
    assert!(
        agent.is_ok(),
        "local memory backend should initialize without valkey"
    );
}

#[tokio::test]
async fn strict_valkey_memory_backend_fails_when_unreachable() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        persistence_backend: "valkey".to_string(),
        ..MemoryConfig::default()
    };
    match build_agent_with_optional_session_valkey_url(memory, Some("redis://127.0.0.1:1/0")).await
    {
        Ok(_) => panic!("strict valkey backend should fail when redis is unreachable"),
        Err(err) => {
            assert!(
                err.to_string()
                    .contains("strict valkey memory backend failed during startup"),
                "unexpected error: {err}"
            );
        }
    }
}

#[tokio::test]
async fn auto_memory_backend_without_valkey_url_persists_locally() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "auto_local".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "auto".to_string(),
        ..MemoryConfig::default()
    };
    let (episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    let agent = build_agent_with_optional_session_valkey_url(memory, None)
        .await
        .expect("auto backend without redis url should initialize");

    agent
        .append_turn_for_session("auto-local-session", "u1", "a1")
        .await
        .expect("append turn should succeed");

    assert!(
        episodes_path.exists(),
        "auto backend without redis url should persist local episode snapshot"
    );
    assert!(
        q_path.exists(),
        "auto backend without redis url should persist local q-table snapshot"
    );
}

#[tokio::test]
async fn auto_memory_backend_with_unreachable_valkey_fails_by_default() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "auto_valkey".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "auto".to_string(),
        ..MemoryConfig::default()
    };
    let (episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    match build_agent_with_optional_session_valkey_url(memory, Some("redis://127.0.0.1:1/0")).await
    {
        Ok(_) => panic!("auto backend with valkey url should fail startup by default"),
        Err(err) => {
            assert!(
                err.to_string()
                    .contains("strict valkey memory backend failed during startup"),
                "unexpected error: {err}"
            );
        }
    }

    assert!(
        !episodes_path.exists(),
        "failed strict startup should not create local episode snapshot files"
    );
    assert!(
        !q_path.exists(),
        "failed strict startup should not create local q-table snapshot files"
    );
}

#[tokio::test]
async fn auto_memory_backend_can_relax_strict_startup_without_local_fallback() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "auto_valkey_relaxed".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "auto".to_string(),
        persistence_strict_startup: Some(false),
        ..MemoryConfig::default()
    };
    let (episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    let agent = build_agent_with_optional_session_valkey_url(memory, Some("redis://127.0.0.1:1/0"))
        .await
        .expect("auto backend should allow relaxed startup when explicitly configured");

    agent
        .append_turn_for_session("auto-valkey-relaxed-session", "u1", "a1")
        .await
        .expect("append turn should still succeed with relaxed startup");

    assert!(
        !episodes_path.exists(),
        "auto backend with configured valkey should not silently fall back to local episode snapshot"
    );
    assert!(
        !q_path.exists(),
        "auto backend with configured valkey should not silently fall back to local q-table snapshot"
    );
}

#[tokio::test]
async fn auto_memory_backend_with_invalid_valkey_url_fails_fast() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        persistence_backend: "auto".to_string(),
        ..MemoryConfig::default()
    };
    match build_agent_with_optional_session_valkey_url(memory, Some("http://127.0.0.1:6379/0"))
        .await
    {
        Ok(_) => panic!("auto backend should fail when valkey url is invalid"),
        Err(err) => {
            assert!(
                err.to_string()
                    .contains("invalid redis url for memory persistence"),
                "unexpected error: {err}"
            );
        }
    }
}

#[tokio::test]
async fn memory_turn_store_succeeds_when_embedding_endpoint_is_unavailable() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "embed_endpoint_down".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        embedding_base_url: Some("http://127.0.0.1:3302".to_string()),
        embedding_model: Some("ollama/qwen3-embedding:0.6b".to_string()),
        embedding_dim: 1024,
        persistence_backend: "local".to_string(),
        ..MemoryConfig::default()
    };
    let (episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    let agent = build_agent_with_optional_session_valkey_url(memory, None)
        .await
        .expect("agent should initialize when embedding endpoint is unavailable");

    let started = Instant::now();
    agent
        .append_turn_for_session("embed-fallback-session", "u1", "a1")
        .await
        .expect("turn store should fall back and succeed without embedding service");
    assert!(
        started.elapsed() < Duration::from_secs(10),
        "embedding fallback should not block turn store unexpectedly"
    );

    assert!(
        episodes_path.exists(),
        "local memory snapshot should still be persisted when embedding endpoint is down"
    );
    assert!(
        q_path.exists(),
        "local q-table snapshot should still be persisted when embedding endpoint is down"
    );
}

#[tokio::test]
async fn memory_decay_policy_applies_on_configured_interval() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let table_name = "decay_interval".to_string();
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name,
        persistence_backend: "local".to_string(),
        decay_enabled: true,
        decay_every_turns: 1,
        decay_factor: 0.5,
        ..MemoryConfig::default()
    };
    let (_episodes_path, q_path) = state_paths(&memory.path, &memory.table_name);
    let agent = build_agent_with_optional_session_valkey_url(memory, None)
        .await
        .expect("agent should initialize for decay test");

    agent
        .append_turn_for_session("decay-session", "u1", "a1")
        .await
        .expect("append turn should succeed");

    let raw = std::fs::read_to_string(&q_path).expect("q-table snapshot should exist");
    let q_values: HashMap<String, f32> =
        serde_json::from_str(&raw).expect("q-table json should parse");
    assert_eq!(q_values.len(), 1, "expected one q-table entry");
    let q = q_values.values().next().copied().unwrap_or_default();
    assert!(
        q < 0.6,
        "decay should reduce first-turn q value below non-decay baseline (q={q})"
    );
}
