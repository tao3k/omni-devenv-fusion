//! Integration tests: (1) real MCP server on 3002, or (2) in-process mock server.
//!
//! - **Real**: Start `omni mcp --transport sse --port 3002`, then run with
//!   `OMNI_MCP_URL=http://127.0.0.1:3002/sse cargo test -p omni-mcp-client --test streamable_http_integration -- --ignored`
//!   or rely on auto-detect (if port 3002 responds, use it).
//! - **Mock**: When real server is not available, `test_connect_with_mock_server` runs an
//!   in-process MCP server (rmcp StreamableHttpService) and tests the client against it.

use omni_mcp_client::{OmniMcpClient, init_params_omni_server};
use std::sync::Arc;
use std::time::Duration;

const HANDSHAKE_TIMEOUT_SECS: u64 = 30;
#[allow(dead_code)]
const REAL_PORT: u16 = 3002;
const REAL_URL: &str = "http://127.0.0.1:3002/sse";

async fn run_client_assertions(url: &str, handshake_timeout_secs: u64) {
    let params = init_params_omni_server();
    let client = OmniMcpClient::connect_streamable_http(
        url,
        params,
        Some(Duration::from_secs(handshake_timeout_secs)),
    )
    .await
    .unwrap_or_else(|e| panic!("connect to MCP server at {}: {}", url, e));

    let list = client.list_tools(None).await.expect("list_tools");
    assert!(!list.tools.is_empty(), "expected at least one tool");

    let name = list.tools[0].name.to_string();
    let args = if name.contains("echo") || name.contains("mock") {
        Some(serde_json::json!({ "message": "integration test" }))
    } else {
        Some(serde_json::json!({ "name": "integration" }))
    };

    let result = client.call_tool(name, args).await.expect("call_tool");
    assert!(!result.content.is_empty(), "expected non-empty tool result");
}

fn real_server_url() -> String {
    std::env::var("OMNI_MCP_URL").unwrap_or_else(|_| REAL_URL.to_string())
}

/// Returns true if something is listening on the given port (TCP connect).
#[allow(dead_code)]
async fn port_open(port: u16) -> bool {
    tokio::net::TcpStream::connect(format!("127.0.0.1:{}", port))
        .await
        .is_ok()
}

// ========== Test 1: Real server (when 3002 is available) ==========

#[tokio::test]
#[ignore = "run with --ignored when MCP server is on 3002; or use test_connect_with_mock_server"]
async fn test_connect_real_server() {
    let url = real_server_url();
    run_client_assertions(&url, HANDSHAKE_TIMEOUT_SECS).await;
}

// ========== Test 2: Mock server (always runnable) ==========

mod mock {
    use rmcp::ServerHandler;
    use rmcp::model::{
        CallToolRequestParams, CallToolResult, Content, ErrorData, ListToolsResult,
        PaginatedRequestParams, ServerCapabilities, ServerInfo, Tool,
    };
    use rmcp::service::{RequestContext, RoleServer};
    use std::sync::Arc;

    #[derive(Clone, Default)]
    pub struct MockMcpServer;

    impl MockMcpServer {
        fn mock_tool() -> Tool {
            let input_schema = serde_json::json!({
                "type": "object",
                "properties": { "message": { "type": "string" } }
            });
            let map = input_schema.as_object().cloned().unwrap_or_default();
            Tool {
                name: "mock_echo".into(),
                title: Some("Mock Echo".into()),
                description: Some("Echo for integration test".into()),
                input_schema: Arc::new(map),
                output_schema: None,
                annotations: None,
                execution: None,
                icons: None,
                meta: None,
            }
        }
    }

    impl ServerHandler for MockMcpServer {
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
        ) -> impl std::future::Future<Output = Result<ListToolsResult, ErrorData>> + Send + '_
        {
            std::future::ready(Ok(ListToolsResult::with_all_items(vec![Self::mock_tool()])))
        }

        fn call_tool(
            &self,
            request: CallToolRequestParams,
            _context: RequestContext<RoleServer>,
        ) -> impl std::future::Future<Output = Result<CallToolResult, ErrorData>> + Send + '_
        {
            let msg = request
                .arguments
                .as_ref()
                .and_then(|m| m.get("message"))
                .and_then(|v| v.as_str())
                .unwrap_or("ok");
            let content = CallToolResult::success(vec![Content::text(format!("echo: {}", msg))]);
            std::future::ready(Ok(content))
        }
    }
}

#[tokio::test]
async fn test_connect_with_mock_server() {
    use axum::Router;
    use rmcp::transport::streamable_http_server::session::local::LocalSessionManager;
    use rmcp::transport::streamable_http_server::{
        StreamableHttpServerConfig, StreamableHttpService,
    };
    use tokio_util::sync::CancellationToken;

    let ct = CancellationToken::new();
    let service: StreamableHttpService<mock::MockMcpServer, LocalSessionManager> =
        StreamableHttpService::new(
            || Ok(mock::MockMcpServer),
            Arc::new(LocalSessionManager::default()),
            StreamableHttpServerConfig {
                stateful_mode: true,
                sse_keep_alive: None,
                cancellation_token: ct.child_token(),
                ..Default::default()
            },
        );
    let router = Router::new().nest_service("/mcp", service);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("bind");
    let addr = listener.local_addr().expect("local_addr");

    let handle = tokio::spawn({
        let ct = ct.clone();
        async move {
            let _ = axum::serve(listener, router)
                .with_graceful_shutdown(async move { ct.cancelled_owned().await })
                .await;
        }
    });

    let url = format!("http://{}/mcp", addr);
    run_client_assertions(&url, 10).await;

    ct.cancel();
    let _ = handle.await;
}
