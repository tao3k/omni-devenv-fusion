//! Tests for Phase 2 maintenance: auto_index_if_needed, compact, has_*_index, bounded dataset cache.

use omni_vector::{IndexThresholds, VectorStore, ops::DatasetCacheConfig};

async fn add_tools_table(store: &VectorStore, table: &str, n: usize, categories: &[&str]) {
    let mut ids = Vec::with_capacity(n);
    let mut vectors = Vec::with_capacity(n);
    let mut contents = Vec::with_capacity(n);
    let mut metadatas = Vec::with_capacity(n);
    for i in 0..n {
        let cat = categories[i % categories.len()];
        let skill = format!("skill_{}", cat);
        ids.push(format!("{}.cmd_{}", skill, i));
        vectors.push(vec![0.1; 64]);
        contents.push(format!("content {}", i));
        metadatas.push(
            serde_json::json!({
                "skill_name": skill,
                "category": cat,
                "file_path": format!("{}/scripts/x.py", skill),
                "tool_name": format!("cmd_{}", i),
            })
            .to_string(),
        );
    }
    store
        .add_documents(table, ids, vectors, contents, metadatas)
        .await
        .unwrap();
}

#[tokio::test]
async fn test_has_vector_index_false_without_index() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("has_vec");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 50, &["a", "b"]).await;

    let has = store.has_vector_index("t").await.unwrap();
    assert!(!has);
}

#[tokio::test]
async fn test_has_vector_index_true_after_create_index() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("has_vec_after");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 150, &["a", "b"]).await;
    store.create_index("t").await.unwrap();

    let has = store.has_vector_index("t").await.unwrap();
    assert!(has);
}

#[tokio::test]
async fn test_has_fts_index_true_after_create_fts_index() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("has_fts");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 50, &["a"]).await;
    store.create_fts_index("t").await.unwrap();

    let has = store.has_fts_index("t").await.unwrap();
    assert!(has);
}

#[tokio::test]
async fn test_has_scalar_index_true_after_create_scalar() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("has_scalar");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 50, &["x", "y"]).await;
    store.create_btree_index("t", "skill_name").await.unwrap();

    let has = store.has_scalar_index("t").await.unwrap();
    assert!(has);
}

#[tokio::test]
async fn test_auto_index_if_needed_returns_none_below_threshold() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("auto_low");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 50, &["a", "b"]).await;

    let out = store.auto_index_if_needed("t").await.unwrap();
    assert!(out.is_none());
}

#[tokio::test]
async fn test_auto_index_if_needed_creates_indices_over_threshold() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("auto_high");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 250, &["git", "docker", "python"]).await;

    let out = store.auto_index_if_needed("t").await.unwrap();
    let has_vec = store.has_vector_index("t").await.unwrap();
    let has_scalar = store.has_scalar_index("t").await.unwrap();
    assert!(has_vec, "vector index should be created");
    assert!(has_scalar, "scalar indices should be created");
    assert!(out.is_some(), "should return at least one IndexStats");
}

#[tokio::test]
async fn test_compact_returns_stats() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("compact");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 20, &["a", "b"]).await;

    let stats = store.compact("t").await.unwrap();
    assert!(stats.fragments_before >= 1);
    assert!(stats.fragments_after >= 1);
    assert!(stats.duration_ms <= 60_000);
}

#[tokio::test]
async fn test_bounded_cache_eviction() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("bounded_cache");
    let store = VectorStore::new_with_cache_options(
        db_path.to_str().unwrap(),
        Some(64),
        DatasetCacheConfig {
            max_cached_tables: Some(2),
        },
    )
    .await
    .unwrap();
    add_tools_table(&store, "a", 5, &["x"]).await;
    add_tools_table(&store, "b", 5, &["y"]).await;
    add_tools_table(&store, "c", 5, &["z"]).await;
    assert_eq!(store.count("a").await.unwrap(), 5);
    assert_eq!(store.count("b").await.unwrap(), 5);
    assert_eq!(store.count("c").await.unwrap(), 5);
}

#[tokio::test]
async fn test_create_index_background_finishes() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("bg_index");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 150, &["a", "b"]).await;
    assert!(!store.has_vector_index("t").await.unwrap());

    store.create_index_background("t");
    for _ in 0..30 {
        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;
        if store.has_vector_index("t").await.unwrap() {
            return;
        }
    }
    panic!("create_index_background did not create vector index within 15s");
}

#[tokio::test]
async fn test_compact_table_not_found() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("compact_missing");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();

    let err = store.compact("nonexistent").await.unwrap_err();
    let msg = format!("{}", err);
    assert!(msg.contains("not found") || msg.contains("Table"));
}

/// Snapshot: auto_index and compact API contract (has_* flags and compaction shape).
#[tokio::test]
async fn snapshot_maintenance_contract_v1() {
    use insta::assert_json_snapshot;

    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("maint_snap");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "skills", 200, &["git", "docker", "python"]).await;

    let auto_result = store
        .auto_index_if_needed_with_thresholds("skills", &IndexThresholds::default())
        .await
        .unwrap();
    let has_vector = store.has_vector_index("skills").await.unwrap();
    let has_fts = store.has_fts_index("skills").await.unwrap();
    let has_scalar = store.has_scalar_index("skills").await.unwrap();

    let compact_stats = store.compact("skills").await.unwrap();

    let view = serde_json::json!({
        "after_auto_index": {
            "has_vector_index": has_vector,
            "has_fts_index": has_fts,
            "has_scalar_index": has_scalar,
            "returned_stats": auto_result.is_some(),
        },
        "compaction": {
            "fragments_before": compact_stats.fragments_before,
            "fragments_after": compact_stats.fragments_after,
            "fragments_removed": compact_stats.fragments_removed,
        },
    });
    assert_json_snapshot!("maintenance_contract_v1", view);
}
