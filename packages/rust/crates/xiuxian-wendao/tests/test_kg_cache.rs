//! Integration tests for KG cache (load_from_lance_cached, invalidate).
//!
//! Tests share a static cache; run with: cargo test -p xiuxian-wendao kg_cache -- --test-threads=1

use std::sync::{LazyLock, Mutex, MutexGuard};
use tempfile::TempDir;
use xiuxian_wendao::graph::KnowledgeGraph;
use xiuxian_wendao::kg_cache::{cache_len, invalidate, invalidate_all, load_from_lance_cached};
use xiuxian_wendao::{Entity, EntityType};

static TEST_LOCK: LazyLock<Mutex<()>> = LazyLock::new(|| Mutex::new(()));

fn test_guard() -> MutexGuard<'static, ()> {
    TEST_LOCK
        .lock()
        .unwrap_or_else(|_| panic!("kg cache test lock poisoned"))
}

fn create_test_kg_with_entity() -> (TempDir, String) {
    let tmp = TempDir::new().unwrap();
    let lance_dir = tmp.path().join("kg").to_string_lossy().into_owned();
    std::fs::create_dir_all(&lance_dir).unwrap();

    let graph = KnowledgeGraph::new();
    let entity = Entity::new(
        "test:foo".to_string(),
        "Foo".to_string(),
        EntityType::Concept,
        "Test entity".to_string(),
    );
    graph.add_entity(entity).unwrap();
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();
    runtime
        .block_on(graph.save_to_lance(&lance_dir, 8))
        .unwrap();
    (tmp, lance_dir)
}

#[test]
fn test_cache_miss_then_hit() {
    let _guard = test_guard();
    invalidate_all();
    let (_tmp, lance_dir) = create_test_kg_with_entity();

    let g1 = load_from_lance_cached(&lance_dir).unwrap().unwrap();
    assert_eq!(g1.get_stats().total_entities, 1);

    let g2 = load_from_lance_cached(&lance_dir).unwrap().unwrap();
    assert_eq!(g2.get_stats().total_entities, 1);
    assert_eq!(cache_len(), 1, "cache should have one entry");
}

#[test]
fn test_cache_invalidation_after_save() {
    let _guard = test_guard();
    invalidate_all();
    let (_tmp, lance_dir) = create_test_kg_with_entity();

    let g1 = load_from_lance_cached(&lance_dir).unwrap().unwrap();
    assert_eq!(g1.get_stats().total_entities, 1);
    assert_eq!(cache_len(), 1);

    invalidate(&lance_dir);
    assert_eq!(cache_len(), 0, "invalidate should remove the entry");

    let g2 = load_from_lance_cached(&lance_dir).unwrap().unwrap();
    assert_eq!(g2.get_stats().total_entities, 1);
}

#[test]
fn test_nonexistent_path_returns_empty() {
    let _guard = test_guard();
    invalidate_all();
    let result = load_from_lance_cached("/nonexistent/path/12345").unwrap();
    assert!(result.is_some());
    let g = result.unwrap();
    assert_eq!(g.get_stats().total_entities, 0);
    assert_eq!(g.get_stats().total_relations, 0);
    assert_eq!(cache_len(), 0);
}

#[test]
fn test_path_normalization() {
    let _guard = test_guard();
    invalidate_all();
    let (_tmp, lance_dir) = create_test_kg_with_entity();
    let lance_dir_trailing = format!("{}/", lance_dir);

    let g1 = load_from_lance_cached(&lance_dir).unwrap().unwrap();
    let g2 = load_from_lance_cached(&lance_dir_trailing)
        .unwrap()
        .unwrap();
    assert_eq!(g1.get_stats().total_entities, g2.get_stats().total_entities);
    assert_eq!(
        cache_len(),
        1,
        "normalized paths should share one cache entry"
    );
}
