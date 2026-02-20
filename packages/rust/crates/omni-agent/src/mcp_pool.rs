//! MCP client pool for concurrent tool calls.
//!
//! Multiple Telegram groups (or gateway requests) can call tools concurrently.
//! A single MCP client uses a Mutex, serializing all calls. This pool holds
//! N clients and uses round-robin so up to N tool calls run in parallel.

mod discover_cache;

use std::sync::OnceLock;
use std::sync::atomic::{AtomicU64, AtomicUsize, Ordering};
use std::time::{Duration, Instant};

use anyhow::{Result, anyhow};
use discover_cache::DiscoverReadThroughCache;
use omni_mcp_client::{OmniMcpClient, init_params_omni_server};
use rmcp::model::{CallToolResult, ListToolsResult, PaginatedRequestParams};
use serde::Serialize;
use tokio::sync::{Mutex, RwLock, oneshot};
use tokio::task::JoinSet;

/// Default pool size for concurrent MCP tool calls (e.g. multiple Telegram groups).
const DEFAULT_POOL_SIZE: usize = 4;
const DEFAULT_HANDSHAKE_TIMEOUT_SECS: u64 = 30;
const DEFAULT_CONNECT_RETRIES: u32 = 3;
const DEFAULT_CONNECT_RETRY_BACKOFF_MS: u64 = 1_000;
const DEFAULT_TOOL_TIMEOUT_SECS: u64 = 180;
const DEFAULT_HEALTH_PROBE_TIMEOUT_MS: u64 = 1_500;
const DEFAULT_HEALTH_READY_POLL_MS: u64 = 200;
const DEFAULT_INFLIGHT_LOG_INTERVAL_SECS: u64 = 5;
const DEFAULT_SLOW_CALL_WARN_MS: u128 = 2_000;
const DEFAULT_LIST_TOOLS_CACHE_TTL_MS: u64 = 1_000;
const DEFAULT_LIST_TOOLS_CACHE_STATS_LOG_INTERVAL_SECS: u64 = 60;
const DEFAULT_DISCOVER_CACHE_STATS_LOG_INTERVAL_SECS: u64 = 60;
const MAX_LIST_TOOLS_CACHE_TTL_MS: u64 = 60_000;
const MAX_CONNECT_RETRY_BACKOFF_MS: u64 = 30_000;
const MAX_HANDSHAKE_TIMEOUT_SECS: u64 = 120;
const MAX_HEALTH_READY_WAIT_SECS: u64 = 180;
static HEALTH_PROBE_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

#[derive(Clone)]
struct ListToolsCacheEntry {
    value: ListToolsResult,
    cached_at: Instant,
}

/// Snapshot of Rust-side `tools/list` cache behavior in MCP client pool.
#[derive(Debug, Clone, Serialize)]
pub struct McpToolsListCacheStatsSnapshot {
    pub ttl_ms: u64,
    pub requests_total: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub cache_refreshes: u64,
    pub hit_rate_pct: f64,
}

/// Snapshot of discover call-cache behavior in MCP pool.
#[derive(Debug, Clone, Serialize)]
pub struct McpDiscoverCacheStatsSnapshot {
    pub backend: String,
    pub ttl_secs: u64,
    pub requests_total: u64,
    pub cache_hits: u64,
    pub cache_misses: u64,
    pub cache_writes: u64,
    pub hit_rate_pct: f64,
}

/// MCP pool connection settings.
#[derive(Debug, Clone, Copy)]
pub struct McpPoolConnectConfig {
    pub pool_size: usize,
    pub handshake_timeout_secs: u64,
    pub connect_retries: u32,
    pub connect_retry_backoff_ms: u64,
    pub tool_timeout_secs: u64,
    pub list_tools_cache_ttl_ms: u64,
}

impl Default for McpPoolConnectConfig {
    fn default() -> Self {
        Self {
            pool_size: DEFAULT_POOL_SIZE,
            handshake_timeout_secs: DEFAULT_HANDSHAKE_TIMEOUT_SECS,
            connect_retries: DEFAULT_CONNECT_RETRIES,
            connect_retry_backoff_ms: DEFAULT_CONNECT_RETRY_BACKOFF_MS,
            tool_timeout_secs: DEFAULT_TOOL_TIMEOUT_SECS,
            list_tools_cache_ttl_ms: DEFAULT_LIST_TOOLS_CACHE_TTL_MS,
        }
    }
}

/// Pool of MCP clients for concurrent tool calls.
pub struct McpClientPool {
    server_url: String,
    connect_config: McpPoolConnectConfig,
    clients: RwLock<Vec<std::sync::Arc<OmniMcpClient>>>,
    reconnect_locks: Vec<Mutex<()>>,
    pool_size: usize,
    next: AtomicUsize,
    tool_timeout: Duration,
    list_tools_cache: RwLock<Option<ListToolsCacheEntry>>,
    list_tools_cache_lock: Mutex<()>,
    list_tools_cache_ttl: Duration,
    list_tools_cache_hits: AtomicU64,
    list_tools_cache_misses: AtomicU64,
    list_tools_cache_refreshes: AtomicU64,
    list_tools_cache_last_log_at: Mutex<Instant>,
    list_tools_cache_stats_log_interval: Duration,
    discover_cache: Option<std::sync::Arc<DiscoverReadThroughCache>>,
    discover_cache_hits: AtomicU64,
    discover_cache_misses: AtomicU64,
    discover_cache_writes: AtomicU64,
    discover_cache_last_log_at: Mutex<Instant>,
    discover_cache_stats_log_interval: Duration,
}

