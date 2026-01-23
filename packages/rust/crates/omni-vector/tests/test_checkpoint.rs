//! Tests for checkpoint store operations.

use omni_vector::CheckpointRecord;
use omni_vector::CheckpointStore;

#[tokio::test]
async fn test_checkpoint_roundtrip() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = CheckpointStore::new(
        temp_dir.path().join("checkpoints").to_str().unwrap(),
        Some(1536),
    )
    .await
    .unwrap();

    let record = CheckpointRecord {
        checkpoint_id: "cp-123".to_string(),
        thread_id: "session-1".to_string(),
        parent_id: None,
        timestamp: 1234567890.0,
        content: r#"{"messages": [], "current_plan": "test plan"}"#.to_string(),
        embedding: None,
        metadata: None,
    };

    // Save checkpoint
    store.save_checkpoint("test_table", &record).await.unwrap();

    // Get latest
    let latest = store.get_latest("test_table", "session-1").await.unwrap();
    assert!(latest.is_some());
    assert!(latest.unwrap().contains("test plan"));

    // Get history
    let history = store
        .get_history("test_table", "session-1", 10)
        .await
        .unwrap();
    assert_eq!(history.len(), 1);

    // Count
    let count = store.count("test_table", "session-1").await.unwrap();
    assert_eq!(count, 1);

    // Delete thread
    let deleted = store
        .delete_thread("test_table", "session-1")
        .await
        .unwrap();
    assert_eq!(deleted, 1);

    // Verify deleted
    let latest = store.get_latest("test_table", "session-1").await.unwrap();
    assert!(latest.is_none());
}

#[tokio::test]
async fn test_multiple_checkpoints() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = CheckpointStore::new(
        temp_dir.path().join("checkpoints").to_str().unwrap(),
        Some(1536),
    )
    .await
    .unwrap();

    // Save multiple checkpoints with different timestamps
    for i in 0..5 {
        let record = CheckpointRecord {
            checkpoint_id: format!("cp-{}", i),
            thread_id: "session-2".to_string(),
            parent_id: if i > 0 {
                Some(format!("cp-{}", i - 1))
            } else {
                None
            },
            timestamp: 1000.0 + (i as f64 * 100.0),
            content: format!(r#"{{"step": {}}}"#, i),
            embedding: None,
            metadata: None,
        };
        store.save_checkpoint("test_table", &record).await.unwrap();
    }

    // Get history (should be in reverse chronological order)
    let history = store
        .get_history("test_table", "session-2", 10)
        .await
        .unwrap();
    assert_eq!(history.len(), 5);

    // Verify order (newest first)
    assert!(history[0].contains(r##""step": 4"##));
    assert!(history[4].contains(r##""step": 0"##));
}

#[tokio::test]
async fn test_search_similar() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = CheckpointStore::new(
        temp_dir.path().join("search_test").to_str().unwrap(),
        Some(10), // Smaller dimension for faster testing
    )
    .await
    .unwrap();

    // Save checkpoints with known embeddings
    let test_cases = vec![
        (
            "cp-1",
            "Python programming help",
            vec![1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "cp-2",
            "Rust compiler error",
            vec![0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "cp-3",
            "Database connection",
            vec![0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
    ];

    for (id, content, embedding) in &test_cases {
        let record = CheckpointRecord {
            checkpoint_id: id.to_string(),
            thread_id: "test-session".to_string(),
            parent_id: None,
            timestamp: 1000.0,
            content: format!(r#"{{"plan": "{content}"}}"#),
            embedding: Some(embedding.clone()),
            metadata: None,
        };
        store
            .save_checkpoint("search_table", &record)
            .await
            .unwrap();
    }

    // Search for similar to "Python code"
    let query = vec![0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
    let results = store
        .search("search_table", &query, 5, None, None)
        .await
        .unwrap();

    assert_eq!(results.len(), 3);
    // First result should be "Python programming help" (closest to query)
    assert!(results[0].0.contains("Python programming help"));
    // Last result should be "Database connection" (farthest)
    assert!(results[2].0.contains("Database connection"));
    // Verify distances are increasing
    assert!(results[0].2 <= results[1].2);
    assert!(results[1].2 <= results[2].2);
}

#[tokio::test]
async fn test_search_with_filter() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = CheckpointStore::new(
        temp_dir.path().join("filter_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Save checkpoints with metadata
    for (i, success) in [true, false, true].iter().enumerate() {
        let record = CheckpointRecord {
            checkpoint_id: format!("cp-{}", i),
            thread_id: "session-filter".to_string(),
            parent_id: None,
            timestamp: 1000.0 + (i as f64),
            content: format!(r#"{{"plan": "task {}", "success": {}}}"#, i, success),
            embedding: Some(vec![0.0; 10]),
            metadata: Some(format!(r#"{{"success": {}}}"#, success)),
        };
        store
            .save_checkpoint("filter_table", &record)
            .await
            .unwrap();
    }

    // Filter by success=true
    let query = vec![0.0; 10];
    let filter = serde_json::json!({"success": true});
    let results = store
        .search("filter_table", &query, 5, None, Some(filter))
        .await
        .unwrap();

    assert_eq!(results.len(), 2);
    for (_, metadata, _) in &results {
        let meta: serde_json::Value = serde_json::from_str(metadata).unwrap();
        assert_eq!(meta.get("success").unwrap(), true);
    }
}
