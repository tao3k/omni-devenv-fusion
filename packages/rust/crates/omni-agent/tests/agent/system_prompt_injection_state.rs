use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use omni_agent::{Agent, AgentConfig};

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

#[tokio::test]
async fn upsert_and_inspect_system_prompt_injection_roundtrip() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("system-prompt-injection-roundtrip");
    let xml = r#"
<system_prompt_injection>
  <qa>
    <q>What backend should we use?</q>
    <a>Use valkey for session/memory state.</a>
  </qa>
  <qa>
    <q>What fallback should be avoided?</q>
    <a>Do not use local json fallback in production.</a>
  </qa>
</system_prompt_injection>
"#;

    let snapshot = agent
        .upsert_session_system_prompt_injection_xml(&session_id, xml)
        .await?;
    assert_eq!(snapshot.qa_count, 2);
    assert!(snapshot.xml.contains("<system_prompt_injection>"));

    let loaded = agent
        .inspect_session_system_prompt_injection(&session_id)
        .await
        .expect("snapshot should exist");
    assert_eq!(loaded.qa_count, 2);
    assert!(loaded.xml.contains("<q>What backend should we use?</q>"));
    Ok(())
}

#[tokio::test]
async fn clear_system_prompt_injection_is_idempotent() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("system-prompt-injection-clear");
    let xml = "<qa><q>q</q><a>a</a></qa>";

    let _ = agent
        .upsert_session_system_prompt_injection_xml(&session_id, xml)
        .await?;
    assert!(
        agent
            .clear_session_system_prompt_injection(&session_id)
            .await?
    );
    assert!(
        !agent
            .clear_session_system_prompt_injection(&session_id)
            .await?
    );
    assert!(
        agent
            .inspect_session_system_prompt_injection(&session_id)
            .await
            .is_none()
    );
    Ok(())
}

#[tokio::test]
async fn upsert_system_prompt_injection_rejects_invalid_xml() -> Result<()> {
    let agent = build_agent().await?;
    let session_id = unique_id("system-prompt-injection-invalid");
    let invalid = "<qa><q>question only</q></qa>";

    let error = agent
        .upsert_session_system_prompt_injection_xml(&session_id, invalid)
        .await
        .expect_err("invalid payload should fail");
    assert!(
        error
            .to_string()
            .contains("invalid system prompt injection xml payload")
    );
    Ok(())
}