impl McpClientPool {
    /// Connect to MCP server and create a pool of clients.
    pub async fn connect(url: &str, config: McpPoolConnectConfig) -> Result<Self> {
        if config.pool_size == 0 {
            return Err(anyhow!("MCP pool_size must be greater than 0"));
        }
        let retries = config.connect_retries.max(1);
        let mut clients = Vec::with_capacity(config.pool_size);
        let first_client = connect_one_client_with_retry(url, config, retries, 0).await?;
        clients.push(first_client);

        if config.pool_size > 1 {
            let mut connect_tasks = JoinSet::new();
            for client_index in 1..config.pool_size {
                let url = url.to_string();
                connect_tasks.spawn(async move {
                    connect_one_client_with_retry(&url, config, retries, client_index).await
                });
            }

            while let Some(task_result) = connect_tasks.join_next().await {
                match task_result {
                    Ok(Ok(client)) => clients.push(client),
                    Ok(Err(error)) => {
                        connect_tasks.abort_all();
                        return Err(error);
                    }
                    Err(join_error) => {
                        connect_tasks.abort_all();
                        return Err(anyhow!("MCP connect task join failed: {join_error}"));
                    }
                }
            }
        }
        let cache_stats_log_interval =
            Duration::from_secs(DEFAULT_LIST_TOOLS_CACHE_STATS_LOG_INTERVAL_SECS);
        let initial_cache_stats_log_at = Instant::now()
            .checked_sub(cache_stats_log_interval)
            .unwrap_or_else(Instant::now);
        let discover_cache = match DiscoverReadThroughCache::from_runtime() {
            Ok(cache) => cache.map(std::sync::Arc::new),
            Err(error) => {
                tracing::warn!(
                    event = "mcp.pool.discover_cache.init_failed",
                    error = %error,
                    "discover read-through cache init failed; continuing without cache"
                );
                None
            }
        };
        if let Some(cache) = discover_cache.as_ref() {
            let runtime = cache.runtime_info();
            tracing::info!(
                event = "mcp.pool.discover_cache.enabled",
                backend = runtime.backend,
                ttl_secs = runtime.ttl_secs,
                "discover read-through cache enabled"
            );
        }
        let discover_cache_stats_log_interval =
            Duration::from_secs(DEFAULT_DISCOVER_CACHE_STATS_LOG_INTERVAL_SECS);
        let initial_discover_cache_stats_log_at = Instant::now()
            .checked_sub(discover_cache_stats_log_interval)
            .unwrap_or_else(Instant::now);
        Ok(Self {
            server_url: url.to_string(),
            connect_config: config,
            clients: RwLock::new(clients.into_iter().map(std::sync::Arc::new).collect()),
            reconnect_locks: (0..config.pool_size).map(|_| Mutex::new(())).collect(),
            pool_size: config.pool_size,
            next: AtomicUsize::new(0),
            tool_timeout: Duration::from_secs(config.tool_timeout_secs.max(1)),
            list_tools_cache: RwLock::new(None),
            list_tools_cache_lock: Mutex::new(()),
            list_tools_cache_ttl: list_tools_cache_ttl_from_config(config.list_tools_cache_ttl_ms),
            list_tools_cache_hits: AtomicU64::new(0),
            list_tools_cache_misses: AtomicU64::new(0),
            list_tools_cache_refreshes: AtomicU64::new(0),
            list_tools_cache_last_log_at: Mutex::new(initial_cache_stats_log_at),
            list_tools_cache_stats_log_interval: cache_stats_log_interval,
            discover_cache,
            discover_cache_hits: AtomicU64::new(0),
            discover_cache_misses: AtomicU64::new(0),
            discover_cache_writes: AtomicU64::new(0),
            discover_cache_last_log_at: Mutex::new(initial_discover_cache_stats_log_at),
            discover_cache_stats_log_interval,
        })
    }

    /// List tools (uses first client).
    pub async fn list_tools(
        &self,
        params: Option<PaginatedRequestParams>,
    ) -> Result<ListToolsResult> {
        if params.is_some() {
            return self.list_tools_uncached(params).await;
        }

        if let Some(cached) = self.get_cached_list_tools().await {
            self.record_list_tools_cache_hit();
            tracing::debug!(
                event = "mcp.pool.tools_list.cache_hit",
                ttl_ms = self.list_tools_cache_ttl.as_millis(),
                "mcp tools/list served from cache"
            );
            return Ok(cached);
        }

        let _cache_guard = self.list_tools_cache_lock.lock().await;
        if let Some(cached) = self.get_cached_list_tools().await {
            self.record_list_tools_cache_hit();
            tracing::debug!(
                event = "mcp.pool.tools_list.cache_hit_after_wait",
                ttl_ms = self.list_tools_cache_ttl.as_millis(),
                "mcp tools/list served from cache after waiting for in-flight refresh"
            );
            return Ok(cached);
        }

        self.record_list_tools_cache_miss();
        let fresh = self.list_tools_uncached(None).await?;
        self.update_list_tools_cache(&fresh).await;
        self.record_list_tools_cache_refresh();
        Ok(fresh)
    }

