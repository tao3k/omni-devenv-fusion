//! Tests for checkpoint store operations.

use omni_vector::CheckpointRecord;
use omni_vector::CheckpointStore;

/// Helper to clean up any existing test database before creating a new one
fn clean_test_db(path: &std::path::Path) {
    if path.exists() {
        let _ = std::fs::remove_dir_all(path);
    }
}

#[tokio::test]
async fn test_checkpoint_roundtrip() {
    let temp_dir = tempfile::tempdir().unwrap();
    // Clean up any existing database with the same path
    let db_path = temp_dir.path().join("checkpoints");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
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
    let db_path = temp_dir.path().join("checkpoints");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
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
    let db_path = temp_dir.path().join("search_test");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
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
    let db_path = temp_dir.path().join("filter_test");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
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

// =============================================================================
// Predicate Push-down Tests (thread_id as first-class column)
// =============================================================================

#[tokio::test]
async fn test_thread_id_isolation() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("isolation_test");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("isolation_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Save checkpoints for different threads
    let threads = vec!["thread-a", "thread-b", "thread-c"];
    for thread in &threads {
        for j in 0..3 {
            let record = CheckpointRecord {
                checkpoint_id: format!("{}-cp-{}", thread, j),
                thread_id: thread.to_string(),
                parent_id: None,
                timestamp: 1000.0 + (j as f64),
                content: format!(r#"{{"thread": "{thread}", "step": {}}}"#, j),
                embedding: Some(vec![0.0; 10]),
                metadata: None,
            };
            store
                .save_checkpoint("isolation_table", &record)
                .await
                .unwrap();
        }
    }

    // Each thread should have exactly 3 checkpoints
    for thread in threads {
        let count = store.count("isolation_table", thread).await.unwrap();
        assert_eq!(count, 3, "Thread {} should have 3 checkpoints", thread);

        let latest = store.get_latest("isolation_table", thread).await.unwrap();
        assert!(latest.is_some());
        let latest_content: serde_json::Value = serde_json::from_str(&latest.unwrap()).unwrap();
        assert_eq!(latest_content["thread"].as_str().unwrap(), thread);
    }
}

#[tokio::test]
async fn test_search_with_thread_id_filter() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("thread_search_test");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("thread_search_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Save checkpoints for different threads with known embeddings
    // Thread "python" has embeddings similar to query
    let python_records = vec![
        (
            "py-cp-1",
            "python-thread",
            vec![1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "py-cp-2",
            "python-thread",
            vec![0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
    ];

    // Thread "rust" has different embeddings
    let rust_records = vec![
        (
            "rust-cp-1",
            "rust-thread",
            vec![0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "rust-cp-2",
            "rust-thread",
            vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
    ];

    for (id, thread, emb) in python_records.iter().chain(rust_records.iter()) {
        let record = CheckpointRecord {
            checkpoint_id: id.to_string(),
            thread_id: thread.to_string(),
            parent_id: None,
            timestamp: 1000.0,
            content: format!(r#"{{"lang": "{thread}"}}"#),
            embedding: Some(emb.clone()),
            metadata: None,
        };
        store
            .save_checkpoint("thread_search_table", &record)
            .await
            .unwrap();
    }

    // Query similar to Python embeddings
    let query = vec![0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];

    // Without thread filter - should return all 4 results
    let all_results = store
        .search("thread_search_table", &query, 5, None, None)
        .await
        .unwrap();
    assert_eq!(all_results.len(), 4);

    // With thread filter - should only return Python thread results
    let python_results = store
        .search(
            "thread_search_table",
            &query,
            5,
            Some("python-thread"),
            None,
        )
        .await
        .unwrap();
    assert_eq!(python_results.len(), 2);
    for (content, _, _) in &python_results {
        assert!(content.contains("python"), "Expected Python thread results");
    }

    // With rust thread filter - should return 0 results (no similarity)
    let rust_results = store
        .search("thread_search_table", &query, 5, Some("rust-thread"), None)
        .await
        .unwrap();
    // Rust embeddings are orthogonal, should have high distance but still returned
    assert_eq!(rust_results.len(), 2);
}

#[tokio::test]
async fn test_get_history_thread_isolation() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("history_isolation");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("history_isolation").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Interleave checkpoints from different threads
    let interleaved_records = vec![
        ("cp-1", "thread-1", 1001.0),
        ("cp-2", "thread-2", 1002.0),
        ("cp-3", "thread-1", 1003.0),
        ("cp-4", "thread-2", 1004.0),
        ("cp-5", "thread-1", 1005.0),
    ];

    for (id, thread, ts) in interleaved_records {
        let record = CheckpointRecord {
            checkpoint_id: id.to_string(),
            thread_id: thread.to_string(),
            parent_id: None,
            timestamp: ts,
            content: format!(r#"{{"id": "{id}"}}"#),
            embedding: None,
            metadata: None,
        };
        store
            .save_checkpoint("history_table", &record)
            .await
            .unwrap();
    }

    // Get history for thread-1 - should get 3 checkpoints in reverse order
    let history_1 = store
        .get_history("history_table", "thread-1", 10)
        .await
        .unwrap();
    assert_eq!(history_1.len(), 3);
    // Verify order (newest first)
    assert!(history_1[0].contains("cp-5"));
    assert!(history_1[1].contains("cp-3"));
    assert!(history_1[2].contains("cp-1"));

    // Get history for thread-2 - should get 2 checkpoints
    let history_2 = store
        .get_history("history_table", "thread-2", 10)
        .await
        .unwrap();
    assert_eq!(history_2.len(), 2);
    assert!(history_2[0].contains("cp-4"));
    assert!(history_2[1].contains("cp-2"));
}

#[tokio::test]
async fn test_count_thread_isolation() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("count_isolation");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("count_isolation").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Create varying number of checkpoints per thread
    let thread_counts = vec![("thread-a", 5), ("thread-b", 2), ("thread-c", 8)];

    for (thread, count) in &thread_counts {
        for i in 0..*count {
            let record = CheckpointRecord {
                checkpoint_id: format!("{}-cp-{}", thread, i),
                thread_id: thread.to_string(),
                parent_id: None,
                timestamp: 1000.0 + (i as f64),
                content: format!(r#"{{"n": {}}}"#, i),
                embedding: None,
                metadata: None,
            };
            store.save_checkpoint("count_table", &record).await.unwrap();
        }
    }

    // Verify counts
    for (thread, expected_count) in &thread_counts {
        let actual_count = store.count("count_table", thread).await.unwrap();
        assert_eq!(
            actual_count, *expected_count as u32,
            "Thread {} count mismatch",
            thread
        );
    }
}

#[tokio::test]
async fn test_delete_thread_isolation() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("delete_isolation");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("delete_isolation").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Create checkpoints for multiple threads
    let threads = vec!["keep-thread", "delete-me"];
    for thread in &threads {
        for i in 0..3 {
            let record = CheckpointRecord {
                checkpoint_id: format!("{}-cp-{}", thread, i),
                thread_id: thread.to_string(),
                parent_id: None,
                timestamp: 1000.0 + (i as f64),
                content: format!(r#"{{"thread": "{thread}"}}"#),
                embedding: None,
                metadata: None,
            };
            store
                .save_checkpoint("delete_table", &record)
                .await
                .unwrap();
        }
    }

    // Initial counts
    assert_eq!(store.count("delete_table", "keep-thread").await.unwrap(), 3);
    assert_eq!(store.count("delete_table", "delete-me").await.unwrap(), 3);

    // Delete "delete-me" thread
    let deleted = store
        .delete_thread("delete_table", "delete-me")
        .await
        .unwrap();
    assert_eq!(deleted, 3);

    // Verify only "keep-thread" remains
    assert_eq!(store.count("delete_table", "keep-thread").await.unwrap(), 3);
    assert_eq!(store.count("delete_table", "delete-me").await.unwrap(), 0);

    // Verify get_latest returns None for deleted thread
    let latest_deleted = store.get_latest("delete_table", "delete-me").await.unwrap();
    assert!(latest_deleted.is_none());
}

#[tokio::test]
async fn test_get_latest_timestamp_order() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("latest_timestamp");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("latest_timestamp").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Save checkpoints with non-sequential timestamps
    let records = vec![
        ("cp-1", "thread-x", 3000.0),
        ("cp-2", "thread-x", 1000.0), // Earlier
        ("cp-3", "thread-x", 2000.0), // Middle
    ];

    for (id, thread, ts) in records {
        let record = CheckpointRecord {
            checkpoint_id: id.to_string(),
            thread_id: thread.to_string(),
            parent_id: None,
            timestamp: ts,
            content: format!(r#"{{"id": "{id}"}}"#),
            embedding: None,
            metadata: None,
        };
        store
            .save_checkpoint("latest_table", &record)
            .await
            .unwrap();
    }

    // Get latest - should return cp-1 (highest timestamp 3000)
    let latest = store.get_latest("latest_table", "thread-x").await.unwrap();
    assert!(latest.is_some());
    let latest_content: serde_json::Value = serde_json::from_str(&latest.unwrap()).unwrap();
    assert_eq!(latest_content["id"].as_str().unwrap(), "cp-1");
}

#[tokio::test]
async fn test_cleanup_orphan_checkpoints() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("orphan_test");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("orphan_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Create valid checkpoints with proper parent chain
    let valid_records = vec![
        ("cp-1", "valid-thread", None, 1000.0),
        ("cp-2", "valid-thread", Some("cp-1"), 1001.0),
        ("cp-3", "valid-thread", Some("cp-2"), 1002.0),
    ];

    for (id, thread, parent, ts) in &valid_records {
        let record = CheckpointRecord {
            checkpoint_id: id.to_string(),
            thread_id: thread.to_string(),
            parent_id: parent.map(|s| s.to_string()),
            timestamp: *ts,
            content: format!(r#"{{"id": "{id}"}}"#),
            embedding: None,
            metadata: None,
        };
        store
            .save_checkpoint("orphan_table", &record)
            .await
            .unwrap();
    }

    // Create orphan checkpoints (UUID patterns indicating interrupted tasks)
    // Using proper UUID format: 8-4-4-4-12 (hex chars only)
    let orphan_records: Vec<(&str, &str, Option<&str>, f64)> = vec![
        (
            "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "orphan-thread-1",
            None,
            2000.0,
        ),
        (
            "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "orphan-thread-2",
            None,
            2001.0,
        ),
    ];

    for (id, thread, parent, ts) in &orphan_records {
        let record = CheckpointRecord {
            checkpoint_id: id.to_string(),
            thread_id: thread.to_string(),
            parent_id: parent.map(|s| s.to_string()),
            timestamp: *ts,
            content: format!(r#"{{"orphan": "{id}"}}"#),
            embedding: None,
            metadata: None,
        };
        store
            .save_checkpoint("orphan_table", &record)
            .await
            .unwrap();
    }

    // Dry run should find 2 orphans
    let found = store
        .cleanup_orphan_checkpoints("orphan_table", true)
        .await
        .unwrap();
    assert_eq!(found, 2, "Should find 2 orphan checkpoints");

    // Actual cleanup
    let removed = store
        .cleanup_orphan_checkpoints("orphan_table", false)
        .await
        .unwrap();
    assert_eq!(removed, 2, "Should remove 2 orphan checkpoints");

    // Verify orphans are gone
    let orphan_count = store
        .count("orphan_table", "orphan-thread-1")
        .await
        .unwrap();
    assert_eq!(orphan_count, 0);

    // Verify valid checkpoints still exist
    let valid_count = store.count("orphan_table", "valid-thread").await.unwrap();
    assert_eq!(valid_count, 3);
}

#[tokio::test]
async fn test_force_recover() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("force_recover_test");
    clean_test_db(&db_path);

    let mut store = CheckpointStore::new(
        temp_dir.path().join("force_recover_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Create some checkpoints
    let record = CheckpointRecord {
        checkpoint_id: "cp-1".to_string(),
        thread_id: "test-thread".to_string(),
        parent_id: None,
        timestamp: 1000.0,
        content: r#"{"data": "before"}"#.to_string(),
        embedding: None,
        metadata: None,
    };
    store.save_checkpoint("force_table", &record).await.unwrap();

    // Verify data exists
    let count_before = store.count("force_table", "test-thread").await.unwrap();
    assert_eq!(count_before, 1);

    // Force recover (discard all data)
    store.force_recover("force_table").await.unwrap();

    // Verify data is gone
    let count_after = store.count("force_table", "test-thread").await.unwrap();
    assert_eq!(count_after, 0);

    // Should be able to add new checkpoints
    let record2 = CheckpointRecord {
        checkpoint_id: "cp-new".to_string(),
        thread_id: "test-thread".to_string(),
        parent_id: None,
        timestamp: 2000.0,
        content: r#"{"data": "after"}"#.to_string(),
        embedding: None,
        metadata: None,
    };
    store
        .save_checkpoint("force_table", &record2)
        .await
        .unwrap();

    let latest = store
        .get_latest("force_table", "test-thread")
        .await
        .unwrap();
    assert!(latest.is_some());
    assert!(latest.unwrap().contains("after"));
}

#[tokio::test]
async fn test_corruption_detection() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("corrupt_test");
    clean_test_db(&db_path);

    // Create store and add data
    {
        let store = CheckpointStore::new(
            temp_dir.path().join("corrupt_test").to_str().unwrap(),
            Some(10),
        )
        .await
        .unwrap();

        let record = CheckpointRecord {
            checkpoint_id: "cp-1".to_string(),
            thread_id: "session".to_string(),
            parent_id: None,
            timestamp: 1000.0,
            content: r#"{"step": 1}"#.to_string(),
            embedding: None,
            metadata: None,
        };
        store
            .save_checkpoint("detect_table", &record)
            .await
            .unwrap();
    }

    // Corrupt by removing _versions directory
    let table_path = temp_dir.path().join("corrupt_test.lance");
    let versions_path = table_path.join("_versions");
    if versions_path.exists() {
        std::fs::remove_dir_all(&versions_path).unwrap();
    }

    // Verify corruption is detected when creating new store
    let mut store = CheckpointStore::new(
        temp_dir.path().join("corrupt_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Force recover to get a working store
    store.force_recover("detect_table").await.unwrap();

    // Verify store is usable after recovery
    let count = store.count("detect_table", "session").await.unwrap();
    assert_eq!(count, 0, "Should have 0 checkpoints after recovery");

    // Add new checkpoint
    let record = CheckpointRecord {
        checkpoint_id: "cp-new".to_string(),
        thread_id: "session".to_string(),
        parent_id: None,
        timestamp: 2000.0,
        content: r#"{"step": "new"}"#.to_string(),
        embedding: None,
        metadata: None,
    };
    store
        .save_checkpoint("detect_table", &record)
        .await
        .unwrap();

    let latest = store.get_latest("detect_table", "session").await.unwrap();
    assert!(latest.is_some());
    assert!(latest.unwrap().contains("new"));
}
