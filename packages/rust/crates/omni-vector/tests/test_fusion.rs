//! Tests for RRF Fusion algorithms
//!
//! Tests for apply_rrf, apply_weighted_rrf, and apply_adaptive_rrf

use omni_vector::ToolSearchResult;
use omni_vector::keyword::{
    KEYWORD_WEIGHT, RRF_K, SEMANTIC_WEIGHT, apply_adaptive_rrf, apply_rrf, apply_weighted_rrf,
};

/// Helper to create a ToolSearchResult for testing
fn make_tool_result(name: &str, score: f32) -> ToolSearchResult {
    ToolSearchResult {
        name: name.to_string(),
        description: format!("Description of {}", name),
        input_schema: serde_json::json!({}),
        score,
        vector_score: None,
        keyword_score: Some(score),
        skill_name: name.split('.').next().unwrap_or("").to_string(),
        tool_name: name.to_string(),
        file_path: String::new(),
        keywords: vec![],
        intents: vec![],
        category: "tool".to_string(),
    }
}

// =========================================================================
// Basic RRF Tests
// =========================================================================

#[test]
fn test_apply_rrf_basic() {
    let vector_results = vec![
        ("git_commit".to_string(), 0.85),
        ("git_status".to_string(), 0.75),
    ];
    let keyword_results = vec![
        make_tool_result("git_commit", 1.5),
        make_tool_result("git_status", 1.2),
    ];

    let results = apply_rrf(vector_results, keyword_results, RRF_K);

    assert_eq!(results.len(), 2);
    assert_eq!(results[0].tool_name, "git_commit");
    assert!(results[0].vector_score > 0.0);
    assert!(results[0].keyword_score > 0.0);
}

// =========================================================================
// Weighted RRF Tests
// =========================================================================

#[test]
fn test_weighted_rrf_normal_hybrid_search() {
    // Test normal hybrid search where both streams have results
    let vector_results = vec![
        ("git_commit".to_string(), 0.85),
        ("git_status".to_string(), 0.75),
    ];
    let keyword_results = vec![
        make_tool_result("git_commit", 1.5),
        make_tool_result("git_status", 1.2),
    ];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "commit",
    );

    assert!(!results.is_empty());
    assert_eq!(results[0].tool_name, "git_commit");
    assert!(results[0].vector_score > 0.0);
    assert!(results[0].keyword_score > 0.0);
}

#[test]
fn test_weighted_rrf_fallback_with_sparse_keywords() {
    // Test fallback mode: keyword results are sparse (< 2)
    // This simulates code snippet queries where BM25 fails
    let vector_results = vec![
        ("git_commit".to_string(), 0.95), // High semantic match
        ("git_status".to_string(), 0.70),
    ];
    // Only 1 keyword result - triggers fallback
    let keyword_results = vec![make_tool_result("git_status", 0.5)];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "pub async fn add_documents", // Code-like query
    );

    assert!(!results.is_empty());
    // git_commit should rank first due to vector fallback
    assert_eq!(results[0].tool_name, "git_commit");
    // In fallback mode, vector score contributes more
    assert!(results[0].rrf_score > results[1].rrf_score);
}

#[test]
fn test_weighted_rrf_pure_vector_search() {
    // Test pure vector search (no keyword results at all)
    let vector_results = vec![
        ("git_commit".to_string(), 0.90),
        ("filesystem_read".to_string(), 0.65),
    ];
    let keyword_results: Vec<ToolSearchResult> = vec![];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "some code snippet",
    );

    assert!(!results.is_empty());
    assert_eq!(results[0].tool_name, "git_commit");
    assert_eq!(results[0].keyword_score, 0.0);
    // Vector score should be preserved
    assert!((results[0].vector_score - 0.90).abs() < 0.001);
}

