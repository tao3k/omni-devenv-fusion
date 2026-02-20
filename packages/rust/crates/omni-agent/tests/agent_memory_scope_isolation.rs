#![allow(missing_docs)]

use std::collections::HashSet;
use std::fs;
use std::path::Path;

use anyhow::Result;
use omni_agent::{Agent, AgentConfig, MemoryConfig};

const SESSION_A: &str = "telegram:-200:1001";
const SESSION_B: &str = "telegram:-200:1002";

fn build_agent_config(memory: MemoryConfig) -> AgentConfig {
    AgentConfig {
        inference_url: "http://127.0.0.1:4000/v1/chat/completions".to_string(),
        model: "test-model".to_string(),
        memory: Some(memory),
        ..AgentConfig::default()
    }
}

fn episodes_path(memory_path: &str, table_name: &str) -> String {
    Path::new(memory_path)
        .join(format!("{table_name}.episodes.json"))
        .to_string_lossy()
        .to_string()
}

#[tokio::test]
async fn turn_memory_persistence_is_scoped_by_session_id() -> Result<()> {
    let temp_dir = tempfile::tempdir()?;
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name: "scope_isolation".to_string(),
        persistence_backend: "local".to_string(),
        ..MemoryConfig::default()
    };
    let file_path = episodes_path(&memory.path, &memory.table_name);

    let agent = Agent::from_config(build_agent_config(memory)).await?;
    agent
        .append_turn_for_session(SESSION_A, "session A question", "session A answer")
        .await?;
    agent
        .append_turn_for_session(SESSION_B, "session B question", "session B answer")
        .await?;

    let raw = fs::read_to_string(&file_path)?;
    let payload: serde_json::Value = serde_json::from_str(&raw)?;
    let episodes = payload
        .as_array()
        .expect("episodes persistence payload should be an array");
    assert!(
        episodes.len() >= 2,
        "expected at least two stored episodes, got {}",
        episodes.len()
    );

    let mut scopes: HashSet<String> = HashSet::new();
    for episode in episodes {
        let scope = episode
            .get("scope")
            .and_then(serde_json::Value::as_str)
            .expect("every persisted episode should contain scope")
            .to_string();
        scopes.insert(scope);
    }

    assert!(
        scopes.contains(SESSION_A),
        "session A scope should exist in persisted episodes"
    );
    assert!(
        scopes.contains(SESSION_B),
        "session B scope should exist in persisted episodes"
    );

    Ok(())
}
