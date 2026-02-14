//! Tests for VectorStore path handling and dataset creation.
//!
//! These tests ensure that:
//! 1. Dataset creation works correctly even with pre-existing empty directories
//! 2. drop_table properly cleans up both LanceDB and keyword index data
//! 3. Reindex workflows work correctly after dropping tables

use omni_vector::VectorStore;

/// Helper to verify LanceDB directory has valid structure
fn has_lance_data(path: &std::path::Path) -> bool {
    if !path.exists() {
        return false;
    }
    // Check for LanceDB version directory or data directory
    path.join("_versions").exists() || path.join("data").exists()
}

#[tokio::test]
async fn test_create_store_with_lance_extension() {
    // Test creating store with .lance extension path
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_store.lance");

    // Create vector store with .lance extension
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    // Verify table_path returns the base_path when it ends with .lance
    let table_path = store.table_path("test_table");
    assert_eq!(
        table_path, db_path,
        "table_path should return base_path when it ends with .lance"
    );
}

#[tokio::test]
async fn test_add_documents_creates_dataset() {
    // Test that add_documents creates the dataset properly
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_docs.lance");

    // Create vector store
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    // Add documents - this should create the dataset
    store
        .add_documents(
            "documents",
            vec!["doc1".to_string()],
            vec![vec![0.1; 1536]],
            vec!["Test content".to_string()],
            vec![r#"{"test": true}"#.to_string()],
        )
        .await
        .unwrap();

    // Verify the dataset was created
    let count = store.count("documents").await.unwrap();
    assert_eq!(count, 1, "Should have added one document");

    // Verify the directory now contains LanceDB data
    assert!(
        db_path.exists(),
        "The .lance directory should exist after adding documents"
    );

    // Verify LanceDB structure (_versions, data directories)
    assert!(
        has_lance_data(&db_path),
        "Directory should contain LanceDB data (_versions or data)"
    );
}

#[tokio::test]
async fn test_drop_table_clears_dataset() {
    // Test that drop_table properly removes the dataset
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_drop.lance");

    // Create store and add a document
    let mut store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    store
        .add_documents(
            "test",
            vec!["id1".to_string()],
            vec![vec![0.1; 1536]],
            vec!["Content".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();

    // Verify data is there
    assert_eq!(store.count("test").await.unwrap(), 1);

    // Drop the table
    store.drop_table("test").await.unwrap();

    // After dropping, add_documents should recreate the dataset
    store
        .add_documents(
            "test",
            vec!["id2".to_string()],
            vec![vec![0.2; 1536]],
            vec!["New content".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();

    // Verify data is there again
    assert_eq!(store.count("test").await.unwrap(), 1);
}

#[tokio::test]
async fn test_memory_mode_path_computation() {
    // Test that memory mode computes paths correctly
    let store = VectorStore::new(":memory:", Some(1536)).await.unwrap();

    // Verify memory mode path computation
    let table_path = store.table_path("mem_test");
    assert_eq!(
        table_path.to_string_lossy(),
        ":memory:_mem_test",
        "Memory mode should use :memory: prefix"
    );
}

#[tokio::test]
async fn test_memory_mode_add_documents_twice_without_dataset_exists_error() {
    // Regression: memory mode must not try Dataset::write over an existing dataset.
    // Each store gets a unique temp path (omni_lance/{id}/{table}) so no cross-run collision.
    let store = VectorStore::new(":memory:", Some(1536)).await.unwrap();

    store
        .add_documents(
            "skills",
            vec!["id1".to_string()],
            vec![vec![0.1; 1536]],
            vec!["content1".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();

    // Second write to same table should append/open, not fail with "Dataset already exists".
    store
        .add_documents(
            "skills",
            vec!["id2".to_string()],
            vec![vec![0.2; 1536]],
            vec!["content2".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();
}

#[tokio::test]
async fn test_recreate_after_empty_directory() {
    // Regression test: ensure Dataset::write works even when directory exists but is empty
    // This was a bug where std::fs::create_dir_all created empty directories,
    // causing LanceDB to think a dataset already existed
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_empty_recreate.lance");

    // Create store
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    // Pre-create empty directory (simulating the bug scenario)
    std::fs::create_dir_all(&db_path).unwrap();
    assert!(db_path.exists(), "Directory should exist");
    assert!(
        !has_lance_data(&db_path),
        "Directory should be empty (no LanceDB data)"
    );

    // Add documents - this should succeed despite empty directory
    store
        .add_documents(
            "test",
            vec!["id1".to_string()],
            vec![vec![0.1; 1536]],
            vec!["Content".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();

    // Verify the dataset was created correctly
    let count = store.count("test").await.unwrap();
    assert_eq!(count, 1, "Should have added one document");

    // Verify LanceDB structure exists
    assert!(
        has_lance_data(&db_path),
        "Directory should now contain LanceDB data"
    );
}

#[tokio::test]
async fn test_reindex_after_drop_with_keyword_index() {
    // Regression test: ensure drop_table properly removes keyword index directory
    // This was the bug: drop_table only cleared the Arc reference but didn't delete the directory,
    // causing stale keyword index data to persist across reindex operations
    let temp_dir = tempfile::tempdir().unwrap();
    // Use a directory path (not .lance) so keyword index is at base_path/keyword_index
    let db_path = temp_dir.path().join("test_reindex_kw");

    // Create store with keyword index enabled
    let mut store = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1536),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add initial documents
    store
        .add_documents(
            "skills",
            vec!["tool1".to_string()],
            vec![vec![0.1; 1536]],
            vec!["Initial tool description".to_string()],
            vec![r#"{"skill_name": "test", "tool_name": "test_tool1", "command": "tool1", "keywords": ["test"], "intents": []}"#.to_string()],
        )
        .await
        .unwrap();

    // Verify LanceDB table directory has data (skills.lance)
    let lance_path = db_path.join("skills.lance");
    assert!(
        has_lance_data(&lance_path),
        "LanceDB directory should have data after add_documents"
    );

    // Verify keyword index directory exists at base_path/keyword_index
    let kw_path = db_path.join("keyword_index");
    assert!(
        kw_path.exists(),
        "Keyword index directory should exist after add_documents"
    );

    // Drop the table
    store.drop_table("skills").await.unwrap();

    // Verify keyword index reference is cleared
    assert!(
        store.keyword_index.is_none(),
        "Keyword index reference should be None after drop"
    );

    // Verify keyword index DIRECTORY was removed (this is the key fix!)
    assert!(
        !kw_path.exists(),
        "Keyword index directory should be REMOVED after drop (not just reference cleared)"
    );

    // Verify LanceDB table directory was also removed
    assert!(
        !lance_path.exists(),
        "LanceDB directory should be removed after drop"
    );

    // Recreate store (simulating what Python code does with new PyVectorStore)
    let store2 = VectorStore::new_with_keyword_index(
        db_path.to_str().unwrap(),
        Some(1536),
        true,
        None,
        None,
    )
    .await
    .unwrap();

    // Add new documents with new store instance
    store2
        .add_documents(
            "skills",
            vec!["tool2".to_string()],
            vec![vec![0.2; 1536]],
            vec!["New tool description".to_string()],
            vec![r#"{"skill_name": "new", "tool_name": "new_tool2", "command": "tool2", "keywords": ["new"], "intents": []}"#.to_string()],
        )
        .await
        .unwrap();

    // Verify LanceDB data exists again
    assert!(
        has_lance_data(&lance_path),
        "LanceDB directory should have data after reindex"
    );

    // Verify keyword index was recreated
    let kw_path_new = db_path.join("keyword_index");
    assert!(
        kw_path_new.exists(),
        "Keyword index directory should be recreated after reindex with new store"
    );

    // Verify data was added to LanceDB
    let count = store2.count("skills").await.unwrap();
    assert_eq!(count, 1, "Should have added one document after reindex");
}

#[tokio::test]
async fn test_multiple_cycles_of_drop_and_recreate() {
    // Stress test: multiple cycles of drop and recreate
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_multi_cycle.lance");

    let mut store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    for cycle in 1..=3 {
        // Add data
        store
            .add_documents(
                "test",
                vec![format!("id_cycle{cycle}")],
                vec![vec![0.1; 1536]],
                vec![format!("Content from cycle {cycle}")],
                vec!["{}".to_string()],
            )
            .await
            .unwrap();

        // Verify
        assert_eq!(
            store.count("test").await.unwrap(),
            1,
            "Should have 1 document in cycle {cycle}"
        );

        // Drop
        store.drop_table("test").await.unwrap();

        // Verify empty
        assert_eq!(
            store.count("test").await.unwrap(),
            0,
            "Should be empty after drop in cycle {cycle}"
        );
    }

    // Final add
    store
        .add_documents(
            "test",
            vec!["final_id".to_string()],
            vec![vec![0.9; 1536]],
            vec!["Final content".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();

    assert_eq!(store.count("test").await.unwrap(), 1);
}