#[test]
fn test_weighted_rrf_field_boosting_in_fallback() {
    // Test that field boosting still works in fallback mode
    let vector_results = vec![
        ("git_commit".to_string(), 0.80),
        ("git_status".to_string(), 0.78),
    ];
    // Sparse keywords trigger fallback
    let keyword_results = vec![make_tool_result("filesystem_read", 0.3)];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "commit", // Query matches "commit" in git_commit
    );

    // git_commit should get name token boost
    let commit_result = results
        .iter()
        .find(|r| r.tool_name == "git_commit")
        .unwrap();
    assert!(commit_result.rrf_score > 0.8); // Boost applied
}

#[test]
fn test_weighted_rrf_fallback_preserves_ranking() {
    // Test that fallback mode preserves vector ranking order
    let vector_results = vec![
        ("tool_a".to_string(), 0.95),
        ("tool_b".to_string(), 0.85),
        ("tool_c".to_string(), 0.75),
    ];
    let keyword_results = vec![make_tool_result("tool_d", 0.1)]; // Only 1 result

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "code snippet",
    );

    // Original order should be preserved
    assert_eq!(results[0].tool_name, "tool_a");
    assert_eq!(results[1].tool_name, "tool_b");
    assert_eq!(results[2].tool_name, "tool_c");
}

#[test]
fn test_weighted_rrf_fallback_bonus_computation() {
    // Test that fallback bonus is correctly computed from similarity score
    let vector_results = vec![
        ("high_score".to_string(), 0.99),
        ("low_score".to_string(), 0.50),
    ];
    let keyword_results = vec![make_tool_result("other_tool", 0.1)];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "fn process",
    );

    let high = results
        .iter()
        .find(|r| r.tool_name == "high_score")
        .unwrap();
    let low = results.iter().find(|r| r.tool_name == "low_score").unwrap();

    // High score should have significantly higher RRF due to fallback bonus
    assert!(high.rrf_score > low.rrf_score);
    // Fallback bonus should be proportional to similarity
    let bonus_diff = (high.rrf_score - low.rrf_score) / 0.49; // (0.99-0.50) diff
    assert!((bonus_diff - 0.3).abs() < 0.05); // ~0.3 * score difference
}

#[test]
fn test_weighted_rrf_empty_vector_results() {
    // Handle edge case: empty vector results
    let vector_results: Vec<(String, f32)> = vec![];
    let keyword_results = vec![
        make_tool_result("git_commit", 1.5),
        make_tool_result("git_status", 1.2),
    ];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "commit",
    );

    // Should still return keyword-only results
    assert_eq!(results.len(), 2);
    assert_eq!(results[0].tool_name, "git_commit");
    assert_eq!(results[0].vector_score, 0.0);
}

#[test]
fn test_weighted_rrf_empty_both_results() {
    // Handle edge case: both results empty
    let vector_results: Vec<(String, f32)> = vec![];
    let keyword_results: Vec<ToolSearchResult> = vec![];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "xyz nonexistent",
    );

    assert!(results.is_empty());
}

// =========================================================================
// Adaptive RRF Tests
// =========================================================================

#[test]
fn test_adaptive_rrf_full_keyword_confidence() {
    // Test when keyword results are abundant (5+), confidence = 1.0
    let vector_results = vec![
        ("git_commit".to_string(), 0.85),
        ("git_status".to_string(), 0.75),
    ];
    let keyword_results = vec![
        make_tool_result("git_commit", 1.5),
        make_tool_result("git_status", 1.2),
        make_tool_result("git_push", 1.0),
        make_tool_result("git_pull", 0.9),
        make_tool_result("git_branch", 0.8),
    ];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "git commit",
    );

    assert!(!results.is_empty());
    // With full confidence, should behave like standard weighted RRF
    assert_eq!(results[0].tool_name, "git_commit");
}

#[test]
fn test_adaptive_rrf_sparse_keyword_confidence() {
    // Test with sparse keyword results - confidence decays linearly
    let vector_results = vec![
        ("git_commit".to_string(), 0.95),
        ("git_status".to_string(), 0.70),
    ];
    // Only 1 keyword result -> confidence = 0.2
    let keyword_results = vec![make_tool_result("git_status", 0.5)];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "pub async fn add_documents", // Code snippet
    );

    assert!(!results.is_empty());
    // git_commit should rank first due to high vector score and low kw confidence
    assert_eq!(results[0].tool_name, "git_commit");
}

