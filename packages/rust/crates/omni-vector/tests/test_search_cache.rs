//! Integration tests for search result cache (get_cached, set_cached, hybrid).
//!
//! Tests share a static cache; run with: cargo test -p omni-vector --test test_search_cache -- --test-threads=1

use omni_vector::search_cache::{
    clear_cache, get_cached, get_cached_hybrid, set_cached, set_cached_hybrid,
};

#[test]
fn test_cache_miss_then_hit() {
    clear_cache();
    let path = "/tmp/test";
    let table = "knowledge";
    let limit = 10;
    let vector = vec![0.1, 0.2, 0.3f32];

    assert!(get_cached(path, table, limit, None, &vector).is_none());

    let results = vec!["a".to_string(), "b".to_string()];
    set_cached(path, table, limit, None, &vector, results.clone());

    let cached = get_cached(path, table, limit, None, &vector).unwrap();
    assert_eq!(cached, results);
}

#[test]
fn test_different_vectors_different_entries() {
    clear_cache();
    let path = "/tmp/test";
    let table = "knowledge";
    let limit = 10;

    let v1 = vec![0.1f32, 0.2];
    let v2 = vec![0.2f32, 0.1];
    set_cached(path, table, limit, None, &v1, vec!["r1".into()]);
    set_cached(path, table, limit, None, &v2, vec!["r2".into()]);

    assert_eq!(get_cached(path, table, limit, None, &v1).unwrap(), ["r1"]);
    assert_eq!(get_cached(path, table, limit, None, &v2).unwrap(), ["r2"]);
}

#[test]
fn test_hybrid_cache_miss_then_hit() {
    clear_cache();
    let path = "/tmp/test";
    let table = "tools";
    let limit = 5;
    let vector = vec![0.5f32, 0.6];
    let query_text = "git commit";

    assert!(get_cached_hybrid(path, table, limit, &vector, query_text).is_none());

    let results = vec!["git.smart_commit".into(), "git.status".into()];
    set_cached_hybrid(path, table, limit, &vector, query_text, results.clone());

    let cached = get_cached_hybrid(path, table, limit, &vector, query_text).unwrap();
    assert_eq!(cached, results);
}
