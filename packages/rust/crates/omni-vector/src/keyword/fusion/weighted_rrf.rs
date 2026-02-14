//! Weighted RRF with field boosting (SOTA algorithm).
//! P5: Boost phase runs in parallel (rayon) over name/token/metadata deltas.

use std::collections::HashMap;

use rayon::prelude::*;

use crate::ToolSearchResult;
use crate::keyword::{EXACT_PHRASE_BOOST, NAME_TOKEN_BOOST};

use super::boost::{file_discovery_boost, is_file_discovery_query, metadata_alignment_boost};
use super::match_util::{
    NameMatchResult, build_name_lower_arrow, build_name_token_automaton_with_phrase,
    count_name_token_matches_and_exact,
};
use super::types::HybridSearchResult;

/// Apply Weighted RRF with Field Boosting.
///
/// Algorithm: weighted vector + keyword streams, smart fallback for sparse keyword results,
/// dynamic field boosting (name token match, exact phrase, metadata alignment).
pub fn apply_weighted_rrf(
    vector_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    k: f32,
    semantic_weight: f32,
    keyword_weight: f32,
    query: &str,
) -> Vec<HybridSearchResult> {
    let mut fusion_map: HashMap<String, HybridSearchResult> = HashMap::new();
    let query_lower = query.to_lowercase();
    let query_parts: Vec<&str> = query_lower.split_whitespace().collect();
    let file_discovery_intent = is_file_discovery_query(&query_lower, &query_parts);
    let keyword_context: HashMap<&str, &ToolSearchResult> = keyword_results
        .iter()
        .map(|r| (r.tool_name.as_str(), r))
        .collect();

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

    if log::log_enabled!(log::Level::Debug) && is_keyword_sparse && !keyword_results.is_empty() {
        log::debug!(
            "Smart RRF Fallback: Sparse keyword results ({}) for query '{}', \
             boosting vector weight to {:.1}",
            keyword_results.len(),
            query,
            effective_vec_weight
        );
    }

    for (rank, (name, score)) in vector_results.into_iter().enumerate() {
        let rrf_score = effective_vec_weight * super::kernels::rrf_term(k, rank);
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

    if effective_kw_weight > 0.05 {
        for (rank, result) in keyword_results.iter().enumerate() {
            let rrf_score = effective_kw_weight * super::kernels::rrf_term(k, rank);
            let tool_name = result.tool_name.as_str();

            if let Some(entry) = fusion_map.get_mut(tool_name) {
                entry.rrf_score += rrf_score;
                entry.keyword_score = result.score;
            } else {
                fusion_map.insert(
                    result.tool_name.clone(),
                    HybridSearchResult {
                        tool_name: result.tool_name.clone(),
                        rrf_score,
                        vector_score: 0.0,
                        keyword_score: result.score,
                    },
                );
            }
        }
    }

    let (keys_ordered, names_lower_array) = build_name_lower_arrow(fusion_map.keys());

    let ac_and_exact = build_name_token_automaton_with_phrase(&query_parts, &query_lower);

    // P5: Parallel boost — compute deltas per index (read-only), then apply once.
    let deltas: Vec<f32> = (0..keys_ordered.len())
        .into_par_iter()
        .map(|i| {
            let tool_name = &keys_ordered[i];
            let name_lower = names_lower_array.value(i);
            let NameMatchResult {
                token_count: match_count,
                exact_phrase,
            } = ac_and_exact
                .as_ref()
                .map(|(ac, exact_id)| count_name_token_matches_and_exact(ac, name_lower, *exact_id))
                .unwrap_or(NameMatchResult::default());

            let mut delta = 0.0;
            if match_count > 0 {
                delta += (match_count as f32) * NAME_TOKEN_BOOST;
            }
            if exact_phrase {
                delta += EXACT_PHRASE_BOOST;
            }
            if let Some(meta) = keyword_context.get(tool_name.as_str()) {
                delta += metadata_alignment_boost(meta, &query_parts);
                if file_discovery_intent && file_discovery_boost(meta) {
                    delta += 0.25;
                }
            }
            delta
        })
        .collect();

    for (i, delta) in deltas.into_iter().enumerate() {
        if let Some(entry) = fusion_map.get_mut(&keys_ordered[i]) {
            entry.rrf_score += delta;
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
