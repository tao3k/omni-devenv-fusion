//! Tests for Phase 3 vector index: create_hnsw_index, create_optimal_vector_index.

use omni_vector::VectorStore;

async fn add_tools_table(store: &VectorStore, table: &str, n: usize, dim: usize) {
    let mut ids = Vec::with_capacity(n);
    let mut vectors = Vec::with_capacity(n);
    let mut contents = Vec::with_capacity(n);
    let mut metadatas = Vec::with_capacity(n);
    for i in 0..n {
        ids.push(format!("skill.cmd_{}", i));
        vectors.push(vec![0.1; dim]);
        contents.push(format!("content {}", i));
        metadatas.push(
            serde_json::json!({
                "skill_name": "skill",
                "category": "test",
                "file_path": "skill/scripts/x.py",
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
async fn test_create_hnsw_index_returns_stats() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("hnsw_stats");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 100, 64).await;

    let stats = store.create_hnsw_index("t").await.unwrap();

    assert_eq!(stats.column, "vector");
    assert_eq!(stats.index_type, "ivf_hnsw");
    assert!(stats.duration_ms <= 60_000);
}

#[tokio::test]
async fn test_create_hnsw_index_requires_min_rows() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("hnsw_min");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 10, 64).await;

    let err = store.create_hnsw_index("t").await.unwrap_err();
    let msg = format!("{}", err);
    assert!(msg.contains("50") || msg.contains("row"));
}

#[tokio::test]
async fn test_create_optimal_vector_index_small_uses_hnsw() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("optimal_small");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 500, 64).await;

    let stats = store.create_optimal_vector_index("t").await.unwrap();

    assert_eq!(stats.column, "vector");
    assert_eq!(stats.index_type, "ivf_hnsw");
}

#[tokio::test]
async fn test_create_optimal_vector_index_requires_min_rows() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("optimal_min");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 50, 64).await;

    let err = store.create_optimal_vector_index("t").await.unwrap_err();
    let msg = format!("{}", err);
    assert!(msg.contains("100") || msg.contains("row"));
}

#[tokio::test]
async fn test_create_optimal_vector_index_large_uses_ivf_flat() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("optimal_large");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 12_000, 64).await;

    let stats = store.create_optimal_vector_index("t").await.unwrap();

    assert_eq!(stats.column, "vector");
    assert_eq!(stats.index_type, "ivf_flat");
}

/// Snapshot: vector index API contract (hnsw and optimal small path).
#[tokio::test]
async fn snapshot_vector_index_contract_v1() {
    use insta::assert_json_snapshot;

    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("vec_snap");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "skills", 300, 64).await;

    let hnsw_stats = store.create_hnsw_index("skills").await.unwrap();
    let view = serde_json::json!({
        "hnsw": {
            "column": hnsw_stats.column,
            "index_type": hnsw_stats.index_type,
        },
    });
    assert_json_snapshot!("vector_index_contract_v1", view);
}
