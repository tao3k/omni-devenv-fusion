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
    let results = store
        .search_tools("tools", &query, None, 5, 0.0)
        .await
        .unwrap();

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
    let results_high = store
        .search_tools("tools", &query, None, 5, 0.9)
        .await
        .unwrap();

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
        .search_tools("tools", &vec![0.0; 10], None, 1, 0.0)
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

#[tokio::test]
async fn test_search_tools_weighted_rrf() {
    // Test that Weighted RRF fusion works correctly in search_tools
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("wrrf_test");
    clean_test_db(&db_path);

    // Create store WITH keyword index
    let store = VectorStore::new_with_keyword_index(
        temp_dir.path().join("wrrf_test").to_str().unwrap(),
        Some(10),
        true, // enable keyword index
    )
    .await
    .unwrap();

    // Add git-related tools with keyword index
    let tools = vec![
        (
            "git.commit",
            "Commit changes to repository",
            r#"{"skill_name": "git", "tool_name": "commit", "type": "command", "command": "git.commit", "file_path": "git/commit.py", "keywords": ["git", "commit", "vcs"], "input_schema": {}}"#,
            vec![0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "git.status",
            "Show working tree status",
            r#"{"skill_name": "git", "tool_name": "status", "type": "command", "command": "git.status", "file_path": "git/status.py", "keywords": ["git", "status", "vcs"], "input_schema": {}}"#,
            vec![0.8, 0.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "git.branch",
            "Create or list branches",
            r#"{"skill_name": "git", "tool_name": "branch", "type": "command", "command": "git.branch", "file_path": "git/branch.py", "keywords": ["git", "branch", "vcs"], "input_schema": {}}"#,
            vec![0.7, 0.3, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "python.run",
            "Run Python code",
            r#"{"skill_name": "python", "tool_name": "run", "type": "command", "command": "python.run", "file_path": "python/run.py", "keywords": ["python", "run"], "input_schema": {}}"#,
            vec![0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
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

    // Index keywords
    let kw_docs: Vec<(String, String, String, Vec<String>, Vec<String>)> = vec![
        (
            "git.commit".to_string(),
            "Commit changes to repository".to_string(),
            "git".to_string(),
            vec!["git".to_string(), "commit".to_string()],
            vec![],
        ),
        (
            "git.status".to_string(),
            "Show working tree status".to_string(),
            "git".to_string(),
            vec!["git".to_string(), "status".to_string()],
            vec![],
        ),
        (
            "git.branch".to_string(),
            "Create or list branches".to_string(),
            "git".to_string(),
            vec!["git".to_string(), "branch".to_string()],
            vec![],
        ),
        (
            "python.run".to_string(),
            "Run Python code".to_string(),
            "python".to_string(),
            vec!["python".to_string(), "run".to_string()],
            vec![],
        ),
    ];
    store.bulk_index_keywords(kw_docs).unwrap();

    // Search with keyword text - should use Weighted RRF
    let query = vec![0.85, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
    let results = store
        .search_tools("tools", &query, Some("commit"), 10, 0.0)
        .await
        .unwrap();

    assert!(!results.is_empty());
    // git.commit should rank first due to field boosting (token "commit" matches)
    assert_eq!(results[0].name, "git.commit");
}

#[tokio::test]
async fn test_search_tools_field_boosting() {
    // Test that Field Boosting (exact phrase + token match) works
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("field_boost_test");
    clean_test_db(&db_path);

    let store = VectorStore::new_with_keyword_index(
        temp_dir.path().join("field_boost_test").to_str().unwrap(),
        Some(10),
        true,
    )
    .await
    .unwrap();

    let tools = vec![
        (
            "git.commit",
            "Commit changes to repository",
            r#"{"skill_name": "git", "tool_name": "commit", "type": "command", "command": "git.commit", "file_path": "git/commit.py", "keywords": ["git", "commit"], "input_schema": {}}"#,
            vec![0.5; 10],
        ),
        (
            "git.status",
            "Show git status",
            r#"{"skill_name": "git", "tool_name": "status", "type": "command", "command": "git.status", "file_path": "git/status.py", "keywords": ["git", "status"], "input_schema": {}}"#,
            vec![0.5; 10],
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

    // Index keywords
    let kw_docs: Vec<(String, String, String, Vec<String>, Vec<String>)> = vec![
        (
            "git.commit".to_string(),
            "Commit changes to repository".to_string(),
            "git".to_string(),
            vec!["git".to_string(), "commit".to_string()],
            vec![],
        ),
        (
            "git.status".to_string(),
            "Show git status".to_string(),
            "git".to_string(),
            vec!["git".to_string(), "status".to_string()],
            vec![],
        ),
    ];
    store.bulk_index_keywords(kw_docs).unwrap();

    // Query "git commit" - should boost git.commit significantly
    // due to matching both tokens "git" and "commit"
    let query = vec![0.5; 10];
    let results = store
        .search_tools("tools", &query, Some("git commit"), 10, 0.0)
        .await
        .unwrap();

    // Should find at least our 2 indexed tools (may find more if keyword index had prior data)
    assert!(
        results.len() >= 2,
        "Expected at least 2 results, got {}",
        results.len()
    );
    // git.commit should have higher score due to field boosting
    // (matches "git" AND "commit" in tool name)
    assert_eq!(results[0].name, "git.commit");
    // git.commit should score higher than git.status due to extra token match
    assert!(
        results[0].score > results[1].score,
        "Field boosting should give git.commit higher score"
    );
}

#[tokio::test]
async fn test_search_tools_keyword_rescue() {
    // Test that tools not found by vector search can be rescued by keyword
    let temp_dir = tempfile::tempdir().unwrap();
    let db_path = temp_dir.path().join("rescue_test");
    clean_test_db(&db_path);

    let store = VectorStore::new_with_keyword_index(
        temp_dir.path().join("rescue_test").to_str().unwrap(),
        Some(10),
        true,
    )
    .await
    .unwrap();

    // Add tools with very different embeddings
    let tools = vec![
        (
            "git.commit",
            "Commit changes",
            r#"{"skill_name": "git", "tool_name": "commit", "type": "command", "command": "git.commit", "file_path": "git/commit.py", "keywords": ["git", "commit"], "input_schema": {}}"#,
            vec![1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ),
        (
            "filesystem.read",
            "Read file contents",
            r#"{"skill_name": "filesystem", "tool_name": "read", "type": "command", "command": "filesystem.read", "file_path": "fs/read.py", "keywords": ["file", "read"], "input_schema": {}}"#,
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

    // Index keywords
    let kw_docs: Vec<(String, String, String, Vec<String>, Vec<String>)> = vec![
        (
            "git.commit".to_string(),
            "Commit changes".to_string(),
            "git".to_string(),
            vec!["git".to_string(), "commit".to_string()],
            vec![],
        ),
        (
            "filesystem.read".to_string(),
            "Read file contents".to_string(),
            "filesystem".to_string(),
            vec!["file".to_string(), "read".to_string()],
            vec![],
        ),
    ];
    store.bulk_index_keywords(kw_docs).unwrap();

    // Query with "git commit" but vector similar to filesystem
    let query = vec![0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0];
    let results = store
        .search_tools("tools", &query, Some("git commit"), 10, 0.0)
        .await
        .unwrap();

    // git.commit should be rescued by keyword search
    assert!(results.iter().any(|r| r.name == "git.commit"));
}
