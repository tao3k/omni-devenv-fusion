//! Tests for search operations - keyword boosting and filtering.

use omni_types::VectorSearchResult;
use omni_vector::VectorStore;

#[tokio::test]
async fn test_apply_keyword_boost_metadata_match() {
    // Test that keyword matching works with metadata.keywords array
    // Use smaller distance difference (0.05) so keyword boost (0.03) can overcome it
    let mut results = vec![
        VectorSearchResult {
            id: "git.commit".to_string(),
            content: "Execute git.commit".to_string(),
            metadata: serde_json::json!({
                "keywords": ["git", "commit", "version"]
            }),
            distance: 0.35, // Slightly worse vector similarity
        },
        VectorSearchResult {
            id: "file.save".to_string(),
            content: "Save a file".to_string(),
            metadata: serde_json::json!({
                "keywords": ["file", "save", "write"]
            }),
            distance: 0.3, // Better vector similarity
        },
    ];

    VectorStore::apply_keyword_boost(&mut results, &["git".to_string()]);

    // git.commit: keyword_score = 0.1, keyword_bonus = 0.03
    // git.commit: 0.35 - 0.03 = 0.32
    // file.save: 0.3
    // git.commit should rank higher
    assert!(
        results[0].id == "git.commit",
        "git.commit should rank first with keyword boost"
    );
    assert!(
        results[0].distance < results[1].distance,
        "git.commit distance should be lower"
    );
}

#[tokio::test]
async fn test_apply_keyword_boost_no_keywords() {
    // Test that results unchanged when no keywords provided
    let mut results = vec![VectorSearchResult {
        id: "git.commit".to_string(),
        content: "Execute git.commit".to_string(),
        metadata: serde_json::json!({"keywords": ["git"]}),
        distance: 0.5,
    }];

    VectorStore::apply_keyword_boost(&mut results, &[]);

    assert_eq!(
        results[0].distance, 0.5,
        "Distance should not change with empty keywords"
    );
}

#[tokio::test]
async fn test_apply_keyword_boost_multiple_keywords() {
    // Test that multiple keyword matches accumulate
    let mut results = vec![
        VectorSearchResult {
            id: "git.commit".to_string(),
            content: "Execute git.commit".to_string(),
            metadata: serde_json::json!({
                "keywords": ["git", "commit", "version"]
            }),
            distance: 0.4,
        },
        VectorSearchResult {
            id: "file.save".to_string(),
            content: "Save a file".to_string(),
            metadata: serde_json::json!({
                "keywords": ["file", "save"]
            }),
            distance: 0.3,
        },
    ];

    // Query with multiple keywords
    VectorStore::apply_keyword_boost(&mut results, &["git".to_string(), "commit".to_string()]);

    // git.commit matches both keywords: keyword_score = 0.1 + 0.1 = 0.2, bonus = 0.06
    // git.commit: 0.4 - 0.06 = 0.34
    // file.save: 0.3
    // file.save still wins (0.3 < 0.34)
    assert!(
        results[0].distance < results[1].distance,
        "Results should be sorted by hybrid distance"
    );
}

#[tokio::test]
async fn test_apply_keyword_boost_empty_results() {
    // Test with empty results list
    let mut results: Vec<VectorSearchResult> = vec![];
    VectorStore::apply_keyword_boost(&mut results, &["git".to_string()]);
    assert!(results.is_empty());
}

// =========================================================================
// Tests for matches_filter function
// =========================================================================

#[test]
fn test_matches_filter_string_exact() {
    let metadata = serde_json::json!({"domain": "python"});
    let conditions = serde_json::json!({"domain": "python"});
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_string_mismatch() {
    let metadata = serde_json::json!({"domain": "python"});
    let conditions = serde_json::json!({"domain": "testing"});
    assert!(!VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_number() {
    let metadata = serde_json::json!({"count": 42});
    let conditions = serde_json::json!({"count": 42});
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_boolean() {
    let metadata = serde_json::json!({"enabled": true});
    let conditions = serde_json::json!({"enabled": true});
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_missing_key() {
    let metadata = serde_json::json!({"domain": "python"});
    let conditions = serde_json::json!({"missing_key": "value"});
    assert!(!VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_multiple_conditions_all_match() {
    let metadata = serde_json::json!({
        "domain": "python",
        "type": "function"
    });
    let conditions = serde_json::json!({
        "domain": "python",
        "type": "function"
    });
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_multiple_conditions_one_mismatch() {
    let metadata = serde_json::json!({
        "domain": "python",
        "type": "function"
    });
    let conditions = serde_json::json!({
        "domain": "python",
        "type": "class"
    });
    assert!(!VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_nested_key() {
    let metadata = serde_json::json!({
        "config": {
            "domain": "python"
        }
    });
    let conditions = serde_json::json!({
        "config.domain": "python"
    });
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_null_metadata() {
    let metadata = serde_json::Value::Null;
    let conditions = serde_json::json!({"domain": "python"});
    assert!(!VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_empty_conditions() {
    let metadata = serde_json::json!({"domain": "python"});
    let conditions = serde_json::json!({});
    // Empty conditions should match everything
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}

#[test]
fn test_matches_filter_non_object_conditions() {
    let metadata = serde_json::json!({"domain": "python"});
    let conditions = serde_json::json!("invalid");
    // Non-object conditions should match everything
    assert!(VectorStore::matches_filter(&metadata, &conditions));
}
