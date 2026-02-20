//! Discover tool-call read-through cache backed by Valkey.
//!
//! This cache is intentionally scoped to discover-like calls (e.g. `skill.discover`)
//! to keep key cardinality predictable while accelerating repeated intent lookups.

use std::sync::Arc;

use anyhow::{Context, Result};
use redis::FromRedisValue;
use rmcp::model::{CallToolResult, Content, Meta};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use tokio::sync::Mutex;

use crate::config::load_runtime_settings;

const DEFAULT_DISCOVER_CACHE_KEY_PREFIX: &str = "omni-agent:discover";
const DEFAULT_DISCOVER_CACHE_TTL_SECS: u64 = 30;
const MAX_DISCOVER_CACHE_TTL_SECS: u64 = 3_600;

#[derive(Debug, Clone)]
pub(super) struct DiscoverCacheRuntimeInfo {
    pub(super) backend: &'static str,
    pub(super) ttl_secs: u64,
}

#[derive(Debug, Clone)]
struct DiscoverCacheConfig {
    valkey_url: String,
    key_prefix: String,
    ttl_secs: u64,
}

#[derive(Debug)]
pub(super) struct DiscoverReadThroughCache {
    backend: ValkeyDiscoverCache,
}

impl DiscoverReadThroughCache {
    /// Build discover cache from env + runtime settings.
    ///
    /// Returns `Ok(None)` when cache is disabled or no valkey url is configured.
    pub(super) fn from_runtime() -> Result<Option<Self>> {
        let Some(config) = resolve_discover_cache_config() else {
            return Ok(None);
        };
        let backend = ValkeyDiscoverCache::new(config)?;
        Ok(Some(Self { backend }))
    }

    pub(super) fn runtime_info(&self) -> DiscoverCacheRuntimeInfo {
        DiscoverCacheRuntimeInfo {
            backend: "valkey",
            ttl_secs: self.backend.ttl_secs(),
        }
    }

    pub(super) fn build_cache_key(
        &self,
        tool_name: &str,
        arguments: Option<&Value>,
    ) -> Option<String> {
        if !is_discover_tool(tool_name) {
            return None;
        }

        let arguments = arguments?;
        let query = extract_discover_query(arguments)?;
        let normalized_args = canonicalize_json_value(arguments);
        let args_payload = normalized_args.to_string();
        let args_digest = sha256_hex(args_payload.as_bytes());
        let query_digest = sha256_hex(query.as_bytes());
        let tool_digest = tool_name.replace('.', "_");
        Some(format!(
            "{}:v1:{}:{}:{}",
            self.backend.key_prefix(),
            tool_digest,
            query_digest,
            args_digest
        ))
    }

    pub(super) async fn get(&self, key: &str) -> Result<Option<CallToolResult>> {
        self.backend.get(key).await
    }

    pub(super) async fn set(&self, key: &str, result: &CallToolResult) -> Result<()> {
        self.backend.set(key, result).await
    }
}

#[derive(Debug)]
struct ValkeyDiscoverCache {
    client: redis::Client,
    key_prefix: String,
    ttl_secs: u64,
    connection: Arc<Mutex<Option<redis::aio::MultiplexedConnection>>>,
}

impl ValkeyDiscoverCache {
    fn new(config: DiscoverCacheConfig) -> Result<Self> {
        let client = redis::Client::open(config.valkey_url.as_str()).with_context(|| {
            format!(
                "invalid valkey url for discover cache: {}",
                config.valkey_url
            )
        })?;
        Ok(Self {
            client,
            key_prefix: config.key_prefix,
            ttl_secs: config.ttl_secs,
            connection: Arc::new(Mutex::new(None)),
        })
    }

    fn key_prefix(&self) -> &str {
        &self.key_prefix
    }

    fn ttl_secs(&self) -> u64 {
        self.ttl_secs
    }

    async fn ensure_connection(
        &self,
        connection: &mut Option<redis::aio::MultiplexedConnection>,
    ) -> Result<()> {
        if connection.is_some() {
            return Ok(());
        }
        *connection = Some(
            self.client
                .get_multiplexed_async_connection()
                .await
                .context("failed to open redis connection for discover cache")?,
        );
        Ok(())
    }

