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
            ),
            (
                "filesystem_read".to_string(),
                "Read file contents".to_string(),
                "filesystem".to_string(),
                vec!["read".to_string(), "file".to_string(), "cat".to_string()],
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
            ),
            (
                "git_status".to_string(),
                "Show working tree status".to_string(),
                "git".to_string(),
                vec!["status".to_string()],
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
