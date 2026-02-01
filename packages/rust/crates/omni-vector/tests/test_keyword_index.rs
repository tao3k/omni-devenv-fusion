//! Tests for the keyword module (BM25 keyword search)

use omni_vector::keyword::{KEYWORD_WEIGHT, KeywordIndex, RRF_K, SEMANTIC_WEIGHT};
use tempfile::TempDir;

#[tokio::test]
async fn test_keyword_index_creation() {
    let temp_dir = TempDir::new().unwrap();
    let index = KeywordIndex::new(temp_dir.path()).unwrap();

    assert_eq!(index.count_documents().unwrap(), 0);
}

#[tokio::test]
async fn test_keyword_index_bulk_upsert() {
    let temp_dir = TempDir::new().unwrap();
    let index = KeywordIndex::new(temp_dir.path()).unwrap();

    // Add test documents
    index
        .bulk_upsert(vec![
            (
                "git_commit".to_string(),
                "Commit changes to repository".to_string(),
                "git".to_string(),
                vec!["commit".to_string(), "save".to_string(), "push".to_string()],
                vec![],
            ),
            (
                "git_status".to_string(),
                "Show working tree status".to_string(),
                "git".to_string(),
                vec![
                    "status".to_string(),
                    "dirty".to_string(),
                    "clean".to_string(),
                ],
                vec![],
            ),
            (
                "filesystem_read".to_string(),
                "Read file contents".to_string(),
                "filesystem".to_string(),
                vec!["read".to_string(), "file".to_string(), "cat".to_string()],
                vec![],
            ),
        ])
        .unwrap();

    assert_eq!(index.count_documents().unwrap(), 3);
}

#[tokio::test]
async fn test_keyword_index_search() {
    let temp_dir = TempDir::new().unwrap();
    let index = KeywordIndex::new(temp_dir.path()).unwrap();

    // Add test documents
    index
        .bulk_upsert(vec![
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
                vec!["status".to_string()],
                vec![],
            ),
        ])
        .unwrap();

    // Search for "commit"
    let results = index.search("commit", 10).unwrap();
    assert!(!results.is_empty());
    assert_eq!(results[0].tool_name, "git_commit");
    assert!(results[0].score > 0.0);
}

#[tokio::test]
async fn test_keyword_index_constants() {
    // Verify RRF constants are properly exported
    assert_eq!(RRF_K, 10.0);
    assert_eq!(SEMANTIC_WEIGHT, 1.0);
    assert_eq!(KEYWORD_WEIGHT, 1.5);
}

/// Test that KeywordIndex properly handles open-existing workflow with intents
#[tokio::test]
async fn test_keyword_index_with_intents() {
    let temp_dir = TempDir::new().unwrap();

    // First creation
    let index1 = KeywordIndex::new(temp_dir.path()).unwrap();
    index1
        .bulk_upsert(vec![(
            "test_tool".to_string(),
            "Test tool description".to_string(),
            "test".to_string(),
            vec!["test".to_string()],
            vec!["intent1".to_string(), "intent2".to_string()],
        )])
        .unwrap();
    assert_eq!(index1.count_documents().unwrap(), 1);

    // Second open (should reuse existing with full schema)
    let index2 = KeywordIndex::new(temp_dir.path()).unwrap();
    assert_eq!(index2.count_documents().unwrap(), 1);

    // Verify search works
    let results = index2.search("test", 10).unwrap();
    assert!(!results.is_empty());
    assert_eq!(results[0].tool_name, "test_tool");
}

/// Test that KeywordIndex properly handles a complete open-existing workflow
#[tokio::test]
async fn test_keyword_index_open_existing() {
    let temp_dir = TempDir::new().unwrap();

    // First creation
    let index1 = KeywordIndex::new(temp_dir.path()).unwrap();
    index1
        .bulk_upsert(vec![(
            "existing_tool".to_string(),
            "Existing tool".to_string(),
            "test".to_string(),
            vec!["existing".to_string()],
            vec!["intent1".to_string(), "intent2".to_string()],
        )])
        .unwrap();
    assert_eq!(index1.count_documents().unwrap(), 1);

    // Second open (should reuse existing)
    let index2 = KeywordIndex::new(temp_dir.path()).unwrap();
    assert_eq!(index2.count_documents().unwrap(), 1);

    // Verify we can search in the re-opened index
    let results = index2.search("existing", 10).unwrap();
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].tool_name, "existing_tool");
}

/// Test that KeywordIndex can be recreated after deletion
#[tokio::test]
async fn test_keyword_index_recreate() {
    let temp_dir = TempDir::new().unwrap();

    // Create initial index with data
    let index1 = KeywordIndex::new(temp_dir.path()).unwrap();
    index1
        .bulk_upsert(vec![(
            "original_tool".to_string(),
            "Original tool".to_string(),
            "test".to_string(),
            vec!["original".to_string()],
            vec![],
        )])
        .unwrap();
    assert_eq!(index1.count_documents().unwrap(), 1);

    // Delete the keyword index directory
    let index_path = temp_dir.path().join("keyword_index");
    std::fs::remove_dir_all(&index_path).unwrap();
    assert!(!index_path.exists());

    // Reopening should recreate the index
    let index2 = KeywordIndex::new(temp_dir.path()).unwrap();
    assert_eq!(index2.count_documents().unwrap(), 0);

    // And should still be functional
    index2
        .bulk_upsert(vec![(
            "new_tool".to_string(),
            "New tool".to_string(),
            "test".to_string(),
            vec!["new".to_string()],
            vec!["new_intent".to_string()],
        )])
        .unwrap();

    assert_eq!(index2.count_documents().unwrap(), 1);
}
