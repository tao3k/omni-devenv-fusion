//! Tests for Phase 5 observability: analyze_table_health.

use omni_vector::{Recommendation, VectorStore};

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
async fn test_analyze_table_health_returns_report() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("health");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 50).await;

    let report = store.analyze_table_health("t").await.unwrap();

    assert_eq!(report.row_count, 50);
    assert!(report.fragment_count >= 1);
    assert!(report.fragmentation_ratio >= 0.0);
    assert!(!report.recommendations.is_empty());
}

#[tokio::test]
async fn test_analyze_table_health_recommends_create_indices_when_missing() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("health_idx");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "t", 1500).await;

    let report = store.analyze_table_health("t").await.unwrap();

    assert!(
        report
            .recommendations
            .contains(&Recommendation::CreateIndices)
    );
}

#[tokio::test]
async fn test_analyze_table_health_table_not_found() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("health_missing");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();

    let err = store.analyze_table_health("nonexistent").await.unwrap_err();
    let msg = format!("{}", err);
    assert!(msg.contains("not found") || msg.contains("Table"));
}

#[tokio::test]
async fn test_query_metrics_in_process_record_and_read() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("qm");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();

    let before = store.get_query_metrics("t").await.unwrap();
    assert_eq!(before.query_count, 0);
    assert!(before.last_query_ms.is_none());

    store.record_query("t", 42);
    let after = store.get_query_metrics("t").await.unwrap();
    assert_eq!(after.query_count, 1);
    assert_eq!(after.last_query_ms, Some(42));

    store.record_query("t", 100);
    let again = store.get_query_metrics("t").await.unwrap();
    assert_eq!(again.query_count, 2);
    assert_eq!(again.last_query_ms, Some(100));
}

/// Snapshot: table health report shape (indices and recommendations).
#[tokio::test]
async fn snapshot_observability_contract_v1() {
    use insta::assert_json_snapshot;

    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("obs_snap");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(64))
        .await
        .unwrap();
    add_tools_table(&store, "skills", 50).await;

    let report = store.analyze_table_health("skills").await.unwrap();

    let view = serde_json::json!({
        "row_count": report.row_count,
        "fragment_count": report.fragment_count,
        "fragmentation_ratio": report.fragmentation_ratio,
        "indices_count": report.indices_status.len(),
        "recommendations": report.recommendations,
    });
    assert_json_snapshot!("observability_contract_v1", view);
}
