//! Basic Reciprocal Rank Fusion.

use std::collections::HashMap;

use crate::ToolSearchResult;

use super::types::HybridSearchResult;

/// Apply Reciprocal Rank Fusion to combine vector and keyword results.
#[must_use]
pub fn apply_rrf(
    vector_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    k: f32,
) -> Vec<HybridSearchResult> {
    let mut fusion_map: HashMap<String, HybridSearchResult> = HashMap::new();

    for (rank, (name, score)) in vector_results.into_iter().enumerate() {
        let rrf_score = super::kernels::rrf_term(k, rank);
        fusion_map.insert(
            name.clone(),
            HybridSearchResult {
                tool_name: name,
                rrf_score,
                vector_score: score,
                keyword_score: 0.0,
            },
        );
    }

    for (rank, result) in keyword_results.into_iter().enumerate() {
        let rrf_score = super::kernels::rrf_term(k, rank);
        let tool_name = result.tool_name.clone();

        if let Some(entry) = fusion_map.get_mut(&tool_name) {
            entry.rrf_score += rrf_score;
            entry.keyword_score = result.score;
        } else {
            fusion_map.insert(
                tool_name.clone(),
                HybridSearchResult {
                    tool_name,
                    rrf_score,
                    vector_score: 0.0,
                    keyword_score: result.score,
                },
            );
        }
    }

    let mut results: Vec<_> = fusion_map.into_values().collect();
    results.sort_by(|a, b| {
        b.rrf_score
            .total_cmp(&a.rrf_score)
            .then_with(|| a.tool_name.cmp(&b.tool_name))
    });
    results
}
