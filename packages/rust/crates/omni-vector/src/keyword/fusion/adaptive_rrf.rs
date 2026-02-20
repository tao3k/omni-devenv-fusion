//! Adaptive RRF with keyword-confidence weighting.
//! P5: Boost phase runs in parallel (rayon).

use std::collections::HashMap;

use rayon::prelude::*;

use crate::ToolSearchResult;
use crate::keyword::{EXACT_PHRASE_BOOST, NAME_TOKEN_BOOST};

use super::match_util::{
    NameMatchResult, build_name_lower_arrow, build_name_token_automaton_with_phrase,
    count_name_token_matches_and_exact,
};
use super::types::HybridSearchResult;

/// Apply Adaptive RRF: soft fallback for code queries via keyword confidence (β).
#[must_use]
pub fn apply_adaptive_rrf(
    vector_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    k: f32,
    base_semantic_weight: f32,
    base_keyword_weight: f32,
    query: &str,
) -> Vec<HybridSearchResult> {
    let mut fusion_map: HashMap<String, HybridSearchResult> = HashMap::new();
    let query_lower = query.to_lowercase();
    let query_parts: Vec<&str> = query_lower.split_whitespace().collect();

    let kw_count = keyword_results.len();
    let kw_confidence: f32 = if kw_count >= 5 {
        1.0
    } else {
        f32::from(u16::try_from(kw_count).unwrap_or(u16::MAX)) * 0.2
    };

    let w_vec = base_semantic_weight * (1.0 + (1.0 - kw_confidence));
    let w_kw = base_keyword_weight * kw_confidence;

    if log::log_enabled!(log::Level::Debug) && kw_confidence < 1.0 {
        log::debug!(
            "Adaptive RRF: kw_confidence={kw_confidence:.2}, w_vec={w_vec:.2}, w_kw={w_kw:.2}"
        );
    }

    for (rank, (name, vec_score)) in vector_results.into_iter().enumerate() {
        let rrf_score = w_vec * super::kernels::rrf_term(k, rank);
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

    if w_kw > 0.01 {
        for (rank, result) in keyword_results.into_iter().enumerate() {
            let rrf_score = w_kw * super::kernels::rrf_term(k, rank);
            let tool_name = result.tool_name.clone();

            if let Some(entry) = fusion_map.get_mut(&tool_name) {
                entry.rrf_score += rrf_score;
                entry.keyword_score = result.score;
            } else {
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

    let (keys_ordered, names_lower_array) = build_name_lower_arrow(fusion_map.keys());

    let ac_and_exact = build_name_token_automaton_with_phrase(&query_parts, &query_lower);

    // P5: Parallel boost — compute deltas per index, then apply once.
    let deltas: Vec<f32> = (0..keys_ordered.len())
        .into_par_iter()
        .map(|i| {
            let name_lower = names_lower_array.value(i);
            let NameMatchResult {
                token_count: match_count,
                exact_phrase,
            } = ac_and_exact
                .as_ref()
                .map_or_else(NameMatchResult::default, |(ac, exact_id)| {
                    count_name_token_matches_and_exact(ac, name_lower, *exact_id)
                });

            let mut delta = 0.0;
            if match_count > 0 {
                delta +=
                    f32::from(u16::try_from(match_count).unwrap_or(u16::MAX)) * NAME_TOKEN_BOOST;
            }
            if exact_phrase {
                delta += EXACT_PHRASE_BOOST;
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