    async fn list_tools_uncached(
        &self,
        params: Option<PaginatedRequestParams>,
    ) -> Result<ListToolsResult> {
        let start_idx = self.next.fetch_add(1, Ordering::Relaxed) % self.pool_size;
        let mut attempt_errors: Vec<String> = Vec::with_capacity(self.pool_size);
        for offset in 0..self.pool_size {
            let client_index = (start_idx + offset) % self.pool_size;
            match self.list_tools_once(client_index, params.clone()).await {
                Ok(output) => {
                    if offset > 0 {
                        tracing::info!(
                            event = "mcp.pool.tools_list.fallback_client_used",
                            start_index = start_idx,
                            client_index,
                            previous_failures = offset,
                            "mcp tools/list succeeded via fallback client"
                        );
                    }
                    return Ok(output);
                }
                Err(error) => {
                    let error_class = classify_transport_error(&error);
                    if error_class.retryable {
                        tracing::warn!(
                            event = "mcp.pool.call.retry.transport_error",
                            operation = "tools/list",
                            start_index = start_idx,
                            client_index,
                            error_class = error_class.kind,
                            error = %error,
                            "recoverable mcp tools/list transport error; attempting reconnect + retry"
                        );
                        match self
                            .reconnect_client(client_index, "tools/list transport error")
                            .await
                        {
                            Ok(()) => {
                                match self.list_tools_once(client_index, params.clone()).await {
                                    Ok(output) => return Ok(output),
                                    Err(retry_error) => {
                                        let retry_error_class =
                                            classify_transport_error(&retry_error);
                                        tracing::warn!(
                                            event = "mcp.pool.call.failed_after_retry",
                                            operation = "tools/list",
                                            start_index = start_idx,
                                            client_index,
                                            error_class = retry_error_class.kind,
                                            first_error = %error,
                                            retry_error = %retry_error,
                                            "mcp tools/list retry failed; attempting next pool client"
                                        );
                                        attempt_errors.push(format!(
                                        "client_index={client_index},stage=retry,error_class={},error={}",
                                        retry_error_class.kind,
                                        retry_error
                                    ));
                                    }
                                }
                            }
                            Err(reconnect_error) => {
                                let reconnect_error_class =
                                    classify_transport_error(&reconnect_error);
                                tracing::warn!(
                                    event = "mcp.pool.client.reconnect.failed",
                                    operation = "tools/list",
                                    start_index = start_idx,
                                    client_index,
                                    error_class = reconnect_error_class.kind,
                                    error = %reconnect_error,
                                    "mcp tools/list reconnect failed; attempting next pool client"
                                );
                                attempt_errors.push(format!(
                                    "client_index={client_index},stage=reconnect,error_class={},error={}",
                                    reconnect_error_class.kind,
                                    reconnect_error
                                ));
                            }
                        }
                    } else {
                        tracing::warn!(
                            event = "mcp.pool.call.failed",
                            operation = "tools/list",
                            start_index = start_idx,
                            client_index,
                            error_class = error_class.kind,
                            error = %error,
                            "mcp tools/list failed on client; attempting next pool client"
                        );
                        attempt_errors.push(format!(
                            "client_index={client_index},stage=call,error_class={},error={}",
                            error_class.kind, error
                        ));
                    }
                }
            }
        }

        let joined_errors = if attempt_errors.is_empty() {
            "no_attempts_recorded".to_string()
        } else {
            attempt_errors.join(" | ")
        };
        Err(anyhow!(
            "MCP tools/list failed on all clients (pool_size={}, start_index={}, attempts={})",
            self.pool_size,
            start_idx,
            joined_errors
        ))
    }

    async fn get_cached_list_tools(&self) -> Option<ListToolsResult> {
        let cache = self.list_tools_cache.read().await;
        let entry = cache.as_ref()?;
        if entry.cached_at.elapsed() <= self.list_tools_cache_ttl {
            return Some(entry.value.clone());
        }
        None
    }

    async fn update_list_tools_cache(&self, fresh: &ListToolsResult) {
        let mut cache = self.list_tools_cache.write().await;
        *cache = Some(ListToolsCacheEntry {
            value: fresh.clone(),
            cached_at: Instant::now(),
        });
    }

    async fn invalidate_list_tools_cache(&self) {
        let mut cache = self.list_tools_cache.write().await;
        *cache = None;
    }

    fn record_list_tools_cache_hit(&self) {
        self.list_tools_cache_hits.fetch_add(1, Ordering::Relaxed);
        self.maybe_log_list_tools_cache_stats();
    }

    fn record_list_tools_cache_miss(&self) {
        self.list_tools_cache_misses.fetch_add(1, Ordering::Relaxed);
        self.maybe_log_list_tools_cache_stats();
    }

    fn record_list_tools_cache_refresh(&self) {
        self.list_tools_cache_refreshes
            .fetch_add(1, Ordering::Relaxed);
        self.maybe_log_list_tools_cache_stats();
    }

    fn maybe_log_list_tools_cache_stats(&self) {
        let Ok(mut last_log_at) = self.list_tools_cache_last_log_at.try_lock() else {
            return;
        };
        if last_log_at.elapsed() < self.list_tools_cache_stats_log_interval {
            return;
        }
        *last_log_at = Instant::now();

        let snapshot = self.tools_list_cache_stats_snapshot();

        tracing::info!(
            event = "mcp.pool.tools_list.cache.stats",
            requests_total = snapshot.requests_total,
            cache_hits = snapshot.cache_hits,
            cache_misses = snapshot.cache_misses,
            cache_refreshes = snapshot.cache_refreshes,
            hit_rate_pct = snapshot.hit_rate_pct,
            ttl_ms = snapshot.ttl_ms,
            "mcp tools/list cache stats"
        );
    }

    /// Return a cheap point-in-time snapshot of `tools/list` cache behavior.
    pub fn tools_list_cache_stats_snapshot(&self) -> McpToolsListCacheStatsSnapshot {
        let hits = self.list_tools_cache_hits.load(Ordering::Relaxed);
        let misses = self.list_tools_cache_misses.load(Ordering::Relaxed);
        let refreshes = self.list_tools_cache_refreshes.load(Ordering::Relaxed);
        let requests = hits.saturating_add(misses);
        let hit_rate_pct = if requests == 0 {
            0.0
        } else {
            ((hits as f64 * 10_000.0) / requests as f64).round() / 100.0
        };
        McpToolsListCacheStatsSnapshot {
            ttl_ms: self.list_tools_cache_ttl.as_millis() as u64,
            requests_total: requests,
            cache_hits: hits,
            cache_misses: misses,
            cache_refreshes: refreshes,
            hit_rate_pct,
        }
    }

