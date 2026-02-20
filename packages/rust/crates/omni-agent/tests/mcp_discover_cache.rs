//! MCP discover read-through cache integration tests.

#![allow(missing_docs)]

use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use anyhow::Result;
use axum::Router;
use omni_agent::{McpPoolConnectConfig, connect_pool};
use rmcp::ServerHandler;
use rmcp::model::{
    CallToolRequestParams, CallToolResult, Content, ErrorData, ListToolsResult,
    PaginatedRequestParams, ServerCapabilities, ServerInfo, Tool,
};
use rmcp::service::{RequestContext, RoleServer};
use rmcp::transport::streamable_http_server::session::local::LocalSessionManager;
use rmcp::transport::streamable_http_server::{StreamableHttpServerConfig, StreamableHttpService};

#[derive(Clone, Default)]
struct DiscoverMockServer {
    discover_calls_total: Arc<AtomicUsize>,
}

impl DiscoverMockServer {
    fn discover_tool() -> Tool {
        let input_schema = serde_json::json!({
            "type": "object",
            "properties": {
                "intent": { "type": "string" },
                "limit": { "type": "integer" }
            },
            "required": ["intent"]
        });
        let map = input_schema.as_object().cloned().unwrap_or_default();
        Tool {
            name: "skill.discover".into(),
            title: Some("Skill Discover".into()),
            description: Some("Mock discover tool for cache verification".into()),
            input_schema: Arc::new(map),
            output_schema: None,
            annotations: None,
            execution: None,
            icons: None,
            meta: None,
        }
    }
}

impl ServerHandler for DiscoverMockServer {
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
            Self::discover_tool(),
        ])))
    }

    fn call_tool(
        &self,
        request: CallToolRequestParams,
        _context: RequestContext<RoleServer>,
    ) -> impl std::future::Future<Output = Result<CallToolResult, ErrorData>> + Send + '_ {
        if request.name != "skill.discover" {
            return std::future::ready(Err(ErrorData::internal_error(
                "unsupported tool in discover cache test",
                None,
            )));
        }
        self.discover_calls_total.fetch_add(1, Ordering::SeqCst);
        let intent = request
            .arguments
            .as_ref()
            .and_then(|value| value.get("intent"))
            .and_then(|value| value.as_str())
            .unwrap_or_default();
        let result = CallToolResult::success(vec![Content::text(format!("discover:{intent}"))]);
        std::future::ready(Ok(result))
    }
}

