//! Integration test: Agent with mock or real MCP (when available).
//! Run with real LLM/MCP: set OPENAI_API_KEY (or ANTHROPIC_API_KEY), optionally start `omni mcp --transport sse --port 3002`,
//! then `cargo test -p omni-agent --test agent_integration -- --ignored`.

use omni_agent::{Agent, AgentConfig, McpServerEntry};

fn default_config() -> AgentConfig {
    AgentConfig {
        inference_url: std::env::var("OMNI_AGENT_INFERENCE_URL")
            .unwrap_or_else(|_| "https://api.openai.com/v1/chat/completions".to_string()),
        model: std::env::var("OMNI_AGENT_MODEL").unwrap_or_else(|_| "gpt-4o-mini".to_string()),
        api_key: None,
        mcp_servers: vec![McpServerEntry {
            name: "local".to_string(),
            url: Some(
                std::env::var("OMNI_MCP_URL")
                    .unwrap_or_else(|_| "http://127.0.0.1:3002/sse".to_string()),
            ),
            command: None,
            args: None,
        }],
        max_tool_rounds: 5,
        ..AgentConfig::default()
    }
}

#[tokio::test]
#[ignore = "requires OPENAI_API_KEY and optional MCP on 3002; run with --ignored"]
async fn test_agent_one_turn_with_llm_and_mcp() {
    let config = default_config();
    if config.resolve_api_key().is_none() {
        eprintln!("skip: no API key");
        return;
    }
    let agent = Agent::from_config(config).await.expect("agent from_config");
    let out = agent
        .run_turn("test-session", "Say hello in one short sentence.")
        .await
        .expect("run_turn");
    assert!(!out.is_empty());
}