    /// Return discover cache stats when discover read-through cache is enabled.
    pub fn discover_cache_stats_snapshot(&self) -> Option<McpDiscoverCacheStatsSnapshot> {
        let cache = self.discover_cache.as_ref()?;
        let runtime = cache.runtime_info();
        let hits = self.discover_cache_hits.load(Ordering::Relaxed);
        let misses = self.discover_cache_misses.load(Ordering::Relaxed);
        let writes = self.discover_cache_writes.load(Ordering::Relaxed);
        let requests = hits.saturating_add(misses);
        let hit_rate_pct = if requests == 0 {
            0.0
        } else {
            ((hits as f64 * 10_000.0) / requests as f64).round() / 100.0
        };
        Some(McpDiscoverCacheStatsSnapshot {
            backend: runtime.backend.to_string(),
            ttl_secs: runtime.ttl_secs,
            requests_total: requests,
            cache_hits: hits,
            cache_misses: misses,
            cache_writes: writes,
            hit_rate_pct,
        })
    }

    async fn get_cached_discover_call(&self, cache_key: &str) -> Option<CallToolResult> {
        let Some(cache) = self.discover_cache.as_ref() else {
            return None;
        };
        match cache.get(cache_key).await {
            Ok(Some(cached)) => {
                self.discover_cache_hits.fetch_add(1, Ordering::Relaxed);
                tracing::debug!(
                    event = "mcp.pool.discover_cache.hit",
                    cache_key,
                    "discover call served from cache"
                );
                self.maybe_log_discover_cache_stats();
                Some(cached)
            }
            Ok(None) => {
                self.discover_cache_misses.fetch_add(1, Ordering::Relaxed);
                tracing::debug!(
                    event = "mcp.pool.discover_cache.miss",
                    cache_key,
                    "discover call cache miss"
                );
                self.maybe_log_discover_cache_stats();
                None
            }
            Err(error) => {
                self.discover_cache_misses.fetch_add(1, Ordering::Relaxed);
                tracing::warn!(
                    event = "mcp.pool.discover_cache.get_failed",
                    cache_key,
                    error = %error,
                    "discover call cache read failed; continuing without cache"
                );
                self.maybe_log_discover_cache_stats();
                None
            }
        }
    }

    async fn store_discover_call_cache(&self, cache_key: &str, output: &CallToolResult) {
        if matches!(output.is_error, Some(true)) {
            return;
        }
        let Some(cache) = self.discover_cache.as_ref() else {
            return;
        };
        match cache.set(cache_key, output).await {
            Ok(()) => {
                self.discover_cache_writes.fetch_add(1, Ordering::Relaxed);
                tracing::debug!(
                    event = "mcp.pool.discover_cache.write",
                    cache_key,
                    "discover call cached"
                );
            }
            Err(error) => {
                tracing::warn!(
                    event = "mcp.pool.discover_cache.write_failed",
                    cache_key,
                    error = %error,
                    "discover call cache write failed"
                );
            }
        }
        self.maybe_log_discover_cache_stats();
    }

    fn maybe_log_discover_cache_stats(&self) {
        if self.discover_cache.is_none() {
            return;
        }
        let Ok(mut last_log_at) = self.discover_cache_last_log_at.try_lock() else {
            return;
        };
        if last_log_at.elapsed() < self.discover_cache_stats_log_interval {
            return;
        }
        *last_log_at = Instant::now();

        let Some(snapshot) = self.discover_cache_stats_snapshot() else {
            return;
        };

        tracing::info!(
            event = "mcp.pool.discover_cache.stats",
            backend = %snapshot.backend,
            ttl_secs = snapshot.ttl_secs,
            requests_total = snapshot.requests_total,
            cache_hits = snapshot.cache_hits,
            cache_misses = snapshot.cache_misses,
            cache_writes = snapshot.cache_writes,
            hit_rate_pct = snapshot.hit_rate_pct,
            "mcp discover cache stats"
        );
    }

    /// Call a tool; round-robin picks a client so concurrent calls use different clients.
    pub async fn call_tool(
        &self,
        name: String,
        arguments: Option<serde_json::Value>,
    ) -> Result<CallToolResult> {
        let discover_cache_key = self
            .discover_cache
            .as_ref()
            .and_then(|cache| cache.build_cache_key(name.as_str(), arguments.as_ref()));
        if let Some(cache_key) = discover_cache_key.as_deref()
            && let Some(cached) = self.get_cached_discover_call(cache_key).await
        {
            return Ok(cached);
        }

        let idx = self.next.fetch_add(1, Ordering::Relaxed) % self.pool_size;
        let operation = format!("tools/call:{name}");
        let call_result = match self
            .call_tool_once(idx, name.clone(), arguments.clone())
            .await
        {
            Ok(output) => Ok(output),
            Err(error) if should_retry_transport_error(&error) => {
                tracing::warn!(
                    event = "mcp.pool.call.retry.transport_error",
                    operation = %operation,
                    client_index = idx,
                    error = %error,
                    "recoverable mcp tools/call transport error; attempting reconnect + retry"
                );
                self.reconnect_client(idx, "tools/call transport error")
                    .await?;
                match self.call_tool_once(idx, name, arguments).await {
                    Ok(output) => Ok(output),
                    Err(retry_error) => {
                        tracing::error!(
                            event = "mcp.pool.call.failed_after_retry",
                            operation = %operation,
                            client_index = idx,
                            first_error = %error,
                            retry_error = %retry_error,
                            "mcp tools/call failed after reconnect retry"
                        );
                        Err(anyhow!(
                            "MCP tools/call failed after reconnect retry (client_index={}, tool={}, first_error={}, retry_error={})",
                            idx,
                            operation,
                            error,
                            retry_error
                        ))
                    }
                }
            }
            Err(error) => {
                tracing::error!(
                    event = "mcp.pool.call.failed",
                    operation = %operation,
                    client_index = idx,
                    error = %error,
                    "mcp tools/call failed"
                );
                Err(error)
            }
        };

        if let Some(cache_key) = discover_cache_key.as_deref()
            && let Ok(output) = call_result.as_ref()
        {
            self.store_discover_call_cache(cache_key, output).await;
        }

        call_result
    }