async fn spawn_mock_server_with_discover_counter(
    addr: std::net::SocketAddr,
) -> (tokio::task::JoinHandle<()>, Arc<AtomicUsize>) {
    let discover_calls_total = Arc::new(AtomicUsize::new(0));
    let service: StreamableHttpService<DiscoverMockServer, LocalSessionManager> =
        StreamableHttpService::new(
            {
                let discover_calls_total = discover_calls_total.clone();
                move || {
                    Ok(DiscoverMockServer {
                        discover_calls_total: discover_calls_total.clone(),
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
        discover_calls_total,
    )
}

fn reconnect_test_config() -> McpPoolConnectConfig {
    McpPoolConnectConfig {
        pool_size: 1,
        handshake_timeout_secs: 1,
        connect_retries: 6,
        connect_retry_backoff_ms: 100,
        tool_timeout_secs: 10,
        list_tools_cache_ttl_ms: 1_000,
    }
}

fn env_f64(name: &str, default: f64) -> f64 {
    std::env::var(name)
        .ok()
        .and_then(|value| value.trim().parse::<f64>().ok())
        .filter(|value| *value > 0.0)
        .unwrap_or(default)
}

fn env_usize(name: &str, default: usize) -> usize {
    std::env::var(name)
        .ok()
        .and_then(|value| value.trim().parse::<usize>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(default)
}

fn p95(values: &[f64]) -> f64 {
    if values.is_empty() {
        return 0.0;
    }
    let mut sorted = values.to_vec();
    sorted.sort_by(f64::total_cmp);
    let rank = ((sorted.len() as f64) * 0.95).ceil() as usize;
    let index = rank.saturating_sub(1).min(sorted.len().saturating_sub(1));
    sorted[index]
}

async fn reserve_local_addr() -> std::net::SocketAddr {
    let probe = tokio::net::TcpListener::bind("127.0.0.1:0")
        .await
        .expect("reserve local addr");
    let addr = probe.local_addr().expect("read reserved local addr");
    drop(probe);
    addr
}

#[tokio::test]
#[ignore = "requires live valkey server; set VALKEY_URL"]
async fn discover_calls_use_valkey_read_through_cache_when_configured() -> Result<()> {
    let has_valkey_url = std::env::var("VALKEY_URL")
        .ok()
        .map(|value| !value.trim().is_empty())
        .unwrap_or(false);
    if !has_valkey_url {
        eprintln!("skip: set VALKEY_URL for live cache test");
        return Ok(());
    }

    let addr = reserve_local_addr().await;
    let (handle, discover_calls_total) = spawn_mock_server_with_discover_counter(addr).await;
    let url = format!("http://{addr}/sse");
    let pool = connect_pool(&url, reconnect_test_config())
        .await
        .expect("connect pool");

    let Some(initial_stats) = pool.discover_cache_stats_snapshot() else {
        handle.abort();
        let _ = handle.await;
        eprintln!("skip: discover cache disabled in runtime settings");
        return Ok(());
    };
    assert_eq!(initial_stats.requests_total, 0);

    let iterations = env_usize("OMNI_AGENT_DISCOVER_CACHE_BENCH_ITERATIONS", 12);
    let hit_p95_slo_ms = env_f64("OMNI_AGENT_DISCOVER_CACHE_HIT_P95_MS", 15.0);
    let miss_p95_slo_ms = env_f64("OMNI_AGENT_DISCOVER_CACHE_MISS_P95_MS", 80.0);
    let suffix = SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros();

    let mut miss_latencies_ms = Vec::with_capacity(iterations);
    let mut hit_latencies_ms = Vec::with_capacity(iterations);
    for iteration in 0..iterations {
        let intent = format!("discover-cache-canonicalization-{suffix}-{iteration}");
        let args_miss = serde_json::json!({
            "intent": intent,
            "limit": 5
        });
        let miss_started = Instant::now();
        let first = pool
            .call_tool("skill.discover".to_string(), Some(args_miss))
            .await
            .expect("first discover call");
        miss_latencies_ms.push(miss_started.elapsed().as_secs_f64() * 1000.0);
        assert_ne!(first.is_error, Some(true));

        let args_hit = serde_json::json!({
            "limit": 5,
            "intent": intent
        });
        let hit_started = Instant::now();
        let second = pool
            .call_tool("skill.discover".to_string(), Some(args_hit))
            .await
            .expect("second discover call");
        hit_latencies_ms.push(hit_started.elapsed().as_secs_f64() * 1000.0);
        assert_ne!(second.is_error, Some(true));
    }
    assert_eq!(
        discover_calls_total.load(Ordering::SeqCst),
        iterations,
        "discover backend should only be hit on cache miss requests"
    );

    let miss_p95 = p95(&miss_latencies_ms);
    let hit_p95 = p95(&hit_latencies_ms);
    assert!(
        miss_p95 <= miss_p95_slo_ms,
        "discover cache miss p95 exceeded SLO: miss_p95={miss_p95:.2}ms > miss_p95_slo_ms={miss_p95_slo_ms:.2}ms"
    );
    assert!(
        hit_p95 <= hit_p95_slo_ms,
        "discover cache hit p95 exceeded SLO: hit_p95={hit_p95:.2}ms > hit_p95_slo_ms={hit_p95_slo_ms:.2}ms"
    );

    let iterations_u64 = iterations as u64;
    let stats = pool
        .discover_cache_stats_snapshot()
        .expect("discover cache stats snapshot");
    assert_eq!(stats.requests_total, iterations_u64 * 2);
    assert_eq!(stats.cache_hits, iterations_u64);
    assert_eq!(stats.cache_misses, iterations_u64);
    assert_eq!(stats.cache_writes, iterations_u64);
    assert_eq!(stats.hit_rate_pct, 50.0);

    handle.abort();
    let _ = handle.await;
    Ok(())
}
