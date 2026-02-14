//! Integration tests for hybrid search (vector + keyword).

use omni_vector::VectorStore;

/// Setup a vector store with keyword index enabled for testing.
async fn setup_store(path: &std::path::Path, dim: usize) -> VectorStore {
    VectorStore::new_with_keyword_index(path.to_str().unwrap(), Some(dim), true, None, None)
        .await
        .unwrap()
}

#[tokio::test]
async fn test_hybrid_search_without_keyword_index_falls_back_to_vector() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = VectorStore::new(temp_dir.path().to_str().unwrap(), None)
        .await
        .unwrap();

    // Add documents first so the table exists
    store
        .add_documents(
            "test",
            vec!["doc1".to_string()],
            vec![vec![0.1; 1024]],
            vec!["test content".to_string()],
            vec![r#"{"category": "test"}"#.to_string()],
        )
        .await
        .unwrap();

    // Without keyword backend enabled, hybrid search should degrade gracefully.
    let result = store
        .hybrid_search("test", "test query", vec![0.1; 1024], 10)
        .await;

    assert!(result.is_ok());
    assert!(!result.unwrap().is_empty());
}

#[tokio::test]
async fn test_hybrid_search_with_enabled_index() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 1024).await;

    // Add some test documents
    store
        .add_documents(
            "test",
            vec!["git_commit".to_string(), "git_status".to_string()],
            vec![vec![0.1; 1024], vec![0.2; 1024]],
            vec![
                "Commit changes to repository".to_string(),
                "Show working tree status".to_string(),
            ],
            vec![
                r#"{"category": "git", "keywords": ["commit", "save"]}"#.to_string(),
                r#"{"category": "git", "keywords": ["status", "dirty"]}"#.to_string(),
            ],
        )
        .await
        .unwrap();

    // Index keywords
    let docs: Vec<(String, String, String, Vec<String>, Vec<String>)> = vec![
        (
            "git_commit".to_string(),
            "Commit changes to repository".to_string(),
            "git".to_string(),
            vec!["commit".to_string(), "save".to_string()],
            vec![],
        ),
        (
            "git_status".to_string(),
            "Show working tree status".to_string(),
            "git".to_string(),
            vec!["status".to_string(), "dirty".to_string()],
            vec![],
        ),
    ];
    store.bulk_index_keywords(docs).unwrap();

    // Perform hybrid search
    let results = store
        .hybrid_search("test", "commit", vec![0.1; 1024], 10)
        .await
        .unwrap();

    assert!(!results.is_empty());
    // git_commit should rank higher for "commit" query
    assert_eq!(results[0].tool_name, "git_commit");
}

#[tokio::test]
async fn test_hybrid_search_field_boosting_name_vs_desc() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 10).await;

    // "search" is in the name of tool1, but only in the description of tool2
    store
        .add_documents(
            "boost_test",
            vec!["search_files".to_string(), "file_scanner".to_string()],
            vec![vec![0.0; 10], vec![0.0; 10]],
            vec![
                "Scan directory".to_string(),
                "Search for files in a path".to_string(),
            ],
            vec![r#"{}"#.to_string(), r#"{}"#.to_string()],
        )
        .await
        .unwrap();

    store
        .bulk_index_keywords(vec![
            (
                "search_files".to_string(),
                "Scan directory".to_string(),
                "fs".to_string(),
                vec![],
                vec![],
            ),
            (
                "file_scanner".to_string(),
                "Search for files in a path".to_string(),
                "fs".to_string(),
                vec![],
                vec![],
            ),
        ])
        .unwrap();

    let results = store
        .hybrid_search("boost_test", "search", vec![0.0; 10], 10)
        .await
        .unwrap();

    assert!(!results.is_empty());
    // Tool name match should boost search_files to the top even if file_scanner has "search" in description
    assert_eq!(
        results[0].tool_name, "search_files",
        "Tool name match should outrank description match"
    );
}

#[tokio::test]
async fn test_hybrid_search_intent_match() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 10).await;

    store
        .add_documents(
            "intent_test",
            vec!["writer.polish".to_string()],
            vec![vec![0.0; 10]],
            vec!["Improve text quality".to_string()],
            vec![r#"{}"#.to_string()],
        )
        .await
        .unwrap();

    store
        .bulk_index_keywords(vec![(
            "writer.polish".to_string(),
            "Improve text quality".to_string(),
            "writer".to_string(),
            vec![],
            vec!["refactor documentation".to_string()],
        )])
        .unwrap();

    let results = store
        .hybrid_search("intent_test", "refactor documentation", vec![0.0; 10], 10)
        .await
        .unwrap();

    assert!(!results.is_empty());
    assert_eq!(results[0].tool_name, "writer.polish");
}