    async fn list_tools_once(
        &self,
        client_index: usize,
        params: Option<PaginatedRequestParams>,
    ) -> Result<ListToolsResult> {
        let client = self.client(client_index).await?;
        let started = Instant::now();
        let timeout = self.tool_timeout;
        let (wait_logger, wait_logger_stop) =
            spawn_inflight_wait_logger("tools/list".to_string(), client_index, timeout);
        let mut request_task = tokio::spawn(async move { client.list_tools(params).await });
        let result = tokio::time::timeout(timeout, &mut request_task).await;
        stop_wait_logger(wait_logger, wait_logger_stop).await;
        match result {
            Ok(Ok(Ok(output))) => {
                let elapsed_ms = started.elapsed().as_millis();
                if elapsed_ms >= DEFAULT_SLOW_CALL_WARN_MS {
                    tracing::warn!(
                        event = "mcp.pool.call.slow",
                        operation = "tools/list",
                        client_index,
                        elapsed_ms,
                        timeout_secs = timeout.as_secs(),
                        "mcp tools/list completed slowly"
                    );
                }
                Ok(output)
            }
            Ok(Ok(Err(error))) => Err(error),
            Ok(Err(join_error)) => Err(anyhow!(
                "MCP tools/list worker task join failed (client_index={}, error={})",
                client_index,
                join_error
            )),
            Err(_) => {
                request_task.abort();
                tracing::warn!(
                    event = "mcp.pool.call.timeout.hard",
                    operation = "tools/list",
                    client_index,
                    timeout_secs = timeout.as_secs(),
                    "mcp tools/list hard timeout reached; worker task aborted"
                );
                Err(anyhow!(
                    "MCP tools/list timed out after {}s (client_index={})",
                    timeout.as_secs(),
                    client_index
                ))
            }
        }
    }

    async fn call_tool_once(
        &self,
        client_index: usize,
        name: String,
        arguments: Option<serde_json::Value>,
    ) -> Result<CallToolResult> {
        let client = self.client(client_index).await?;
        let started = Instant::now();
        let timeout = self.tool_timeout;
        let operation = format!("tools/call:{name}");
        let (wait_logger, wait_logger_stop) =
            spawn_inflight_wait_logger(operation.clone(), client_index, timeout);
        let mut request_task = tokio::spawn(async move { client.call_tool(name, arguments).await });
        let result = tokio::time::timeout(timeout, &mut request_task).await;
        stop_wait_logger(wait_logger, wait_logger_stop).await;
        match result {
            Ok(Ok(Ok(output))) => {
                let elapsed_ms = started.elapsed().as_millis();
                if elapsed_ms >= DEFAULT_SLOW_CALL_WARN_MS {
                    tracing::warn!(
                        event = "mcp.pool.call.slow",
                        operation = %operation,
                        client_index,
                        elapsed_ms,
                        timeout_secs = timeout.as_secs(),
                        "mcp tools/call completed slowly"
                    );
                }
                Ok(output)
            }
            Ok(Ok(Err(error))) => Err(error),
            Ok(Err(join_error)) => Err(anyhow!(
                "MCP tools/call worker task join failed (client_index={}, tool={}, error={})",
                client_index,
                operation,
                join_error
            )),
            Err(_) => {
                request_task.abort();
                tracing::warn!(
                    event = "mcp.pool.call.timeout.hard",
                    operation = %operation,
                    client_index,
                    timeout_secs = timeout.as_secs(),
                    "mcp tools/call hard timeout reached; worker task aborted"
                );
                Err(anyhow!(
                    "MCP tools/call timed out after {}s (client_index={}, tool={})",
                    timeout.as_secs(),
                    client_index,
                    operation
                ))
            }
        }
    }

    async fn client(&self, client_index: usize) -> Result<std::sync::Arc<OmniMcpClient>> {
        let clients = self.clients.read().await;
        clients
            .get(client_index)
            .cloned()
            .ok_or_else(|| anyhow!("MCP pool client index out of bounds: {client_index}"))
    }

    async fn reconnect_client(&self, client_index: usize, reason: &str) -> Result<()> {
        let reconnect_lock = self
            .reconnect_locks
            .get(client_index)
            .ok_or_else(|| anyhow!("MCP reconnect lock index out of bounds: {client_index}"))?;
        let _guard = reconnect_lock.lock().await;
        let retries = self.connect_config.connect_retries.max(1);
        let new_client = connect_one_client_with_retry(
            &self.server_url,
            self.connect_config,
            retries,
            client_index,
        )
        .await?;
        let mut clients = self.clients.write().await;
        if client_index >= clients.len() {
            return Err(anyhow!(
                "MCP reconnect client index out of bounds: {client_index}"
            ));
        }
        clients[client_index] = std::sync::Arc::new(new_client);
        drop(clients);
        self.invalidate_list_tools_cache().await;
        tracing::info!(
            event = "mcp.pool.client.reconnected",
            url = %self.server_url,
            client_index,
            reason,
            retries,
            "mcp pool client reconnected"
        );
        Ok(())
    }
}

fn should_retry_transport_error(error: &anyhow::Error) -> bool {
    classify_transport_error(error).retryable
}

