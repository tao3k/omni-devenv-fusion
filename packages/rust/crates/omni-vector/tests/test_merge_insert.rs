//! Integration tests for merge-insert and version APIs.

use omni_vector::{SearchOptions, VectorStore};

#[tokio::test]
async fn test_merge_insert_documents_upsert_and_versions() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("merge_insert_store");
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(4))
        .await
        .unwrap();

    let table = "skills";
    store
        .add_documents(
            table,
            vec!["tool.a".to_string(), "tool.b".to_string()],
            vec![vec![1.0, 0.0, 0.0, 0.0], vec![0.0, 1.0, 0.0, 0.0]],
            vec!["old-a".to_string(), "old-b".to_string()],
            vec![
                serde_json::json!({"kind":"seed","rank":1}).to_string(),
                serde_json::json!({"kind":"seed","rank":2}).to_string(),
            ],
        )
        .await
        .unwrap();

    let version_before = store.get_dataset_version(table).await.unwrap();
    assert_eq!(store.count(table).await.unwrap(), 2);

    let merge_stats = store
        .merge_insert_documents(
            table,
            vec!["tool.b".to_string(), "tool.c".to_string()],
            vec![vec![0.0, 1.0, 0.0, 0.0], vec![0.0, 0.0, 1.0, 0.0]],
            vec!["new-b".to_string(), "new-c".to_string()],
            vec![
                serde_json::json!({"kind":"merged","rank":20}).to_string(),
                serde_json::json!({"kind":"merged","rank":30}).to_string(),
            ],
            "id",
        )
        .await
        .unwrap();

    assert_eq!(merge_stats.inserted, 1);
    assert_eq!(merge_stats.updated, 1);
    assert_eq!(merge_stats.deleted, 0);
    assert_eq!(store.count(table).await.unwrap(), 3);

    let results_b = store
        .search_optimized(
            table,
            vec![0.0, 1.0, 0.0, 0.0],
            3,
            SearchOptions {
                where_filter: Some("id = 'tool.b'".to_string()),
                ..SearchOptions::default()
            },
        )
        .await
        .unwrap();
    assert_eq!(results_b.len(), 1);
    assert_eq!(results_b[0].id, "tool.b");
    assert_eq!(results_b[0].content, "new-b");

    let versions = store.list_versions(table).await.unwrap();
    assert!(versions.len() >= 2);
    let version_after = store.get_dataset_version(table).await.unwrap();
    assert!(version_after > version_before);

    let info = store.get_table_info(table).await.unwrap();
    assert_eq!(info.num_rows, 3);
    assert!(info.fragment_count >= 1);

    let frag_stats = store.get_fragment_stats(table).await.unwrap();
    assert!(!frag_stats.is_empty());

    let old_snapshot = store.checkout_version(table, version_before).await.unwrap();
    assert_eq!(old_snapshot.count_rows(None).await.unwrap(), 2);
}