#[tokio::test]
async fn test_hybrid_search_empty_engines() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 10).await;

    // Create table by adding an unrelated doc
    store
        .add_documents(
            "empty_test",
            vec!["unrelated".to_string()],
            vec![vec![1.0; 10]],
            vec!["content".to_string()],
            vec![r#"{}"#.to_string()],
        )
        .await
        .unwrap();
    store
        .bulk_index_keywords(vec![(
            "unrelated".to_string(),
            "content".to_string(),
            "cat".to_string(),
            vec![],
            vec![],
        )])
        .unwrap();

    // Search for something that won't match either engine
    // Vector search for zeros against a vec of ones will have huge distance
    // Keyword search for "xyz" will return nothing
    let results = store
        .hybrid_search("empty_test", "xyz", vec![0.0; 10], 10)
        .await
        .unwrap();

    // It might still return 'unrelated' via vector if it's the only doc, but distance will be high.
    // Let's assert limit is respected at least.
    assert!(results.len() <= 10);
}

#[tokio::test]
async fn test_hybrid_search_limit() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 10).await;

    let mut ids = Vec::new();
    let mut vectors = Vec::new();
    let mut contents = Vec::new();
    let mut metadatas = Vec::new();
    let mut kw_docs = Vec::new();

    for i in 0..20 {
        let name = format!("tool_{}", i);
        ids.push(name.clone());
        vectors.push(vec![0.1 * i as f32; 10]);
        contents.push(format!("Description for tool {}", i));
        metadatas.push(r#"{}"#.to_string());
        kw_docs.push((
            name,
            format!("Description for tool {}", i),
            "test".to_string(),
            vec![],
            vec![],
        ));
    }

    store
        .add_documents("limit_test", ids, vectors, contents, metadatas)
        .await
        .unwrap();
    store.bulk_index_keywords(kw_docs).unwrap();

    let limit = 5;
    let results = store
        .hybrid_search("limit_test", "tool", vec![0.0; 10], limit)
        .await
        .unwrap();

    assert_eq!(results.len(), limit, "Should respect limit parameter");
}

#[tokio::test]
async fn test_hybrid_search_semantic_rescue() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 10).await;

    // Tool 1: Matches keyword "commit" exactly
    // Tool 2: Semantic match for "save changes" but keyword index doesn't have "commit"
    store
        .add_documents(
            "rescue_test",
            vec!["vcs.commit".to_string(), "vcs.persist".to_string()],
            vec![vec![0.0; 10], vec![0.9; 10]], // tool 2 is closer to query_vector [1.0; 10]
            vec![
                "Execute commit".to_string(),
                "Save all changes to disk".to_string(),
            ],
            vec![r#"{}"#.to_string(), r#"{}"#.to_string()],
        )
        .await
        .unwrap();

    store
        .bulk_index_keywords(vec![
            (
                "vcs.commit".to_string(),
                "Execute commit".to_string(),
                "vcs".to_string(),
                vec!["commit".to_string()],
                vec![],
            ),
            (
                "vcs.persist".to_string(),
                "Save all changes to disk".to_string(),
                "vcs".to_string(),
                vec!["persist".to_string()],
                vec![],
            ),
        ])
        .unwrap();

    // Query has keyword "commit" but vector is closer to "persist"
    let query_vector = vec![1.0; 10];
    let results = store
        .hybrid_search("rescue_test", "commit", query_vector, 10)
        .await
        .unwrap();

    assert!(results.len() >= 2);
    // vcs.commit should rank highly due to keyword match
    // vcs.persist should also be present due to semantic match
    let tool_names: Vec<_> = results.iter().map(|r| &r.tool_name).collect();
    assert!(tool_names.contains(&&"vcs.commit".to_string()));
    assert!(tool_names.contains(&&"vcs.persist".to_string()));
}

#[tokio::test]
async fn test_enable_keyword_index_on_existing_store() {
    let temp_dir = tempfile::tempdir().unwrap();
    let mut store = VectorStore::new(temp_dir.path().to_str().unwrap(), None)
        .await
        .unwrap();

    // Enable keyword index
    store.enable_keyword_index().unwrap();

    // Verify it's enabled
    store
        .index_keyword(
            "test_tool",
            "A test tool",
            "test",
            &["test".to_string(), "example".to_string()],
            &[],
        )
        .unwrap();
}

#[tokio::test]
async fn test_hybrid_search_fallback_on_keyword_error() {
    let temp_dir = tempfile::tempdir().unwrap();
    let store = setup_store(temp_dir.path(), 1024).await;

    // Add document
    store
        .add_documents(
            "test",
            vec!["git_commit".to_string()],
            vec![vec![0.1; 1024]],
            vec!["Commit changes".to_string()],
            vec![r#"{"category": "git"}"#.to_string()],
        )
        .await
        .unwrap();

    // Index keywords
    store
        .bulk_index_keywords(vec![(
            "git_commit".to_string(),
            "Commit changes".to_string(),
            "git".to_string(),
            vec!["commit".to_string()],
            vec![],
        )])
        .unwrap();

    // Search with code snippet (should fallback to vector-only gracefully if parser fails)
    let results = store
        .hybrid_search("test", "pub async fn add_documents", vec![0.1; 1024], 5)
        .await
        .unwrap();

    // Should still return results from vector search
    assert!(!results.is_empty());
}
