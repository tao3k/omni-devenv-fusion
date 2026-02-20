use super::{
    DEFAULT_DECAY_RATE, DEFAULT_SALIENCY_BASE, LINK_GRAPH_SALIENCY_SCHEMA_VERSION,
    LinkGraphSaliencyPolicy, LinkGraphSaliencyState, LinkGraphSaliencyTouchRequest,
    calc::compute_link_graph_saliency,
    keys::{edge_in_key, edge_out_key, saliency_key},
};
use crate::link_graph::runtime_config::{
    DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX, resolve_link_graph_cache_runtime,
};
use std::time::{SystemTime, UNIX_EPOCH};

fn now_unix_i64() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |delta| delta.as_secs() as i64)
}

fn now_unix_f64() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |delta| delta.as_secs_f64())
}

fn normalize_policy(
    alpha: Option<f64>,
    minimum: Option<f64>,
    maximum: Option<f64>,
) -> LinkGraphSaliencyPolicy {
    let mut policy = LinkGraphSaliencyPolicy::default();
    if let Some(alpha_value) = alpha {
        policy.alpha = alpha_value;
    }
    if let Some(minimum_value) = minimum {
        policy.minimum = minimum_value;
    }
    if let Some(maximum_value) = maximum {
        policy.maximum = maximum_value;
    }
    policy.normalized()
}

fn parse_saliency_payload(
    raw: &str,
    node_id: &str,
    policy: LinkGraphSaliencyPolicy,
) -> Option<LinkGraphSaliencyState> {
    let parsed = serde_json::from_str::<LinkGraphSaliencyState>(raw).ok()?;
    if parsed.schema != LINK_GRAPH_SALIENCY_SCHEMA_VERSION {
        return None;
    }
    if parsed.node_id != node_id {
        return None;
    }

    let normalized = policy.normalized();
    let saliency = if parsed.current_saliency.is_finite() {
        parsed
            .current_saliency
            .clamp(normalized.minimum, normalized.maximum)
    } else {
        normalized.minimum
    };
    let mut repaired = parsed;
    repaired.current_saliency = saliency;
    if repaired.last_accessed_unix < 0 {
        repaired.last_accessed_unix = 0;
    }
    if repaired.updated_at_unix < 0.0 || !repaired.updated_at_unix.is_finite() {
        repaired.updated_at_unix = now_unix_f64();
    }
    Some(repaired)
}

fn redis_client(valkey_url: &str) -> Result<redis::Client, String> {
    redis::Client::open(valkey_url)
        .map_err(|err| format!("invalid valkey url for link_graph saliency store: {err}"))
}

fn resolve_runtime() -> Result<(String, String), String> {
    let runtime = resolve_link_graph_cache_runtime()?;
    let key_prefix = if runtime.key_prefix.trim().is_empty() {
        DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX.to_string()
    } else {
        runtime.key_prefix
    };
    Ok((runtime.valkey_url, key_prefix))
}

fn update_inbound_edge_scores(
    conn: &mut redis::Connection,
    node_id: &str,
    key_prefix: &str,
    saliency_score: f64,
) {
    let inbound_key = edge_in_key(node_id, key_prefix);
    let inbound_sources = redis::cmd("SMEMBERS")
        .arg(&inbound_key)
        .query::<Vec<String>>(conn)
        .unwrap_or_default();
    for source in inbound_sources {
        let out_key = edge_out_key(source.trim(), key_prefix);
        let _ = redis::cmd("ZADD")
            .arg(&out_key)
            .arg(saliency_score)
            .arg(node_id)
            .query::<i64>(conn);
    }
}

fn load_current_state(
    conn: &mut redis::Connection,
    cache_key: &str,
    node_id: &str,
    policy: LinkGraphSaliencyPolicy,
) -> Option<LinkGraphSaliencyState> {
    let raw = redis::cmd("GET")
        .arg(cache_key)
        .query::<Option<String>>(conn)
        .ok()?;
    let payload = raw?;
    let parsed = parse_saliency_payload(&payload, node_id, policy);
    if parsed.is_none() {
        let _ = redis::cmd("DEL").arg(cache_key).query::<i64>(conn);
    }
    parsed
}

pub fn valkey_saliency_get(node_id: &str) -> Result<Option<LinkGraphSaliencyState>, String> {
    let (valkey_url, key_prefix) = resolve_runtime()?;
    valkey_saliency_get_with_valkey(node_id, &valkey_url, Some(&key_prefix))
}