#[derive(Debug, Clone, Copy)]
struct TransportErrorClass {
    kind: &'static str,
    retryable: bool,
}

fn classify_transport_error(error: &anyhow::Error) -> TransportErrorClass {
    let message = format!("{error:#}").to_lowercase();
    if message.contains("transport send error") || message.contains("error sending request") {
        return TransportErrorClass {
            kind: "transport_send",
            retryable: true,
        };
    }
    if message.contains("connection refused") {
        return TransportErrorClass {
            kind: "connection_refused",
            retryable: true,
        };
    }
    if message.contains("connection reset") {
        return TransportErrorClass {
            kind: "connection_reset",
            retryable: true,
        };
    }
    if message.contains("broken pipe") {
        return TransportErrorClass {
            kind: "broken_pipe",
            retryable: true,
        };
    }
    if message.contains("connection closed") || message.contains("channel closed") {
        return TransportErrorClass {
            kind: "channel_closed",
            retryable: true,
        };
    }
    if message.contains("timed out") || message.contains("timeout") {
        return TransportErrorClass {
            kind: "timeout",
            retryable: true,
        };
    }
    if message.contains("client error") {
        return TransportErrorClass {
            kind: "client_error",
            retryable: true,
        };
    }
    if message.contains("dns") || message.contains("name or service not known") {
        return TransportErrorClass {
            kind: "dns_error",
            retryable: true,
        };
    }
    TransportErrorClass {
        kind: "non_transport",
        retryable: false,
    }
}

fn list_tools_cache_ttl_from_config(raw_ms: u64) -> Duration {
    let sanitized = raw_ms.max(1).min(MAX_LIST_TOOLS_CACHE_TTL_MS);
    Duration::from_millis(sanitized)
}

fn spawn_inflight_wait_logger(
    operation: String,
    client_index: usize,
    timeout: Duration,
) -> (tokio::task::JoinHandle<()>, oneshot::Sender<()>) {
    let (stop_tx, mut stop_rx) = oneshot::channel::<()>();
    let timeout_secs = timeout.as_secs().max(1);
    let overdue_limit_secs = timeout_secs.saturating_add(DEFAULT_INFLIGHT_LOG_INTERVAL_SECS);
    let handle = tokio::spawn(async move {
        let mut waited_secs = DEFAULT_INFLIGHT_LOG_INTERVAL_SECS;
        loop {
            tokio::select! {
                _ = tokio::time::sleep(Duration::from_secs(DEFAULT_INFLIGHT_LOG_INTERVAL_SECS)) => {}
                _ = &mut stop_rx => break,
            }
            tracing::warn!(
                event = "mcp.pool.call.waiting",
                operation = %operation,
                client_index,
                waited_secs,
                timeout_secs,
                "mcp call still waiting"
            );
            if waited_secs >= overdue_limit_secs {
                tracing::warn!(
                    event = "mcp.pool.call.waiting.guard_stop",
                    operation = %operation,
                    client_index,
                    waited_secs,
                    timeout_secs,
                    "mcp call wait logger stopped after exceeding timeout guard"
                );
                break;
            }
            waited_secs += DEFAULT_INFLIGHT_LOG_INTERVAL_SECS;
        }
    });
    (handle, stop_tx)
}

