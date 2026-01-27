//! Tests for Rust-Native Cortex: search_tools and load_tool_registry

use omni_vector::VectorStore;

fn clean_test_db(path: &std::path::Path) {
    if path.exists() {
        let _ = std::fs::remove_dir_all(path);
    }
}

#[tokio::test]
async fn test_search_tools_basic() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("cortex_test");
    clean_test_db(&db_path);

    let store = VectorStore::new(
        temp_dir.path().join("cortex_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Add some test documents with tool-like metadata
    let tools = vec![
        (
            "git.commit",
            "Commit changes to repository",
            r#"{"skill_name": "git", "tool_name": "commit", "type": "command", "command": "git.commit", "file_path": "git/scripts/commit.py", "keywords": ["git", "commit", "vcs"], "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}}}"#,
            vec![1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "git.branch",
            "Create or list branches",
            r#"{"skill_name": "git", "tool_name": "branch", "type": "command", "command": "git.branch", "file_path": "git/scripts/branch.py", "keywords": ["git", "branch", "vcs"], "input_schema": {"type": "object", "properties": {}}}"#,
            vec![0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "python.run",
            "Execute Python code",
            r#"{"skill_name": "python", "tool_name": "run", "type": "command", "command": "python.run", "file_path": "python/scripts/run.py", "keywords": ["python", "execute", "code"], "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}}}"#,
            vec![0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
    ];

    let ids: Vec<String> = tools.iter().map(|t| t.0.to_string()).collect();
    let contents: Vec<String> = tools.iter().map(|t| t.1.to_string()).collect();
    let metadatas: Vec<String> = tools.iter().map(|t| t.2.to_string()).collect();
    let vectors: Vec<Vec<f32>> = tools.iter().map(|t| t.3.clone()).collect();

    store
        .add_documents("tools", ids.clone(), vectors, contents, metadatas)
        .await
        .unwrap();

    // Search for git-related tools
    let query = vec![0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
    let results = store.search_tools("tools", &query, 5, 0.0).await.unwrap();

    assert!(!results.is_empty(), "Should find some tools");
    // Results should be sorted by score (descending)
    assert!(results.len() <= 5);
}

#[tokio::test]
async fn test_search_tools_with_threshold() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("threshold_test");
    clean_test_db(&db_path);

    let store = VectorStore::new(
        temp_dir.path().join("threshold_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Add tools with different embeddings
    let tools = vec![
        (
            "python.run",
            "Run Python code",
            r#"{"skill_name": "python", "tool_name": "run", "type": "command", "command": "python.run", "file_path": "python/run.py", "keywords": ["python"], "input_schema": {}}"#,
            vec![1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "rust.compile",
            "Compile Rust code",
            r#"{"skill_name": "rust", "tool_name": "compile", "type": "command", "command": "rust.compile", "file_path": "rust/compile.py", "keywords": ["rust"], "input_schema": {}}"#,
            vec![0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
    ];

    let ids: Vec<String> = tools.iter().map(|t| t.0.to_string()).collect();
    let contents: Vec<String> = tools.iter().map(|t| t.1.to_string()).collect();
    let metadatas: Vec<String> = tools.iter().map(|t| t.2.to_string()).collect();
    let vectors: Vec<Vec<f32>> = tools.iter().map(|t| t.3.clone()).collect();

    store
        .add_documents("tools", ids, vectors, contents, metadatas)
        .await
        .unwrap();

    // Query similar to Python (high score for python.run, low for rust.compile)
    let query = vec![0.95, 0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];

    // With high threshold, only python.run should be returned
    let results_high = store.search_tools("tools", &query, 5, 0.9).await.unwrap();

    assert!(results_high.len() <= 1);
}

#[tokio::test]
async fn test_load_tool_registry() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("registry_test");
    clean_test_db(&db_path);

    let store = VectorStore::new(
        temp_dir.path().join("registry_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Add some tools
    let tools = vec![
        (
            "git.commit",
            "Commit changes",
            r#"{"skill_name": "git", "tool_name": "commit", "type": "command", "command": "git.commit", "file_path": "git/commit.py", "keywords": ["git"], "input_schema": {"type": "object"}}"#,
            vec![0.0; 10],
        ),
        (
            "git.branch",
            "List branches",
            r#"{"skill_name": "git", "tool_name": "branch", "type": "command", "command": "git.branch", "file_path": "git/branch.py", "keywords": ["git"], "input_schema": {"type": "object"}}"#,
            vec![0.0; 10],
        ),
        (
            "python.run",
            "Run code",
            r#"{"skill_name": "python", "tool_name": "run", "type": "command", "command": "python.run", "file_path": "python/run.py", "keywords": ["python"], "input_schema": {"type": "object"}}"#,
            vec![0.0; 10],
        ),
    ];

    let ids: Vec<String> = tools.iter().map(|t| t.0.to_string()).collect();
    let contents: Vec<String> = tools.iter().map(|t| t.1.to_string()).collect();
    let metadatas: Vec<String> = tools.iter().map(|t| t.2.to_string()).collect();
    let vectors: Vec<Vec<f32>> = tools.iter().map(|t| t.3.clone()).collect();

    store
        .add_documents("tools", ids, vectors, contents, metadatas)
        .await
        .unwrap();

    // Load all tools for registry
    let registry = store.load_tool_registry("tools").await.unwrap();

    assert_eq!(registry.len(), 3);
    for tool in registry {
        // All tools should have score = 1.0 for registry load
        assert_eq!(tool.score, 1.0);
        // Verify fields are populated
        assert!(!tool.name.is_empty());
        assert!(!tool.skill_name.is_empty());
        assert!(!tool.tool_name.is_empty());
        assert!(!tool.file_path.is_empty());
    }
}

#[tokio::test]
async fn test_tool_search_result_structure() {
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("struct_test");
    clean_test_db(&db_path);

    let store = VectorStore::new(
        temp_dir.path().join("struct_test").to_str().unwrap(),
        Some(10),
    )
    .await
    .unwrap();

    // Add a tool
    store
        .add_documents(
            "tools",
            vec!["test.tool".to_string()],
            vec![vec![0.0; 10]],
            vec!["Test tool description".to_string()],
            vec![r#"{"skill_name": "test", "tool_name": "tool", "type": "command", "command": "test.tool", "file_path": "test.py", "keywords": ["test"], "input_schema": {"type": "object", "properties": {"arg": {"type": "string"}}}}"#.to_string()],
        )
        .await
        .unwrap();

    let results = store
        .search_tools("tools", &vec![0.0; 10], 1, 0.0)
        .await
        .unwrap();

    assert_eq!(results.len(), 1);
    let result = &results[0];

    // Verify all fields are correctly populated
    assert_eq!(result.name, "test.tool");
    assert_eq!(result.skill_name, "test");
    assert_eq!(result.tool_name, "tool");
    assert_eq!(result.file_path, "test.py");
    assert_eq!(result.keywords, vec!["test"]);
    assert!(result.score > 0.0);
    assert!(result.description.contains("Test"));
}
