//! RRF Fusion - Reciprocal Rank Fusion algorithms for hybrid search

use crate::ToolSearchResult;

/// Result type for hybrid search combining vector and keyword scores
#[derive(Debug, Clone)]
pub struct HybridSearchResult {
    /// Full tool name (e.g., "git.commit")
    pub tool_name: String,
    /// Final combined RRF score after fusion
    pub rrf_score: f32,
    /// Raw vector similarity score from semantic search
    pub vector_score: f32,
    /// BM25 keyword score from keyword search
    pub keyword_score: f32,
}

/// Apply Reciprocal Rank Fusion to combine vector and keyword results
pub fn apply_rrf(
    vector_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    k: f32,
) -> Vec<HybridSearchResult> {
    let mut fusion_map: std::collections::HashMap<String, HybridSearchResult> =
        std::collections::HashMap::new();

    // Process vector results (semantic search)
    for (rank, (name, score)) in vector_results.into_iter().enumerate() {
        let rrf_score = 1.0 / (k + (rank as f32) + 1.0);
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

    // Process keyword results (BM25)
    for (rank, result) in keyword_results.into_iter().enumerate() {
        let rrf_score = 1.0 / (k + (rank as f32) + 1.0);
        let tool_name = result.tool_name.clone();

        if let Some(entry) = fusion_map.get_mut(&tool_name) {
            entry.rrf_score += rrf_score;
            entry.keyword_score = result.score;
        } else {
            // Found only by keyword - still include it
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

    // Sort by RRF score descending
    let mut results: Vec<_> = fusion_map.into_values().collect();
    results.sort_by(|a, b| b.rrf_score.partial_cmp(&a.rrf_score).unwrap());

    results
}

/// Apply Weighted RRF with Field Boosting (SOTA Algorithm)
///
/// Based on "Optimizing Hybrid Search Query with Reciprocal Rank Fusion" (2025)
/// and BM25F field-level boosting principles.
///
/// # Algorithm
/// 1. Weighted Vector Stream: `W_vector * (1 / (k + rank))`
/// 2. Weighted Keyword Stream: `W_keyword * (1 / (k + rank))`
/// 3. **Smart Fallback**: If keyword results are sparse (< 2), switch to vector-dominant mode
/// 4. Dynamic Field Boosting: Name token matches + Exact phrase match
///
/// # Arguments
///
/// * `vector_results` - Vector search results (name, similarity_score)
/// * `keyword_results` - Keyword search results with BM25 scores
/// * `k` - Smoothing factor (k=10 for high precision, k=60 for high recall)
/// * `semantic_weight` - Weight for vector search contribution
/// * `keyword_weight` - Weight for keyword search contribution
/// * `query` - Original query for field boosting
///
/// # Returns
///
/// Vector of hybrid search results sorted by final score
pub fn apply_weighted_rrf(
    vector_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    k: f32,
    semantic_weight: f32,
    keyword_weight: f32,
    query: &str,
) -> Vec<HybridSearchResult> {
    use crate::keyword::{EXACT_PHRASE_BOOST, NAME_TOKEN_BOOST};
    use std::collections::HashMap;

    let mut fusion_map: HashMap<String, HybridSearchResult> = HashMap::new();
    let query_lower = query.to_lowercase();
    let query_parts: Vec<&str> = query_lower.split_whitespace().collect();

    // Smart Fallback Detection:
    // If keyword results are too sparse (< 2), it likely means:
    // - Query is a code snippet (syntax chars confuse BM25)
    // - Query uses vocabulary not in the index
    // In this case, we boost vector weight and reduce keyword influence.
    let is_keyword_sparse = keyword_results.len() < 2;
    let effective_kw_weight = if is_keyword_sparse {
        0.1
    } else {
        keyword_weight
    };
    let effective_vec_weight = if is_keyword_sparse {
        2.0
    } else {
        semantic_weight
    };

    // Log fallback mode for debugging
    if is_keyword_sparse && !keyword_results.is_empty() {
        log::debug!(
            "Smart RRF Fallback: Sparse keyword results ({}) for query '{}', \
             boosting vector weight to {:.1}",
            keyword_results.len(),
            query,
            effective_vec_weight
        );
    }

    // 1. Weighted Vector Stream
    for (rank, (name, score)) in vector_results.into_iter().enumerate() {
        // Formula: W * (1 / (k + rank))
        let rrf_score = effective_vec_weight * (1.0 / (k + (rank as f32) + 1.0));

        // In fallback mode, add raw similarity score to preserve ranking information
        // This helps when RRF rank-based scoring loses granularity
        let fallback_bonus = if is_keyword_sparse { score * 0.3 } else { 0.0 };

        fusion_map.insert(
            name.clone(),
            HybridSearchResult {
                tool_name: name.clone(),
                rrf_score: rrf_score + fallback_bonus,
                vector_score: score,
                keyword_score: 0.0,
            },
        );
    }

    // 2. Weighted Keyword Stream (BM25)
    // Skip processing if keyword weight is negligible to save CPU
    if effective_kw_weight > 0.05 {
        for (rank, result) in keyword_results.into_iter().enumerate() {
            let rrf_score = effective_kw_weight * (1.0 / (k + (rank as f32) + 1.0));
            let tool_name = result.tool_name.clone();

            if let Some(entry) = fusion_map.get_mut(&tool_name) {
                entry.rrf_score += rrf_score;
                entry.keyword_score = result.score;
            } else {
                // Found only by keyword - include it with metadata
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
    }

    // 3. Dynamic Field Boosting (The "Magic" Step)
    // This solves the confidence flattening issue by injecting hard signals.
    for entry in fusion_map.values_mut() {
        let name_lower = entry.tool_name.to_lowercase();

        // Boost A: Exact Token Match in Name (e.g., "commit" in "git.commit")
        // This simulates Cross-Encoder attention to the name field.
        let mut match_count = 0;
        for term in &query_parts {
            if term.len() > 2 && name_lower.contains(term) {
                match_count += 1;
            }
        }

        // Boost Score: +0.5 per matched term (Significant in RRF space where max is ~0.1)
        if match_count > 0 {
            entry.rrf_score += (match_count as f32) * NAME_TOKEN_BOOST;
        }

        // Boost B: Exact Phrase Match
        if name_lower.contains(&query_lower) {
            entry.rrf_score += EXACT_PHRASE_BOOST;
        }
    }

    // 4. Sort by final score descending
    let mut results: Vec<_> = fusion_map.into_values().collect();
    results.sort_by(|a, b| b.rrf_score.partial_cmp(&a.rrf_score).unwrap());

    results
}

/// Adaptive RRF - Hybrid search with soft fallback for code queries
///
/// Uses Keyword Confidence (β) to smoothly weight between vector and keyword search:
/// - β = 1.0 when keyword results >= 5
/// - β = result_count * 0.2 when < 5
///
/// When keyword is weak (β < 0.5), injects raw cosine similarity to preserve ranking.
pub fn apply_adaptive_rrf(
    vector_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    k: f32,
    base_semantic_weight: f32,
    base_keyword_weight: f32,
    query: &str,
) -> Vec<HybridSearchResult> {
    use crate::keyword::{EXACT_PHRASE_BOOST, NAME_TOKEN_BOOST};
    use ordered_float::OrderedFloat;
    use std::collections::HashMap;

    let mut fusion_map: HashMap<String, HybridSearchResult> = HashMap::new();
    let query_lower = query.to_lowercase();
    let query_parts: Vec<&str> = query_lower.split_whitespace().collect();

    // Keyword Confidence: 5+ results -> 1.0, 4->0.8, 3->0.6, 2->0.4, 1->0.2, 0->0.0
    let kw_count = keyword_results.len();
    let kw_confidence: f32 = if kw_count >= 5 {
        1.0
    } else {
        (kw_count as f32) * 0.2
    };

    // Dynamic weights based on keyword confidence
    let w_vec = base_semantic_weight * (1.0 + (1.0 - kw_confidence));
    let w_kw = base_keyword_weight * kw_confidence;

    if kw_confidence < 1.0 {
        log::debug!(
            "Adaptive RRF: kw_confidence={:.2}, w_vec={:.2}, w_kw={:.2}",
            kw_confidence,
            w_vec,
            w_kw
        );
    }

    // Process vector results
    for (rank, (name, vec_score)) in vector_results.into_iter().enumerate() {
        let rrf_score = w_vec * (1.0 / (k + (rank as f32) + 1.0));

        // Inject raw cosine similarity when keyword is weak
        let raw_score_injection = if kw_confidence < 0.5 {
            vec_score * 0.4
        } else {
            0.0
        };

        fusion_map.insert(
            name.clone(),
            HybridSearchResult {
                tool_name: name,
                rrf_score: rrf_score + raw_score_injection,
                vector_score: vec_score,
                keyword_score: 0.0,
            },
        );
    }

    // Process keyword results
    if w_kw > 0.01 {
        for (rank, result) in keyword_results.into_iter().enumerate() {
            let rrf_score = w_kw * (1.0 / (k + (rank as f32) + 1.0));
            let tool_name = result.tool_name.clone();

            if let Some(entry) = fusion_map.get_mut(&tool_name) {
                entry.rrf_score += rrf_score;
                entry.keyword_score = result.score;
            } else {
                // Keyword-only: penalized for vector-miss
                fusion_map.insert(
                    tool_name,
                    HybridSearchResult {
                        tool_name: result.tool_name.clone(),
                        rrf_score: rrf_score * 0.5,
                        vector_score: 0.0,
                        keyword_score: result.score,
                    },
                );
            }
        }
    }

    // Field boosting
    for entry in fusion_map.values_mut() {
        let name_lower = entry.tool_name.to_lowercase();

        // Token match in name
        let mut match_count = 0;
        for term in &query_parts {
            if term.len() > 2 && name_lower.contains(term) {
                match_count += 1;
            }
        }
        if match_count > 0 {
            entry.rrf_score += (match_count as f32) * NAME_TOKEN_BOOST;
        }

        // Exact phrase match
        if name_lower.contains(&query_lower) {
            entry.rrf_score += EXACT_PHRASE_BOOST;
        }
    }

    // Sort by score
    let mut results: Vec<_> = fusion_map.into_values().collect();
    results.sort_by(|a, b| OrderedFloat(b.rrf_score).cmp(&OrderedFloat(a.rrf_score)));

    results
}