async fn connect_one_client_with_retry(
    url: &str,
    config: McpPoolConnectConfig,
    retries: u32,
    client_index: usize,
) -> Result<OmniMcpClient> {
    let handshake_timeout_secs = config.handshake_timeout_secs.max(1);
    let retry_backoff_ms = config.connect_retry_backoff_ms.max(1);
    let health_wait_secs = compute_health_ready_wait_secs(handshake_timeout_secs, retries);
    wait_for_mcp_ready(url, client_index, health_wait_secs).await?;
    let mut last_error = None;
    for attempt in 1..=retries {
        let attempt_timeout_secs = compute_handshake_timeout_secs(handshake_timeout_secs, attempt);
        let pre_health_probe = probe_health_summary(url).await;
        tracing::debug!(
            event = "mcp.pool.connect.attempt",
            url,
            client_index,
            attempt,
            retries,
            handshake_timeout_secs = attempt_timeout_secs,
            pre_health_probe = %pre_health_probe,
            "mcp pool client connect attempt started"
        );
        let started = Instant::now();
        let connect_wait_logger = spawn_connect_wait_logger(
            url.to_string(),
            client_index,
            attempt,
            retries,
            attempt_timeout_secs,
        );
        let (connect_wait_logger, connect_wait_logger_stop) = connect_wait_logger;
        let url_owned = url.to_string();
        let mut connect_task = tokio::spawn(async move {
            OmniMcpClient::connect_streamable_http(
                &url_owned,
                init_params_omni_server(),
                Some(Duration::from_secs(attempt_timeout_secs)),
            )
            .await
        });
        let connect_result =
            tokio::time::timeout(Duration::from_secs(attempt_timeout_secs), &mut connect_task)
                .await;
        stop_wait_logger(connect_wait_logger, connect_wait_logger_stop).await;
        match connect_result {
            Ok(Ok(Ok(client))) => {
                tracing::info!(
                    event = "mcp.pool.connect.succeeded",
                    url,
                    client_index,
                    attempt,
                    retries,
                    handshake_timeout_secs = attempt_timeout_secs,
                    duration_ms = started.elapsed().as_millis(),
                    "mcp pool client connected"
                );
                return Ok(client);
            }
            Ok(Ok(Err(error))) => {
                let health_probe = probe_health_summary(url).await;
                let error_class = classify_transport_error(&error);
                tracing::warn!(
                    event = "mcp.pool.connect.failed",
                    url,
                    client_index,
                    attempt,
                    retries,
                    handshake_timeout_secs = attempt_timeout_secs,
                    duration_ms = started.elapsed().as_millis(),
                    health_probe = %health_probe,
                    error_class = error_class.kind,
                    error = %error,
                    "mcp pool client connect failed"
                );
                last_error = Some(error);
                if attempt < retries {
                    let delay_ms = compute_retry_backoff_ms(retry_backoff_ms, attempt, retries);
                    tokio::time::sleep(Duration::from_millis(delay_ms)).await;
                }
            }
            Ok(Err(join_error)) => {
                let error = anyhow!(
                    "MCP connect worker task join failed (url={}, client_index={}, attempt={}, error={})",
                    url,
                    client_index,
                    attempt,
                    join_error
                );
                let health_probe = probe_health_summary(url).await;
                let error_class = classify_transport_error(&error);
                tracing::warn!(
                    event = "mcp.pool.connect.failed",
                    url,
                    client_index,
                    attempt,
                    retries,
                    handshake_timeout_secs = attempt_timeout_secs,
                    duration_ms = started.elapsed().as_millis(),
                    health_probe = %health_probe,
                    error_class = error_class.kind,
                    error = %error,
                    "mcp pool client connect failed"
                );
                last_error = Some(error);
                if attempt < retries {
                    let delay_ms = compute_retry_backoff_ms(retry_backoff_ms, attempt, retries);
                    tokio::time::sleep(Duration::from_millis(delay_ms)).await;
                }
            }
            Err(_) => {
                connect_task.abort();
                let error = anyhow!("MCP handshake timeout");
                let health_probe = probe_health_summary(url).await;
                tracing::warn!(
                    event = "mcp.pool.connect.failed",
                    url,
                    client_index,
                    attempt,
                    retries,
                    handshake_timeout_secs = attempt_timeout_secs,
                    duration_ms = started.elapsed().as_millis(),
                    health_probe = %health_probe,
                    error_class = "timeout",
                    error = %error,
                    "mcp pool client connect hard timeout reached; worker task aborted"
                );
                last_error = Some(error);
                if attempt < retries {
                    let delay_ms = compute_retry_backoff_ms(retry_backoff_ms, attempt, retries);
                    tokio::time::sleep(Duration::from_millis(delay_ms)).await;
                }
            }
        }
    }

    let last_error = last_error.unwrap_or_else(|| anyhow!("unknown mcp connect error"));
    Err(anyhow!(
        "MCP connect failed after {} attempts (url={}, client_index={}, handshake_timeout_secs_base={}, last_error={})",
        retries,
        url,
        client_index,
        handshake_timeout_secs,
        last_error
    ))
}

async fn stop_wait_logger(handle: tokio::task::JoinHandle<()>, stop_tx: oneshot::Sender<()>) {
    let _ = stop_tx.send(());
    let _ = handle.await;
}

fn spawn_connect_wait_logger(
    url: String,
    client_index: usize,
    attempt: u32,
    retries: u32,
    handshake_timeout_secs: u64,
) -> (tokio::task::JoinHandle<()>, oneshot::Sender<()>) {
    let (stop_tx, mut stop_rx) = oneshot::channel::<()>();
    let timeout_secs = handshake_timeout_secs.max(1);
    let overdue_limit_secs = timeout_secs.saturating_add(DEFAULT_INFLIGHT_LOG_INTERVAL_SECS);
    let handle = tokio::spawn(async move {
        let mut waited_secs = DEFAULT_INFLIGHT_LOG_INTERVAL_SECS;
        loop {
            tokio::select! {
                _ = tokio::time::sleep(Duration::from_secs(DEFAULT_INFLIGHT_LOG_INTERVAL_SECS)) => {}
                _ = &mut stop_rx => break,
            }
            tracing::warn!(
                event = "mcp.pool.connect.waiting",
                url = %url,
                client_index,
                attempt,
                retries,
                waited_secs,
                handshake_timeout_secs = timeout_secs,
                "mcp connect attempt still waiting"
            );
            if waited_secs >= overdue_limit_secs {
                tracing::warn!(
                    event = "mcp.pool.connect.waiting.guard_stop",
                    url = %url,
                    client_index,
                    attempt,
                    retries,
                    waited_secs,
                    handshake_timeout_secs = timeout_secs,
                    "mcp connect wait logger stopped after exceeding timeout guard"
                );
                break;
            }
            waited_secs += DEFAULT_INFLIGHT_LOG_INTERVAL_SECS;
        }
    });
    (handle, stop_tx)
}

fn compute_retry_backoff_ms(base_ms: u64, attempt: u32, retries: u32) -> u64 {
    if retries <= 1 {
        return 0;
    }
    let shift = attempt.saturating_sub(1).min(8);
    let multiplier = 1_u64 << shift;
    base_ms
        .saturating_mul(multiplier)
        .min(MAX_CONNECT_RETRY_BACKOFF_MS)
}

fn compute_handshake_timeout_secs(base_secs: u64, attempt: u32) -> u64 {
    let shift = attempt.saturating_sub(1).min(2);
    let multiplier = 1_u64 << shift;
    base_secs
        .saturating_mul(multiplier)
        .min(MAX_HANDSHAKE_TIMEOUT_SECS)
}

fn compute_health_ready_wait_secs(base_secs: u64, retries: u32) -> u64 {
    let effective_retries = retries.max(1) as u64;
    base_secs
        .max(1)
        .saturating_mul(effective_retries)
        .min(MAX_HEALTH_READY_WAIT_SECS)
}

