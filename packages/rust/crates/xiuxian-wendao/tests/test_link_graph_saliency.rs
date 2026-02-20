use redis::Connection;
use std::time::{SystemTime, UNIX_EPOCH};
use xiuxian_wendao::{
    LinkGraphSaliencyPolicy, LinkGraphSaliencyTouchRequest, compute_link_graph_saliency,
    valkey_saliency_get_with_valkey, valkey_saliency_touch_with_valkey,
};

const TEST_VALKEY_URL: &str = "redis://127.0.0.1:6379/0";

fn unique_prefix() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|value| value.as_nanos())
        .unwrap_or(0);
    format!("omni:test:saliency:{nanos}")
}

fn valkey_connection() -> Result<Connection, Box<dyn std::error::Error>> {
    let client = redis::Client::open(TEST_VALKEY_URL)?;
    Ok(client.get_connection()?)
}

fn clear_prefix(prefix: &str) -> Result<(), Box<dyn std::error::Error>> {
    let mut conn = valkey_connection()?;
    let pattern = format!("{prefix}:*");
    let keys: Vec<String> = redis::cmd("KEYS").arg(&pattern).query(&mut conn)?;
    if !keys.is_empty() {
        redis::cmd("DEL").arg(keys).query::<()>(&mut conn)?;
    }
    Ok(())
}

#[test]
fn test_compute_link_graph_saliency_clamps_bounds() {
    let policy = LinkGraphSaliencyPolicy {
        alpha: 0.5,
        minimum: 1.0,
        maximum: 10.0,
    };

    let decayed = compute_link_graph_saliency(5.0, 0.10, 0, 30.0, policy);
    assert!(decayed >= 1.0);
    assert!(decayed < 5.0);

    let boosted = compute_link_graph_saliency(5.0, 0.0, 10_000, 0.0, policy);
    assert!(boosted <= 10.0);
    assert!(boosted > 9.0);
}

#[test]
fn test_compute_link_graph_saliency_activation_boosts_score() {
    let policy = LinkGraphSaliencyPolicy::default();
    let without_activation = compute_link_graph_saliency(5.0, 0.02, 0, 2.0, policy);
    let with_activation = compute_link_graph_saliency(5.0, 0.02, 8, 2.0, policy);
    assert!(with_activation > without_activation);
}

#[test]
fn test_saliency_touch_and_get_with_valkey() -> Result<(), Box<dyn std::error::Error>> {
    let prefix = unique_prefix();
    if clear_prefix(&prefix).is_err() {
        return Ok(());
    }

    let first = valkey_saliency_touch_with_valkey(
        LinkGraphSaliencyTouchRequest {
            node_id: "note-a".to_string(),
            activation_delta: 2,
            saliency_base: Some(5.0),
            decay_rate: Some(0.05),
            alpha: Some(0.5),
            minimum_saliency: Some(1.0),
            maximum_saliency: Some(10.0),
            now_unix: Some(1_700_000_000),
        },
        TEST_VALKEY_URL,
        Some(&prefix),
    )
    .map_err(|err| err.to_string())?;
    assert_eq!(first.activation_count, 2);
    assert!(first.current_saliency >= 1.0);
    assert!((first.saliency_base - first.current_saliency).abs() < 1e-9);

    let second = valkey_saliency_touch_with_valkey(
        LinkGraphSaliencyTouchRequest {
            node_id: "note-a".to_string(),
            activation_delta: 3,
            saliency_base: None,
            decay_rate: None,
            alpha: Some(0.5),
            minimum_saliency: Some(1.0),
            maximum_saliency: Some(10.0),
            now_unix: Some(1_700_086_400),
        },
        TEST_VALKEY_URL,
        Some(&prefix),
    )
    .map_err(|err| err.to_string())?;
    assert_eq!(second.activation_count, 5);
    assert!((second.saliency_base - second.current_saliency).abs() < 1e-9);

    let fetched = valkey_saliency_get_with_valkey("note-a", TEST_VALKEY_URL, Some(&prefix))
        .map_err(|err| err.to_string())?;
    assert!(fetched.is_some());
    let state = fetched.ok_or("missing saliency state after touch")?;
    assert_eq!(state.activation_count, 5);
    assert_eq!(state.last_accessed_unix, 1_700_086_400);

    clear_prefix(&prefix)?;
    Ok(())
}

#[test]
fn test_saliency_store_auto_repairs_invalid_payload() -> Result<(), Box<dyn std::error::Error>> {
    let prefix = unique_prefix();
    if clear_prefix(&prefix).is_err() {
        return Ok(());
    }

    let _ = valkey_saliency_touch_with_valkey(
        LinkGraphSaliencyTouchRequest {
            node_id: "note-b".to_string(),
            activation_delta: 1,
            saliency_base: Some(5.0),
            decay_rate: Some(0.01),
            alpha: None,
            minimum_saliency: None,
            maximum_saliency: None,
            now_unix: Some(1_700_000_000),
        },
        TEST_VALKEY_URL,
        Some(&prefix),
    )
    .map_err(|err| err.to_string())?;

    let mut conn = valkey_connection()?;
    let pattern = format!("{prefix}:saliency:*");
    let keys: Vec<String> = redis::cmd("KEYS").arg(&pattern).query(&mut conn)?;
    if keys.is_empty() {
        clear_prefix(&prefix)?;
        return Ok(());
    }
    let key = keys[0].clone();
    redis::cmd("SET")
        .arg(&key)
        .arg("{\"schema\":\"invalid.schema\"}")
        .query::<()>(&mut conn)?;

    let fetched = valkey_saliency_get_with_valkey("note-b", TEST_VALKEY_URL, Some(&prefix))
        .map_err(|err| err.to_string())?;
    assert!(fetched.is_none());

    let raw: Option<String> = redis::cmd("GET").arg(&key).query(&mut conn)?;
    assert!(raw.is_none(), "invalid payload key should be removed");

    clear_prefix(&prefix)?;
    Ok(())
}

#[test]
fn test_saliency_touch_updates_inbound_edge_zset() -> Result<(), Box<dyn std::error::Error>> {
    let prefix = unique_prefix();
    if clear_prefix(&prefix).is_err() {
        return Ok(());
    }

    let inbound_key = format!("{prefix}:kg:edge:in:note-b");
    let out_key = format!("{prefix}:kg:edge:out:note-a");
    let mut conn = valkey_connection()?;
    redis::cmd("SADD")
        .arg(&inbound_key)
        .arg("note-a")
        .query::<i64>(&mut conn)?;

    let state = valkey_saliency_touch_with_valkey(
        LinkGraphSaliencyTouchRequest {
            node_id: "note-b".to_string(),
            activation_delta: 2,
            saliency_base: Some(7.0),
            decay_rate: Some(0.05),
            alpha: Some(0.5),
            minimum_saliency: Some(1.0),
            maximum_saliency: Some(10.0),
            now_unix: Some(1_700_000_000),
        },
        TEST_VALKEY_URL,
        Some(&prefix),
    )
    .map_err(|err| err.to_string())?;

    let zscore: Option<f64> = redis::cmd("ZSCORE")
        .arg(&out_key)
        .arg("note-b")
        .query(&mut conn)?;
    assert!(zscore.is_some());
    let score = zscore.ok_or("missing zscore for updated edge")?;
    assert!((score - state.current_saliency).abs() < 1e-9);

    clear_prefix(&prefix)?;
    Ok(())
}
