use crate::link_graph::runtime_config::{
    DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX, resolve_link_graph_cache_runtime,
};
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::time::{SystemTime, UNIX_EPOCH};

pub const LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION: &str = "xiuxian_wendao.link_graph.stats.cache.v1";

#[derive(Debug, Clone, Serialize, Deserialize)]
struct LinkGraphStatsCacheStats {
    total_notes: i64,
    orphans: i64,
    links_in_graph: i64,
    nodes_in_graph: i64,
}

impl LinkGraphStatsCacheStats {
    fn normalize(self) -> Self {
        Self {
            total_notes: self.total_notes.max(0),
            orphans: self.orphans.max(0),
            links_in_graph: self.links_in_graph.max(0),
            nodes_in_graph: self.nodes_in_graph.max(0),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct LinkGraphStatsCachePayload {
    schema: String,
    source_key: String,
    updated_at_unix: f64,
    stats: LinkGraphStatsCacheStats,
}

fn now_unix_f64() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

fn resolve_stats_cache_runtime() -> Result<(String, String), String> {
    let runtime = resolve_link_graph_cache_runtime()?;
    let key_prefix = if runtime.key_prefix.trim().is_empty() {
        DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX.to_string()
    } else {
        runtime.key_prefix
    };
    Ok((runtime.valkey_url, key_prefix))
}

fn stats_cache_slot_key(source_key: &str) -> String {
    let mut hasher = DefaultHasher::new();
    source_key.hash(&mut hasher);
    LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION.hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

fn stats_cache_key(source_key: &str, key_prefix: &str) -> String {
    format!("{key_prefix}:stats:{}", stats_cache_slot_key(source_key))
}

fn decode_stats_payload_if_fresh(
    raw: &str,
    source_key: &str,
    ttl_sec: f64,
) -> Option<LinkGraphStatsCachePayload> {
    let payload = serde_json::from_str::<LinkGraphStatsCachePayload>(raw).ok()?;
    if payload.schema != LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION {
        return None;
    }
    if payload.source_key != source_key {
        return None;
    }
    if payload.updated_at_unix <= 0.0 {
        return None;
    }
    if ttl_sec > 0.0 && (now_unix_f64() - payload.updated_at_unix) > ttl_sec {
        return None;
    }
    Some(LinkGraphStatsCachePayload {
        schema: payload.schema,
        source_key: payload.source_key,
        updated_at_unix: payload.updated_at_unix,
        stats: payload.stats.normalize(),
    })
}

pub fn valkey_stats_cache_get(source_key: &str, ttl_sec: f64) -> Result<Option<String>, String> {
    let source_key = source_key.trim();
    if source_key.is_empty() || ttl_sec <= 0.0 {
        return Ok(None);
    }

    let (valkey_url, key_prefix) = resolve_stats_cache_runtime()?;
    let cache_key = stats_cache_key(source_key, &key_prefix);

    let client = redis::Client::open(valkey_url.as_str())
        .map_err(|e| format!("invalid valkey url for link-graph stats cache: {e}"))?;
    let mut conn = client
        .get_connection()
        .map_err(|e| format!("failed to connect valkey for link-graph stats cache: {e}"))?;
    let raw = redis::cmd("GET")
        .arg(&cache_key)
        .query::<Option<String>>(&mut conn)
        .map_err(|e| format!("failed to GET link-graph stats cache from valkey: {e}"))?;
    let Some(payload_raw) = raw else {
        return Ok(None);
    };

    let Some(valid_payload) = decode_stats_payload_if_fresh(&payload_raw, source_key, ttl_sec)
    else {
        let _ = redis::cmd("DEL").arg(&cache_key).query::<i64>(&mut conn);
        return Ok(None);
    };

    serde_json::to_string(&valid_payload)
        .map(Some)
        .map_err(|e| format!("failed to encode link-graph stats cache payload: {e}"))
}

pub fn valkey_stats_cache_set(
    source_key: &str,
    stats_json: &str,
    ttl_sec: f64,
) -> Result<(), String> {
    let source_key = source_key.trim();
    if source_key.is_empty() {
        return Err("source_key must be non-empty".to_string());
    }
    if ttl_sec <= 0.0 {
        return Ok(());
    }

    let parsed_stats = serde_json::from_str::<LinkGraphStatsCacheStats>(stats_json)
        .map_err(|e| format!("invalid link-graph stats payload: {e}"))?
        .normalize();
    let payload = LinkGraphStatsCachePayload {
        schema: LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION.to_string(),
        source_key: source_key.to_string(),
        updated_at_unix: now_unix_f64(),
        stats: parsed_stats,
    };
    let encoded = serde_json::to_string(&payload)
        .map_err(|e| format!("failed to serialize link-graph stats cache payload: {e}"))?;

    let (valkey_url, key_prefix) = resolve_stats_cache_runtime()?;
    let cache_key = stats_cache_key(source_key, &key_prefix);
    let ttl_rounded = ttl_sec.ceil().max(1.0) as u64;

    let client = redis::Client::open(valkey_url.as_str())
        .map_err(|e| format!("invalid valkey url for link-graph stats cache: {e}"))?;
    let mut conn = client
        .get_connection()
        .map_err(|e| format!("failed to connect valkey for link-graph stats cache: {e}"))?;
    redis::cmd("SETEX")
        .arg(&cache_key)
        .arg(ttl_rounded)
        .arg(&encoded)
        .query::<()>(&mut conn)
        .map_err(|e| format!("failed to SETEX link-graph stats cache to valkey: {e}"))?;
    Ok(())
}

pub fn valkey_stats_cache_del(source_key: &str) -> Result<(), String> {
    let source_key = source_key.trim();
    if source_key.is_empty() {
        return Ok(());
    }
    let (valkey_url, key_prefix) = resolve_stats_cache_runtime()?;
    let cache_key = stats_cache_key(source_key, &key_prefix);

    let client = redis::Client::open(valkey_url.as_str())
        .map_err(|e| format!("invalid valkey url for link-graph stats cache: {e}"))?;
    let mut conn = client
        .get_connection()
        .map_err(|e| format!("failed to connect valkey for link-graph stats cache: {e}"))?;
    redis::cmd("DEL")
        .arg(&cache_key)
        .query::<i64>(&mut conn)
        .map_err(|e| format!("failed to DEL link-graph stats cache from valkey: {e}"))?;
    Ok(())
}
