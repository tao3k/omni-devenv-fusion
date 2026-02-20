#![allow(missing_docs)]

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use anyhow::Result;
use axum::Router;
use omni_agent::{Agent, AgentConfig, McpServerEntry, MemoryConfig};
use rmcp::ServerHandler;
use rmcp::model::{
    CallToolRequestParams, CallToolResult, Content, ErrorData, ListToolsResult,
    PaginatedRequestParams, ServerCapabilities, ServerInfo, Tool,
};
use rmcp::service::{RequestContext, RoleServer};
use rmcp::transport::streamable_http_server::session::local::LocalSessionManager;
use rmcp::transport::streamable_http_server::{StreamableHttpServerConfig, StreamableHttpService};

#[derive(Clone)]
struct MockBridgeServer {
    recorded_arguments: Arc<std::sync::Mutex<Vec<serde_json::Value>>>,
    reject_metadata_once_for_flaky: Arc<AtomicBool>,
}

impl MockBridgeServer {
    fn tool(name: &str, description: &str) -> Tool {
        let input_schema = serde_json::json!({
            "type": "object",
            "additionalProperties": true,
        });
        let map = input_schema.as_object().cloned().unwrap_or_default();
        Tool {
            name: name.to_string().into(),
            title: Some(name.to_string().into()),
            description: Some(description.to_string().into()),
            input_schema: Arc::new(map),
            output_schema: None,
            annotations: None,
            execution: None,
            icons: None,
            meta: None,
        }
    }
}

impl ServerHandler for MockBridgeServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            ..Default::default()
        }
    }

    fn list_tools(
        &self,
        _request: Option<PaginatedRequestParams>,
        _context: RequestContext<RoleServer>,
    ) -> impl std::future::Future<Output = Result<ListToolsResult, ErrorData>> + Send + '_ {
        std::future::ready(Ok(ListToolsResult::with_all_items(vec![
            Self::tool("bridge.echo", "Echo JSON arguments"),
            Self::tool("bridge.flaky", "Reject first metadata-rich call"),
        ])))
    }

    fn call_tool(
        &self,
        request: CallToolRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> impl std::future::Future<Output = Result<CallToolResult, ErrorData>> + Send + '_ {
        let args_json = request
            .arguments
            .clone()
            .map(serde_json::Value::Object)
            .unwrap_or_else(|| serde_json::json!({}));

        self.recorded_arguments
            .lock()
            .expect("recorded arguments lock poisoned")
            .push(args_json.clone());

        match request.name.as_ref() {
            "bridge.flaky" => {
                let has_metadata = request
                    .arguments
                    .as_ref()
                    .and_then(|value| value.get("_omni"))
                    .is_some();
                if has_metadata
                    && self
                        .reject_metadata_once_for_flaky
                        .swap(false, Ordering::SeqCst)
                {
                    return std::future::ready(Err(ErrorData::internal_error(
                        "metadata not accepted for first attempt",
                        None,
                    )));
                }
                std::future::ready(Ok(CallToolResult::success(vec![Content::text(
                    "fallback-ok".to_string(),
                )])))
            }
            _ => {
                let payload = serde_json::to_string(&args_json)
                    .unwrap_or_else(|_| "{\"error\":\"serialize\"}".to_string());
                std::future::ready(Ok(CallToolResult::success(vec![Content::text(payload)])))
            }
        }
    }
}

async fn reserve_local_addr() -> std::net::SocketAddr {
    let probe = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("reserve local addr");
    let addr = probe.local_addr().expect("read reserved local addr");
    drop(probe);
    addr
}

async fn spawn_mock_bridge_server(
    addr: std::net::SocketAddr,
) -> (
    tokio::task::JoinHandle<()>,
    Arc<std::sync::Mutex<Vec<serde_json::Value>>>,
) {
    let recorded_arguments = Arc::new(std::sync::Mutex::new(Vec::new()));
    let reject_metadata_once_for_flaky = Arc::new(AtomicBool::new(true));

    let service: StreamableHttpService<MockBridgeServer, LocalSessionManager> =
        StreamableHttpService::new(
            {
                let recorded_arguments = recorded_arguments.clone();
                let reject_metadata_once_for_flaky = reject_metadata_once_for_flaky.clone();
                move || {
                    Ok(MockBridgeServer {
                        recorded_arguments: recorded_arguments.clone(),
                        reject_metadata_once_for_flaky: reject_metadata_once_for_flaky.clone(),
                    })
                }
            },
            Arc::new(LocalSessionManager::default()),
            StreamableHttpServerConfig {
                stateful_mode: true,
                sse_keep_alive: None,
                ..Default::default()
            },
        );

    let router = Router::new().nest_service("/sse", service);
    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("bind mock mcp listener");

    (
        tokio::spawn(async move {
            let _ = axum::serve(listener, router).await;
        }),
        recorded_arguments,
    )
}

