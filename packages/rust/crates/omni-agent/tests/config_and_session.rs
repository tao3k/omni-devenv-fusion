//! Unit tests: config and session store (no network).

use omni_agent::{AgentConfig, ChatMessage, ContextBudgetStrategy, MemoryConfig, SessionStore};

#[test]
fn config_resolve_api_key_from_field() {
    let config = AgentConfig {
        api_key: Some("sk-test".to_string()),
        ..Default::default()
    };
    assert_eq!(config.resolve_api_key().as_deref(), Some("sk-test"));
}

#[test]
fn config_default_mcp_servers_empty() {
    let config = AgentConfig::default();
    assert!(config.mcp_servers.is_empty());
    assert_eq!(config.mcp_pool_size, 4);
    assert_eq!(config.mcp_handshake_timeout_secs, 30);
    assert_eq!(config.mcp_connect_retries, 3);
    assert_eq!(config.mcp_connect_retry_backoff_ms, 1_000);
    assert_eq!(config.mcp_tool_timeout_secs, 180);
    assert_eq!(config.mcp_list_tools_cache_ttl_ms, 1_000);
    assert_eq!(config.max_tool_rounds, 30);
    assert_eq!(
        config.context_budget_strategy,
        ContextBudgetStrategy::RecentFirst
    );
}

#[test]
fn memory_config_default_gate_policy_matches_runtime_defaults() {
    let memory = MemoryConfig::default();
    assert_eq!(memory.gate_promote_threshold, 0.78);
    assert_eq!(memory.gate_obsolete_threshold, 0.32);
    assert_eq!(memory.gate_promote_min_usage, 3);
    assert_eq!(memory.gate_obsolete_min_usage, 2);
    assert_eq!(memory.gate_promote_failure_rate_ceiling, 0.25);
    assert_eq!(memory.gate_obsolete_failure_rate_floor, 0.70);
    assert_eq!(memory.gate_promote_min_ttl_score, 0.50);
    assert_eq!(memory.gate_obsolete_max_ttl_score, 0.45);
}

#[tokio::test]
async fn session_append_and_get() -> anyhow::Result<()> {
    let store = SessionStore::new()?;
    store
        .append(
            "s1",
            vec![
                ChatMessage {
                    role: "user".to_string(),
                    content: Some("hi".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
                ChatMessage {
                    role: "assistant".to_string(),
                    content: Some("hello".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
            ],
        )
        .await?;
    let msgs = store.get("s1").await?;
    assert_eq!(msgs.len(), 2);
    assert_eq!(msgs[0].content.as_deref(), Some("hi"));
    assert_eq!(msgs[1].content.as_deref(), Some("hello"));
    Ok(())
}

#[tokio::test]
async fn session_clear() -> anyhow::Result<()> {
    let store = SessionStore::new()?;
    store
        .append(
            "s2",
            vec![ChatMessage {
                role: "user".to_string(),
                content: Some("x".to_string()),
                tool_calls: None,
                tool_call_id: None,
                name: None,
            }],
        )
        .await?;
    assert_eq!(store.get("s2").await?.len(), 1);
    store.clear("s2").await?;
    assert!(store.get("s2").await?.is_empty());
    Ok(())
}

#[tokio::test]
async fn session_replace_overwrites_existing_messages() -> anyhow::Result<()> {
    let store = SessionStore::new()?;
    store
        .append(
            "s3",
            vec![
                ChatMessage {
                    role: "user".to_string(),
                    content: Some("first".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
                ChatMessage {
                    role: "assistant".to_string(),
                    content: Some("reply-first".to_string()),
                    tool_calls: None,
                    tool_call_id: None,
                    name: None,
                },
            ],
        )
        .await?;
    store
        .replace(
            "s3",
            vec![ChatMessage {
                role: "system".to_string(),
                content: Some("replaced".to_string()),
                tool_calls: None,
                tool_call_id: None,
                name: Some("replace-test".to_string()),
            }],
        )
        .await?;
    let messages = store.get("s3").await?;
    assert_eq!(messages.len(), 1);
    assert_eq!(messages[0].content.as_deref(), Some("replaced"));
    Ok(())
}

#[tokio::test]
async fn session_replace_empty_clears_existing_messages() -> anyhow::Result<()> {
    let store = SessionStore::new()?;
    store
        .append(
            "s4",
            vec![ChatMessage {
                role: "user".to_string(),
                content: Some("to-clear".to_string()),
                tool_calls: None,
                tool_call_id: None,
                name: None,
            }],
        )
        .await?;
    assert_eq!(store.get("s4").await?.len(), 1);
    store.replace("s4", Vec::new()).await?;
    assert!(store.get("s4").await?.is_empty());
    Ok(())
}