async fn wait_for_mcp_ready(url: &str, client_index: usize, wait_secs: u64) -> Result<()> {
    let wait_secs = wait_secs.max(1).min(MAX_HEALTH_READY_WAIT_SECS);
    let deadline = Instant::now() + Duration::from_secs(wait_secs);
    let mut probe = probe_health_status(url).await;

    if !probe.has_structured_ready_state {
        tracing::debug!(
            event = "mcp.pool.health.wait.skipped",
            url,
            client_index,
            health_probe = %probe.summary,
            "mcp health readiness gate skipped (structured fields unavailable)"
        );
        return Ok(());
    }

    tracing::debug!(
        event = "mcp.pool.health.wait.start",
        url,
        client_index,
        wait_secs,
        health_probe = %probe.summary,
        "mcp health readiness gate started"
    );
    loop {
        if probe.ready == Some(true) && probe.initializing != Some(true) {
            tracing::debug!(
                event = "mcp.pool.health.wait.ready",
                url,
                client_index,
                wait_secs,
                health_probe = %probe.summary,
                "mcp health readiness gate passed"
            );
            return Ok(());
        }

        if Instant::now() >= deadline {
            tracing::warn!(
                event = "mcp.pool.health.wait.timeout",
                url,
                client_index,
                wait_secs,
                health_probe = %probe.summary,
                "mcp health readiness gate timed out"
            );
            return Err(anyhow!(
                "MCP health ready wait timed out after {}s (url={}, client_index={}, last_probe={})",
                wait_secs,
                url,
                client_index,
                probe.summary
            ));
        }

        tokio::time::sleep(Duration::from_millis(DEFAULT_HEALTH_READY_POLL_MS)).await;
        probe = probe_health_status(url).await;
    }
}

#[derive(Debug)]
struct HealthProbeStatus {
    summary: String,
    ready: Option<bool>,
    initializing: Option<bool>,
    has_structured_ready_state: bool,
}

async fn probe_health_summary(url: &str) -> String {
    probe_health_status(url).await.summary
}

async fn probe_health_status(url: &str) -> HealthProbeStatus {
    let Some(health_url) = derive_health_url(url) else {
        return HealthProbeStatus {
            summary: "health_probe_skipped(invalid_url)".to_string(),
            ready: None,
            initializing: None,
            has_structured_ready_state: false,
        };
    };
    let client = match health_probe_client() {
        Ok(client) => client,
        Err(summary) => {
            return HealthProbeStatus {
                summary,
                ready: None,
                initializing: None,
                has_structured_ready_state: false,
            };
        }
    };
    match client.get(&health_url).send().await {
        Ok(response) => {
            let status = response.status().as_u16();
            let body = response.text().await.unwrap_or_default();
            if let Ok(payload) = serde_json::from_str::<serde_json::Value>(&body) {
                let ready = payload
                    .get("ready")
                    .and_then(serde_json::Value::as_bool)
                    .map_or_else(|| "unknown".to_string(), |value| value.to_string());
                let initializing = payload
                    .get("initializing")
                    .and_then(serde_json::Value::as_bool)
                    .map_or_else(|| "unknown".to_string(), |value| value.to_string());
                let active_sessions = payload
                    .get("active_sessions")
                    .and_then(serde_json::Value::as_u64)
                    .map_or_else(|| "unknown".to_string(), |value| value.to_string());
                let parsed_ready = payload.get("ready").and_then(serde_json::Value::as_bool);
                let parsed_initializing = payload
                    .get("initializing")
                    .and_then(serde_json::Value::as_bool);
                return HealthProbeStatus {
                    summary: format!(
                        "health_status={status},ready={ready},initializing={initializing},active_sessions={active_sessions}"
                    ),
                    ready: parsed_ready,
                    initializing: parsed_initializing,
                    has_structured_ready_state: parsed_ready.is_some()
                        && parsed_initializing.is_some(),
                };
            }
            HealthProbeStatus {
                summary: format!("health_status={status}"),
                ready: None,
                initializing: None,
                has_structured_ready_state: false,
            }
        }
        Err(error) => {
            if error.is_timeout() {
                HealthProbeStatus {
                    summary: "health_timeout".to_string(),
                    ready: None,
                    initializing: None,
                    has_structured_ready_state: false,
                }
            } else {
                HealthProbeStatus {
                    summary: format!("health_error({error})"),
                    ready: None,
                    initializing: None,
                    has_structured_ready_state: false,
                }
            }
        }
    }
}

fn health_probe_client() -> std::result::Result<&'static reqwest::Client, String> {
    if let Some(client) = HEALTH_PROBE_CLIENT.get() {
        return Ok(client);
    }

    let client = reqwest::Client::builder()
        .timeout(Duration::from_millis(DEFAULT_HEALTH_PROBE_TIMEOUT_MS))
        .build()
        .map_err(|error| format!("health_probe_build_failed({error})"))?;
    let _ = HEALTH_PROBE_CLIENT.set(client);
    match HEALTH_PROBE_CLIENT.get() {
        Some(client) => Ok(client),
        None => Err("health_probe_build_failed(once_lock_not_initialized)".to_string()),
    }
}

fn derive_health_url(url: &str) -> Option<String> {
    let trimmed = url.trim();
    if trimmed.is_empty() {
        return None;
    }
    let without_trailing = trimmed.trim_end_matches('/');
    if let Some(base) = without_trailing.strip_suffix("/sse") {
        return Some(format!("{base}/health"));
    }
    if let Some(base) = without_trailing.strip_suffix("/messages") {
        return Some(format!("{base}/health"));
    }
    if let Some(base) = without_trailing.strip_suffix("/mcp") {
        return Some(format!("{base}/health"));
    }
    Some(format!("{without_trailing}/health"))
}

/// Build pool from URL with explicit connect configuration.
pub async fn connect_pool(url: &str, config: McpPoolConnectConfig) -> Result<McpClientPool> {
    McpClientPool::connect(url, config).await
}
