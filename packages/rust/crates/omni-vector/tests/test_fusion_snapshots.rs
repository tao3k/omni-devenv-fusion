//! Snapshot tests for fusion contract stability.
//!
//! These tests lock score ordering/shape for weighted and adaptive RRF outputs.
//! If behavior changes intentionally, update snapshots in a reviewable commit.

use insta::assert_json_snapshot;
use omni_vector::ToolSearchResult;
use omni_vector::keyword::{
    KEYWORD_WEIGHT, RRF_K, SEMANTIC_WEIGHT, apply_adaptive_rrf, apply_weighted_rrf,
};
use serde_json::json;

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
        routing_keywords: vec![],
        intents: vec![],
        category: "tool".to_string(),
        parameters: vec![],
    }
}

fn round6(v: f32) -> String {
    format!("{v:.6}")
}

#[test]
fn snapshot_weighted_rrf_contract_v1() {
    let vector_results = vec![
        ("git.commit".to_string(), 0.92),
        ("git.status".to_string(), 0.83),
        ("filesystem.read".to_string(), 0.55),
    ];
    let keyword_results = vec![
        make_tool_result("git.commit", 3.2),
        make_tool_result("git.status", 2.4),
        make_tool_result("git.diff", 1.1),
    ];

    let results = apply_weighted_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "git commit",
    );

    let view: Vec<_> = results
        .into_iter()
        .map(|r| {
            json!({
                "tool_name": r.tool_name,
                "rrf_score": round6(r.rrf_score),
                "vector_score": round6(r.vector_score),
                "keyword_score": round6(r.keyword_score),
            })
        })
        .collect();

    assert_json_snapshot!("weighted_rrf_contract_v1", view);
}

#[test]
fn snapshot_adaptive_rrf_contract_v1() {
    let vector_results = vec![
        ("git.commit".to_string(), 0.95),
        ("git.status".to_string(), 0.79),
        ("filesystem.read".to_string(), 0.51),
    ];
    let keyword_results = vec![
        make_tool_result("git.commit", 2.8),
        make_tool_result("git.status", 2.0),
    ];

    let results = apply_adaptive_rrf(
        vector_results,
        keyword_results,
        RRF_K,
        SEMANTIC_WEIGHT,
        KEYWORD_WEIGHT,
        "git commit",
    );

    let view: Vec<_> = results
        .into_iter()
        .map(|r| {
            json!({
                "tool_name": r.tool_name,
                "rrf_score": round6(r.rrf_score),
                "vector_score": round6(r.vector_score),
                "keyword_score": round6(r.keyword_score),
            })
        })
        .collect();

    assert_json_snapshot!("adaptive_rrf_contract_v1", view);
}
