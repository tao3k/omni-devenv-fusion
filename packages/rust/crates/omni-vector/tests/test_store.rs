//! Tests for VectorStore - delete operations and core functionality.

use omni_vector::VectorStore;

#[tokio::test]
async fn test_delete_by_file_path_with_underscores() {
    // Create a temporary directory for the test database
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_delete");

    // Create vector store (VectorStore::new is async)
    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    // Add a document with a path containing underscores
    let test_id = "test_tool.test_function";
    let test_content = "Test content for delete";
    let test_path = "temp_skill/scripts/hello.py"; // Contains underscore
    let test_metadata = serde_json::json!({
        "skill_name": "test_tool",
        "tool_name": "test_function",
        "file_path": test_path,
        "function_name": "test_function",
        "keywords": ["test"],
        "file_hash": "abc123",
        "input_schema": "{}",
        "docstring": "Test function"
    })
    .to_string();

    // Add the document (use add_documents with single element)
    store
        .add_documents(
            "test_table",
            vec![test_id.to_string()],
            vec![vec![0.1; 1536]],
            vec![test_content.to_string()],
            vec![test_metadata],
        )
        .await
        .unwrap();

    // Verify it's there
    let count_before = store.count("test_table").await.unwrap();
    assert_eq!(count_before, 1, "Document should be added");

    // Delete by file path (with underscore)
    store
        .delete_by_file_path("test_table", vec![test_path.to_string()])
        .await
        .unwrap();

    // Verify it's deleted
    let count_after = store.count("test_table").await.unwrap();
    assert_eq!(
        count_after, 0,
        "Document should be deleted after calling delete_by_file_path"
    );
}

#[tokio::test]
async fn test_delete_by_file_path_multiple_paths() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_multi_delete");

    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    // Add multiple documents with different path formats
    let paths_and_ids = vec![
        ("path_with_underscore/file.py", "skill1.func1"),
        ("path/with/slashes/file.py", "skill2.func2"),
        ("path%with%percent/file.py", "skill3.func3"),
    ];

    for (path, id) in &paths_and_ids {
        let metadata = serde_json::json!({
            "file_path": path,
            "skill_name": "test",
            "tool_name": "test",
        })
        .to_string();

        store
            .add_documents(
                "multi_test",
                vec![id.to_string()],
                vec![vec![0.1; 1536]],
                vec!["content".to_string()],
                vec![metadata],
            )
            .await
            .unwrap();
    }

    let count_before = store.count("multi_test").await.unwrap();
    assert_eq!(count_before, 3);

    // Delete all paths
    let paths: Vec<String> = paths_and_ids.iter().map(|(p, _)| p.to_string()).collect();
    store
        .delete_by_file_path("multi_test", paths)
        .await
        .unwrap();

    let count_after = store.count("multi_test").await.unwrap();
    assert_eq!(count_after, 0);
}

#[tokio::test]
async fn test_delete_regression_sql_like_patterns() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_regression");

    let store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    // These paths contain characters that have special meaning in SQL LIKE
    let problematic_paths = vec![
        "my_skill/scripts/utils.py",
        "path%with%percent/script.js",
        "dir.with.dots/config.yaml",
    ];

    for (i, path) in problematic_paths.iter().enumerate() {
        let metadata = serde_json::json!({
            "file_path": path,
            "skill_name": format!("skill_{}", i),
            "tool_name": "test_func",
        })
        .to_string();

        store
            .add_documents(
                "regression_test",
                vec![format!("skill_{}.test_func", i)],
                vec![vec![0.1; 1536]],
                vec!["content".to_string()],
                vec![metadata],
            )
            .await
            .unwrap();
    }

    // Delete all problematic paths
    let paths: Vec<String> = problematic_paths.iter().map(|s| s.to_string()).collect();
    store
        .delete_by_file_path("regression_test", paths)
        .await
        .unwrap();

    // Verify all deleted
    let count = store.count("regression_test").await.unwrap();
    assert_eq!(
        count, 0,
        "All paths with SQL-like special chars should be deleted"
    );
}

#[tokio::test]
async fn test_replace_documents_rebuilds_table_snapshot() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("test_replace_docs");

    let mut store = VectorStore::new(db_path.to_str().unwrap(), Some(1536))
        .await
        .unwrap();

    store
        .add_documents(
            "skills",
            vec!["id1".to_string(), "id2".to_string()],
            vec![vec![0.1; 1536], vec![0.2; 1536]],
            vec!["content1".to_string(), "content2".to_string()],
            vec!["{}".to_string(), "{}".to_string()],
        )
        .await
        .unwrap();
    assert_eq!(store.count("skills").await.unwrap(), 2);

    store
        .replace_documents(
            "skills",
            vec!["id3".to_string()],
            vec![vec![0.3; 1536]],
            vec!["content3".to_string()],
            vec!["{}".to_string()],
        )
        .await
        .unwrap();

    // Old snapshot should be fully replaced.
    assert_eq!(store.count("skills").await.unwrap(), 1);
}