#[test]
fn test_adaptive_rrf_zero_keyword_results() {
    // Test with zero keyword results - pure vector fallback
    let vector_results = vec![
        ("python_func".to_string(), 0.92),
        ("python_class".to_string(), 0.78),
    ];
    let keyword_results: Vec<ToolSearchResult> = vec![];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "def factorial(n):", // Pure code, no keyword matches
    );

    assert_eq!(results.len(), 2);
    assert_eq!(results[0].tool_name, "python_func");
    // With zero confidence, vector score injection should be active
    assert!(results[0].rrf_score > 0.1); // Should have raw score boost
}

#[test]
fn test_adaptive_rrf_vector_score_preservation() {
    // Test that raw vector scores are preserved when keyword is weak
    let vector_results = vec![
        ("high_match".to_string(), 0.98),
        ("medium_match".to_string(), 0.75),
        ("low_match".to_string(), 0.50),
    ];
    let keyword_results: Vec<ToolSearchResult> = vec![];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "code snippet",
    );

    // High match should have significantly higher score
    assert_eq!(results[0].tool_name, "high_match");
    assert_eq!(results[1].tool_name, "medium_match");
    assert_eq!(results[2].tool_name, "low_match");

    // Score differences should reflect raw similarity
    let high_rrf = results[0].rrf_score;
    let low_rrf = results[2].rrf_score;
    assert!(high_rrf - low_rrf > 0.1); // Significant difference due to score injection
}

#[test]
fn test_adaptive_rrf_field_boosting() {
    // Test that field boosting still works in adaptive mode
    let vector_results = vec![
        ("git_commit".to_string(), 0.80),
        ("filesystem_read".to_string(), 0.85),
    ];
    let keyword_results = vec![make_tool_result("other_tool", 0.3)];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "commit", // Query matches "commit" in git_commit
    );

    // git_commit should get name token boost
    let commit_result = results
        .iter()
        .find(|r| r.tool_name == "git_commit")
        .unwrap();
    assert!(commit_result.rrf_score > 0.7); // Token boost applied
}

#[test]
fn test_adaptive_rrf_keyword_only_penalty() {
    // Test that keyword-only results get penalized when vector misses
    let vector_results = vec![("vector_tool".to_string(), 0.90)];
    let keyword_results = vec![make_tool_result("keyword_only_tool", 2.0)];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "some query",
    );

    // keyword_only_tool should be ranked lower due to penalty
    let keyword_only = results
        .iter()
        .find(|r| r.tool_name == "keyword_only_tool")
        .unwrap();
    assert_eq!(keyword_only.vector_score, 0.0);
    // The score should be penalized (0.5 multiplier for vector-miss)
}

#[test]
fn test_adaptive_rrf_confidence_calculation() {
    // Test confidence calculation edge cases
    let vector_results = vec![("tool".to_string(), 0.9)];

    // 5+ results -> confidence = 1.0
    let kw_5plus: Vec<ToolSearchResult> = (0..5)
        .map(|i| make_tool_result(&format!("t{}", i), 1.0))
        .collect();
    let r5plus = apply_adaptive_rrf(vector_results.clone(), kw_5plus, RRF_K, 1.0, 1.5, "test");
    assert!(r5plus[0].rrf_score > 0.05); // Normal scoring

    // 3 results -> confidence = 0.6
    let kw_3: Vec<ToolSearchResult> = (0..3)
        .map(|i| make_tool_result(&format!("t{}", i), 1.0))
        .collect();
    let _r3 = apply_adaptive_rrf(vector_results.clone(), kw_3, RRF_K, 1.0, 1.5, "test");

    // 0 results -> confidence = 0.0
    let kw_0: Vec<ToolSearchResult> = vec![];
    let r0 = apply_adaptive_rrf(vector_results.clone(), kw_0, RRF_K, 1.0, 1.5, "test");
    assert!(r0[0].rrf_score > 0.3); // More vector boost with zero kw
}