fn base_config(mcp_url: String) -> AgentConfig {
    AgentConfig {
        inference_url: "http://127.0.0.1:4000/v1/chat/completions".to_string(),
        model: "test-model".to_string(),
        mcp_servers: vec![McpServerEntry {
            name: "mock".to_string(),
            url: Some(mcp_url),
            command: None,
            args: None,
        }],
        mcp_handshake_timeout_secs: 2,
        mcp_connect_retries: 2,
        mcp_connect_retry_backoff_ms: 50,
        mcp_tool_timeout_secs: 15,
        mcp_list_tools_cache_ttl_ms: 100,
        max_tool_rounds: 3,
        ..AgentConfig::default()
    }
}

#[tokio::test]
async fn graph_shortcut_includes_typed_injection_snapshot_metadata() -> Result<()> {
    let addr = reserve_local_addr().await;
    let (server_handle, recorded_arguments) = spawn_mock_bridge_server(addr).await;
    let mcp_url = format!("http://{addr}/sse");

    let temp_dir = tempfile::tempdir()?;
    let memory = MemoryConfig {
        path: temp_dir.path().join("memory").to_string_lossy().to_string(),
        table_name: "agent_injection_snapshot".to_string(),
        persistence_backend: "local".to_string(),
        embedding_base_url: Some("http://127.0.0.1:9".to_string()),
        ..MemoryConfig::default()
    };

    let mut config = base_config(mcp_url);
    config.memory = Some(memory);
    config.window_max_turns = Some(1);
    config.consolidation_threshold_turns = Some(1);
    config.consolidation_take_turns = 1;
    config.consolidation_async = false;
    config.summary_max_segments = 32;

    let agent = Agent::from_config(config).await?;
    let session_id = "telegram:-100200:42";

    for index in 0..18 {
        agent
            .append_turn_for_session(
                session_id,
                &format!("historical question {index}"),
                &format!("historical answer {index}"),
            )
            .await?;
    }

    let huge_answer = "X".repeat(12_000);
    let xml =
        format!("<qa><q>critical runtime policy</q><a>{huge_answer}</a><source>ops</source></qa>");
    let _ = agent
        .upsert_session_system_prompt_injection_xml(session_id, &xml)
        .await?;

    let output = agent
        .run_turn(session_id, r#"graph bridge.echo {"task":"snapshot-test"}"#)
        .await?;

    let payload: serde_json::Value = serde_json::from_str(&output)?;
    assert_eq!(payload["task"], "snapshot-test");

    let metadata = payload
        .get("_omni")
        .and_then(serde_json::Value::as_object)
        .expect("shortcut metadata should be attached under _omni");
    assert_eq!(
        metadata
            .get("workflow_mode")
            .and_then(serde_json::Value::as_str),
        Some("graph")
    );

    let session_context = metadata
        .get("session_context")
        .and_then(serde_json::Value::as_object)
        .expect("session context metadata should exist");
    assert!(
        session_context
            .get("snapshot_id")
            .and_then(serde_json::Value::as_str)
            .is_some(),
        "snapshot_id must exist"
    );
    assert!(
        session_context
            .get("dropped_block_ids")
            .and_then(serde_json::Value::as_array)
            .is_some_and(|items| !items.is_empty()),
        "expected dropped blocks when summary segments exceed max_blocks"
    );
    assert!(
        session_context
            .get("truncated_block_ids")
            .and_then(serde_json::Value::as_array)
            .is_some_and(|items| !items.is_empty()),
        "expected at least one truncated block when payload exceeds max_chars"
    );
    assert!(
        session_context
            .get("role_mix_profile_id")
            .and_then(serde_json::Value::as_str)
            .is_some(),
        "role-mix profile must be attached for multi-domain shortcut injection"
    );
    assert!(
        session_context
            .get("role_mix_roles")
            .and_then(serde_json::Value::as_array)
            .is_some_and(|items| !items.is_empty()),
        "role-mix role list must be present in shortcut metadata"
    );

    let captured = recorded_arguments
        .lock()
        .expect("recorded arguments lock poisoned")
        .clone();
    assert!(
        !captured.is_empty(),
        "mock MCP should capture at least one tool call"
    );

    server_handle.abort();
    let _ = server_handle.await;
    Ok(())
}

#[tokio::test]
async fn omega_shortcut_retries_without_metadata_after_bridge_error() -> Result<()> {
    let addr = reserve_local_addr().await;
    let (server_handle, recorded_arguments) = spawn_mock_bridge_server(addr).await;
    let mcp_url = format!("http://{addr}/sse");

    let config = base_config(mcp_url);
    let agent = Agent::from_config(config).await?;

    let output = agent
        .run_turn(
            "telegram:-100300:7",
            r#"omega bridge.flaky {"task":"fallback-check"}"#,
        )
        .await?;

    assert_eq!(output, "fallback-ok");

    let captured = recorded_arguments
        .lock()
        .expect("recorded arguments lock poisoned")
        .clone();
    assert_eq!(
        captured.len(),
        2,
        "omega fallback should perform exactly two attempts"
    );

    assert!(
        captured[0].get("_omni").is_some(),
        "first attempt should include omega metadata"
    );
    assert!(
        captured[1].get("_omni").is_none(),
        "fallback attempt should strip metadata for compatibility"
    );

    server_handle.abort();
    let _ = server_handle.await;
    Ok(())
}
