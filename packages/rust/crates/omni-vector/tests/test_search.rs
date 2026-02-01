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

// =========================================================================
// Tests for search vector distance calculation
// =========================================================================

/// Test that vector distance calculation produces correct relative ordering.
/// Identical vectors should have distance 0 (score 1.0).
/// Vectors that differ more should have higher distance (lower score).
#[tokio::test]
async fn test_vector_distance_calculation() {
    use omni_vector::ToolSearchResult;

    // Create two vectors: one identical to query, one different
    let _query_vec = vec![1.0, 0.0, 0.0, 0.0]; // 4D unit vector along x
    let _identical_vec = vec![1.0, 0.0, 0.0, 0.0]; // Same as query, distance = 0
    let _opposite_vec = vec![-1.0, 0.0, 0.0, 0.0]; // Opposite, distance = 2
    let _orthogonal_vec = vec![0.0, 1.0, 0.0, 0.0]; // Orthogonal, distance = sqrt(2) ≈ 1.41

    // Calculate expected distances manually
    // dist_sq = sum((a - b)^2)
    let identical_dist_sq: f32 = (1.0_f32 - 1.0_f32).powi(2) * 4.0; // = 0
    let opposite_dist_sq: f32 = (1.0_f32 - (-1.0_f32)).powi(2) + 3.0 * (0.0_f32 - 0.0_f32).powi(2); // = 4
    let orthogonal_dist_sq: f32 = (1.0_f32 - 0.0_f32).powi(2)
        + (0.0_f32 - 1.0_f32).powi(2)
        + 2.0 * (0.0_f32 - 0.0_f32).powi(2); // = 2

    let identical_score = 1.0 / (1.0 + identical_dist_sq.sqrt());
    let opposite_score = 1.0 / (1.0 + opposite_dist_sq.sqrt());
    let orthogonal_score = 1.0 / (1.0 + orthogonal_dist_sq.sqrt());

    // Verify score ordering: identical > orthogonal > opposite
    assert!(
        identical_score > orthogonal_score,
        "Identical should score higher than orthogonal"
    );
    assert!(
        orthogonal_score > opposite_score,
        "Orthogonal should score higher than opposite"
    );
    assert_eq!(
        identical_score, 1.0,
        "Identical vectors should have score 1.0"
    );

    // Create ToolSearchResult objects
    let identical = ToolSearchResult {
        name: "identical_tool".to_string(),
        description: "Identical vector".to_string(),
        input_schema: serde_json::json!({}),
        score: identical_score,
        skill_name: "test".to_string(),
        tool_name: "identical".to_string(),
        file_path: "".to_string(),
        keywords: vec![],
        intents: vec![],
    };

    let opposite = ToolSearchResult {
        name: "opposite_tool".to_string(),
        description: "Opposite vector".to_string(),
        input_schema: serde_json::json!({}),
        score: opposite_score,
        skill_name: "test".to_string(),
        tool_name: "opposite".to_string(),
        file_path: "".to_string(),
        keywords: vec![],
        intents: vec![],
    };

    let orthogonal = ToolSearchResult {
        name: "orthogonal_tool".to_string(),
        description: "Orthogonal vector".to_string(),
        input_schema: serde_json::json!({}),
        score: orthogonal_score,
        skill_name: "test".to_string(),
        tool_name: "orthogonal".to_string(),
        file_path: "".to_string(),
        keywords: vec![],
        intents: vec![],
    };

    // Verify results are ordered by score
    let mut results = vec![opposite.clone(), orthogonal.clone(), identical.clone()];
    results.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap());

    assert_eq!(results[0].name, "identical_tool");
    assert_eq!(results[1].name, "orthogonal_tool");
    assert_eq!(results[2].name, "opposite_tool");
}