pub fn valkey_saliency_get_with_valkey(
    node_id: &str,
    valkey_url: &str,
    key_prefix: Option<&str>,
) -> Result<Option<LinkGraphSaliencyState>, String> {
    let trimmed = node_id.trim();
    if trimmed.is_empty() {
        return Ok(None);
    }
    if valkey_url.trim().is_empty() {
        return Err("link_graph saliency valkey_url must be non-empty".to_string());
    }
    let prefix = key_prefix
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX);
    let cache_key = saliency_key(trimmed, prefix);

    let policy = LinkGraphSaliencyPolicy::default();
    let client = redis_client(valkey_url)?;
    let mut conn = client
        .get_connection()
        .map_err(|err| format!("failed to connect valkey for link_graph saliency store: {err}"))?;

    let raw = redis::cmd("GET")
        .arg(&cache_key)
        .query::<Option<String>>(&mut conn)
        .map_err(|err| format!("failed to GET link_graph saliency entry: {err}"))?;
    let Some(payload_raw) = raw else {
        return Ok(None);
    };

    if let Some(state) = parse_saliency_payload(&payload_raw, trimmed, policy) {
        return Ok(Some(state));
    }

    let _ = redis::cmd("DEL").arg(&cache_key).query::<i64>(&mut conn);
    Ok(None)
}

pub fn valkey_saliency_del(node_id: &str) -> Result<(), String> {
    let (valkey_url, key_prefix) = resolve_runtime()?;
    let trimmed = node_id.trim();
    if trimmed.is_empty() {
        return Ok(());
    }
    let cache_key = saliency_key(trimmed, &key_prefix);
    let client = redis_client(&valkey_url)?;
    let mut conn = client
        .get_connection()
        .map_err(|err| format!("failed to connect valkey for link_graph saliency store: {err}"))?;
    redis::cmd("DEL")
        .arg(&cache_key)
        .query::<i64>(&mut conn)
        .map_err(|err| format!("failed to DEL link_graph saliency entry: {err}"))?;
    Ok(())
}

pub fn valkey_saliency_touch(
    request: LinkGraphSaliencyTouchRequest,
) -> Result<LinkGraphSaliencyState, String> {
    let (valkey_url, key_prefix) = resolve_runtime()?;
    valkey_saliency_touch_with_valkey(request, &valkey_url, Some(&key_prefix))
}

pub fn valkey_saliency_touch_with_valkey(
    request: LinkGraphSaliencyTouchRequest,
    valkey_url: &str,
    key_prefix: Option<&str>,
) -> Result<LinkGraphSaliencyState, String> {
    let node_id = request.node_id.trim();
    if node_id.is_empty() {
        return Err("node_id must be non-empty".to_string());
    }
    if valkey_url.trim().is_empty() {
        return Err("link_graph saliency valkey_url must be non-empty".to_string());
    }
    let prefix = key_prefix
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or(DEFAULT_LINK_GRAPH_VALKEY_KEY_PREFIX);
    let cache_key = saliency_key(node_id, prefix);
    let now_unix = request.now_unix.unwrap_or_else(now_unix_i64);
    let delta_activation = request.activation_delta.max(1);

    let policy = normalize_policy(
        request.alpha,
        request.minimum_saliency,
        request.maximum_saliency,
    );
    let client = redis_client(valkey_url)?;
    let mut conn = client
        .get_connection()
        .map_err(|err| format!("failed to connect valkey for link_graph saliency store: {err}"))?;

    let existing = load_current_state(&mut conn, &cache_key, node_id, policy);
    // Settlement strategy:
    // - Use current score as the next baseline.
    // - Apply decay across elapsed time and only this touch delta for activation boost.
    // - Persist settled score as both `current_saliency` and next `saliency_base`.
    let (baseline, decay_rate, total_activation, delta_days) = if let Some(state) = existing {
        let elapsed_seconds = (now_unix - state.last_accessed_unix).max(0) as f64;
        (
            request.saliency_base.unwrap_or(state.current_saliency),
            request.decay_rate.unwrap_or(state.decay_rate),
            state.activation_count.saturating_add(delta_activation),
            elapsed_seconds / 86_400.0,
        )
    } else {
        (
            request.saliency_base.unwrap_or(DEFAULT_SALIENCY_BASE),
            request.decay_rate.unwrap_or(DEFAULT_DECAY_RATE),
            delta_activation,
            0.0,
        )
    };

    let settled_score =
        compute_link_graph_saliency(baseline, decay_rate, delta_activation, delta_days, policy);
    let state = LinkGraphSaliencyState {
        schema: LINK_GRAPH_SALIENCY_SCHEMA_VERSION.to_string(),
        node_id: node_id.to_string(),
        saliency_base: settled_score,
        decay_rate,
        activation_count: total_activation,
        last_accessed_unix: now_unix,
        current_saliency: settled_score,
        updated_at_unix: now_unix as f64,
    };
    let encoded = serde_json::to_string(&state)
        .map_err(|err| format!("failed to serialize link_graph saliency state: {err}"))?;

    redis::cmd("SET")
        .arg(&cache_key)
        .arg(encoded)
        .query::<()>(&mut conn)
        .map_err(|err| format!("failed to SET link_graph saliency entry: {err}"))?;

    update_inbound_edge_scores(&mut conn, node_id, prefix, settled_score);
    Ok(state)
}
