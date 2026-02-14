//! Tests for Phase 4 partitioning: suggest_partition_column and add_documents_partitioned.

use omni_vector::VectorStore;

async fn add_tools_table(store: &VectorStore, table: &str, n: usize) {
    let mut ids = Vec::with_capacity(n);
    let mut vectors = Vec::with_capacity(n);
    let mut contents = Vec::with_capacity(n);
    let mut metadatas = Vec::with_capacity(n);
    for i in 0..n {
        ids.push(format!("skill.cmd_{}", i));
        vectors.push(vec![0.1; 64]);
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
async fn test_suggest_partition_column_none_for_missing_table() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("part_missing");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();

    let out = store.suggest_partition_column("nonexistent").await.unwrap();
    assert_eq!(out, None);
}

#[tokio::test]
async fn test_suggest_partition_column_none_for_small_table() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("part_small");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 100).await;

    let out = store.suggest_partition_column("t").await.unwrap();
    assert_eq!(out, None);
}

#[tokio::test]
async fn test_suggest_partition_column_some_for_large_tools_table() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("part_large");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 10_050).await;

    let out = store.suggest_partition_column("t").await.unwrap();
    assert_eq!(out.as_deref(), Some("skill_name"));
}

/// Snapshot: suggested partition column for large tools table.
#[tokio::test]
async fn snapshot_partition_suggestion_contract_v1() {
    use insta::assert_json_snapshot;

    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("part_snap");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "skills", 10_050).await;

    let suggested = store.suggest_partition_column("skills").await.unwrap();

    let view = serde_json::json!({
        "suggested_column": suggested,
        "threshold": 10_000_usize,
    });
    assert_json_snapshot!("partition_suggestion_contract_v1", view);
}

#[tokio::test]
async fn test_add_documents_partitioned_groups_by_column() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("part_write");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();

    let ids = vec!["a.1".to_string(), "a.2".to_string(), "b.1".to_string()];
    let vectors = vec![vec![0.1f32; 64], vec![0.2f32; 64], vec![0.3f32; 64]];
    let contents = vec!["c1".to_string(), "c2".to_string(), "c3".to_string()];
    let metadatas = vec![
        serde_json::json!({"skill_name": "a", "category": "x"}).to_string(),
        serde_json::json!({"skill_name": "a", "category": "x"}).to_string(),
        serde_json::json!({"skill_name": "b", "category": "y"}).to_string(),
    ];

    store
        .add_documents_partitioned("t", "skill_name", ids, vectors, contents, metadatas)
        .await
        .unwrap();

    let n = store.count("t").await.unwrap();
    assert_eq!(n, 3);

    let fragments = store.get_fragment_stats("t").await.unwrap();
    assert!(
        fragments.len() >= 2,
        "partitioned write should produce at least 2 fragments (one per partition value)"
    );
}