    async fn run_command<T, F>(&self, operation: &'static str, build: F) -> Result<T>
    where
        T: FromRedisValue + Send,
        F: Fn() -> redis::Cmd,
    {
        let mut last_error: Option<anyhow::Error> = None;
        for attempt in 0..2 {
            let mut conn_guard = self.connection.lock().await;
            self.ensure_connection(&mut conn_guard).await?;
            let conn = conn_guard
                .as_mut()
                .ok_or_else(|| anyhow::anyhow!("discover cache connection unavailable"))?;
            let result: redis::RedisResult<T> = build().query_async(conn).await;
            match result {
                Ok(value) => return Ok(value),
                Err(error) => {
                    tracing::warn!(
                        event = "mcp.pool.discover_cache.command.retry",
                        operation,
                        attempt = attempt + 1,
                        error = %error,
                        "discover cache valkey command failed; reconnecting"
                    );
                    *conn_guard = None;
                    last_error = Some(
                        anyhow::anyhow!(error).context("discover cache valkey command failed"),
                    );
                    if attempt == 0 {
                        continue;
                    }
                }
            }
        }
        Err(last_error.unwrap_or_else(|| anyhow::anyhow!("discover cache valkey command failed")))
    }

    async fn get(&self, key: &str) -> Result<Option<CallToolResult>> {
        let key = key.to_string();
        let raw: Option<String> = self
            .run_command("discover_cache_get", move || {
                let mut cmd = redis::cmd("GET");
                cmd.arg(&key);
                cmd
            })
            .await?;
        raw.map(|payload| {
            serde_json::from_str::<CachedCallToolResult>(&payload)
                .context("failed to decode cached discover tool result")
                .map(Into::into)
        })
        .transpose()
    }

    async fn set(&self, key: &str, result: &CallToolResult) -> Result<()> {
        let key = key.to_string();
        let ttl_secs = self.ttl_secs;
        let payload = serde_json::to_string(&CachedCallToolResult::from(result))
            .context("failed to encode discover cache payload")?;
        let _: () = self
            .run_command("discover_cache_set", move || {
                let mut cmd = redis::cmd("SETEX");
                cmd.arg(&key).arg(ttl_secs).arg(&payload);
                cmd
            })
            .await?;
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CachedCallToolResult {
    content: Vec<Content>,
    structured_content: Option<Value>,
    is_error: Option<bool>,
    meta: Option<Meta>,
}

impl From<&CallToolResult> for CachedCallToolResult {
    fn from(value: &CallToolResult) -> Self {
        Self {
            content: value.content.clone(),
            structured_content: value.structured_content.clone(),
            is_error: value.is_error,
            meta: value.meta.clone(),
        }
    }
}

impl From<CachedCallToolResult> for CallToolResult {
    fn from(value: CachedCallToolResult) -> Self {
        Self {
            content: value.content,
            structured_content: value.structured_content,
            is_error: value.is_error,
            meta: value.meta,
        }
    }
}

fn resolve_discover_cache_config() -> Option<DiscoverCacheConfig> {
    let settings = load_runtime_settings();

    let enabled = env_bool("OMNI_AGENT_MCP_DISCOVER_CACHE_ENABLED")
        .or(settings.mcp.agent_discover_cache_enabled)
        .unwrap_or(true);
    if !enabled {
        return None;
    }

    let valkey_url = std::env::var("VALKEY_URL")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .or_else(|| {
            settings
                .session
                .valkey_url
                .as_deref()
                .map(str::trim)
                .map(str::to_string)
                .filter(|value| !value.is_empty())
        })?;

    let key_prefix = std::env::var("OMNI_AGENT_MCP_DISCOVER_CACHE_KEY_PREFIX")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .or_else(|| {
            settings
                .mcp
                .agent_discover_cache_key_prefix
                .as_deref()
                .map(str::trim)
                .map(str::to_string)
                .filter(|value| !value.is_empty())
        })
        .unwrap_or_else(|| DEFAULT_DISCOVER_CACHE_KEY_PREFIX.to_string());

    let ttl_secs = std::env::var("OMNI_AGENT_MCP_DISCOVER_CACHE_TTL_SECS")
        .ok()
        .and_then(|raw| raw.parse::<u64>().ok())
        .filter(|value| *value > 0)
        .or(settings.mcp.agent_discover_cache_ttl_secs)
        .unwrap_or(DEFAULT_DISCOVER_CACHE_TTL_SECS)
        .clamp(1, MAX_DISCOVER_CACHE_TTL_SECS);

    Some(DiscoverCacheConfig {
        valkey_url,
        key_prefix,
        ttl_secs,
    })
}

fn env_bool(name: &str) -> Option<bool> {
    let raw = std::env::var(name).ok()?;
    match raw.trim().to_ascii_lowercase().as_str() {
        "1" | "true" | "yes" | "on" => Some(true),
        "0" | "false" | "no" | "off" => Some(false),
        _ => None,
    }
}

fn is_discover_tool(name: &str) -> bool {
    matches!(name.trim(), "skill.discover" | "skill_discover")
}

fn extract_discover_query(arguments: &Value) -> Option<String> {
    let object = arguments.as_object()?;
    let intent = object
        .get("intent")
        .and_then(Value::as_str)
        .or_else(|| object.get("query").and_then(Value::as_str))?;
    let trimmed = intent.trim();
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed.to_string())
}

fn canonicalize_json_value(value: &Value) -> Value {
    match value {
        Value::Object(map) => {
            let mut entries = map.iter().collect::<Vec<_>>();
            entries.sort_by(|(a, _), (b, _)| a.cmp(b));
            let mut out = serde_json::Map::with_capacity(entries.len());
            for (key, child) in entries {
                out.insert(key.clone(), canonicalize_json_value(child));
            }
            Value::Object(out)
        }
        Value::Array(items) => Value::Array(items.iter().map(canonicalize_json_value).collect()),
        _ => value.clone(),
    }
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}
