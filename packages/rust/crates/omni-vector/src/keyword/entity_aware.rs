//! Entity-Aware Search Enhancement
//!
//! Integrates knowledge graph entities with vector/keyword search for improved recall.
//! When entities are provided, they boost results that contain or are related to those entities.

use crate::HybridSearchResult;
use crate::skill::ToolSearchResult;
use aho_corasick::AhoCorasick;
use std::collections::HashSet;

/// Result type for entity-aware search
#[derive(Debug, Clone)]
pub struct EntityAwareSearchResult {
    /// Full result with base scores
    pub base: HybridSearchResult,
    /// Entity matches that contributed to boosting
    pub entity_matches: Vec<EntityMatch>,
    /// Final boosted score
    pub boosted_score: f32,
}

/// An entity that matched in the search
#[derive(Debug, Clone)]
pub struct EntityMatch {
    /// Entity name
    pub entity_name: String,
    /// Entity type (PERSON, TOOL, CONCEPT, etc.)
    pub entity_type: String,
    /// Confidence score of the match
    pub confidence: f32,
    /// How the entity was matched (`name_match`, `metadata_match`, etc.)
    pub match_type: EntityMatchType,
}

/// How an entity was matched in the search
#[derive(Debug, Clone)]
pub enum EntityMatchType {
    /// Entity name exactly matched content
    NameMatch,
    /// Entity aliases matched content
    AliasMatch,
    /// Entity was mentioned in metadata
    MetadataMatch,
    /// Entity is related to a matched result
    RelatedEntity,
}

/// Cached entity data for efficient matching
struct CachedEntity<'a> {
    original: &'a EntityMatch,
    name_lower: String,
}

/// Apply entity boosting to hybrid search results
///
/// # Arguments
///
/// * `results` - Base hybrid search results
/// * `entities` - Entities from knowledge graph to boost with
/// * `entity_weight` - Weight for entity contribution (default 0.3)
/// * `metadata` - Document metadata to check for entity mentions
///
/// # Returns
///
/// Entity-aware results with boosted scores
#[must_use]
#[allow(clippy::needless_pass_by_value)]
#[allow(clippy::too_many_lines)]
pub fn apply_entity_boost(
    results: Vec<HybridSearchResult>,
    entities: Vec<EntityMatch>,
    entity_weight: f32,
    metadata: Option<&[serde_json::Value]>,
) -> Vec<EntityAwareSearchResult> {
    // Pre-compute lowercase entity names for efficient matching
    let cached_entities: Vec<CachedEntity> = entities
        .iter()
        .map(|e| CachedEntity {
            original: e,
            name_lower: e.entity_name.to_lowercase(),
        })
        .collect();

    // Aho-Corasick over entity names: one automaton, O(n+m) per haystack instead of O(entities * contains)
    let (entity_ac, pattern_to_cached_idx): (Option<AhoCorasick>, Vec<usize>) = {
        let mut patterns: Vec<&str> = Vec::new();
        let mut pattern_to_cached_idx: Vec<usize> = Vec::new();
        for (i, c) in cached_entities.iter().enumerate() {
            if !c.name_lower.is_empty() {
                patterns.push(c.name_lower.as_str());
                pattern_to_cached_idx.push(i);
            }
        }
        if patterns.is_empty() {
            (None, Vec::new())
        } else {
            match AhoCorasick::new(patterns) {
                Ok(ac) => (Some(ac), pattern_to_cached_idx),
                Err(_) => (None, Vec::new()),
            }
        }
    };

    let mut aware_results: Vec<EntityAwareSearchResult> = Vec::new();

    for result in results {
        let tool_name_lower = result.tool_name.to_lowercase();
        let mut matched_entities: Vec<EntityMatch> = Vec::new();
        let mut matched_names: HashSet<String> = HashSet::new();

        // Check 1: Direct name match in tool name via Aho-Corasick (O(n+m))
        if let Some(ref ac) = entity_ac {
            for mat in ac.find_iter(&tool_name_lower) {
                let cached_idx = pattern_to_cached_idx.get(mat.pattern().as_usize()).copied();
                if let Some(i) = cached_idx {
                    let cached = &cached_entities[i];
                    if matched_names.insert(cached.name_lower.clone()) {
                        matched_entities.push(cached.original.clone());
                    }
                }
            }
        } else {
            for cached in &cached_entities {
                if tool_name_lower.contains(&cached.name_lower) {
                    matched_entities.push(cached.original.clone());
                    matched_names.insert(cached.name_lower.clone());
                }
            }
        }

        // Check 2: Metadata entity mentions (AC over content_lower)
        if let Some(meta_list) = metadata {
            for meta in meta_list {
                if let Some(content) = meta.get("content").and_then(|c| c.as_str()) {
                    let content_lower = content.to_lowercase();
                    if let Some(ref ac) = entity_ac {
                        for mat in ac.find_iter(&content_lower) {
                            if let Some(&i) = pattern_to_cached_idx.get(mat.pattern().as_usize()) {
                                let cached = &cached_entities[i];
                                if matched_names.insert(cached.name_lower.clone()) {
                                    let mut meta_match = cached.original.clone();
                                    meta_match.match_type = EntityMatchType::MetadataMatch;
                                    matched_entities.push(meta_match);
                                }
                            }
                        }
                    } else {
                        for cached in &cached_entities {
                            if !matched_names.contains(&cached.name_lower)
                                && content_lower.contains(&cached.name_lower)
                            {
                                let mut meta_match = cached.original.clone();
                                meta_match.match_type = EntityMatchType::MetadataMatch;
                                matched_entities.push(meta_match);
                                matched_names.insert(cached.name_lower.clone());
                            }
                        }
                    }
                }
            }
        }

        // Calculate entity boost
        let entity_boost: f32 = if matched_entities.is_empty() {
            0.0
        } else {
            let match_count_f32 =
                u16::try_from(matched_entities.len()).map_or(f32::from(u16::MAX), f32::from);
            let avg_confidence: f32 =
                matched_entities.iter().map(|e| e.confidence).sum::<f32>() / match_count_f32;
            let match_bonus = match_count_f32 * entity_weight * 0.5;
            avg_confidence * entity_weight + match_bonus
        };

        // Apply boost to RRF score
        let boosted_score = result.rrf_score * (1.0 + entity_boost);

        aware_results.push(EntityAwareSearchResult {
            base: result,
            entity_matches: matched_entities,
            boosted_score,
        });
    }

    // Sort by boosted score
    aware_results.sort_by(|a, b| {
        b.boosted_score
            .partial_cmp(&a.boosted_score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    aware_results
}

/// Apply triple RRF fusion with entity awareness
///
/// Combines semantic, keyword, and entity signals using RRF fusion
#[must_use]
pub fn apply_triple_rrf(
    semantic_results: Vec<(String, f32)>,
    keyword_results: Vec<ToolSearchResult>,
    entity_results: Vec<EntityAwareSearchResult>,
    k: f32,
) -> Vec<EntityAwareSearchResult> {
    use std::collections::HashMap;

    let mut fusion_map: HashMap<String, EntityAwareSearchResult> = HashMap::new();

    // Process semantic results
    for (rank, (name, score)) in semantic_results.into_iter().enumerate() {
        let rrf = crate::rrf_term(k, rank);
        fusion_map.insert(
            name.clone(),
            EntityAwareSearchResult {
                base: HybridSearchResult {
                    tool_name: name.clone(),
                    rrf_score: rrf,
                    vector_score: score,
                    keyword_score: 0.0,
                },
                entity_matches: Vec::new(),
                boosted_score: rrf,
            },
        );
    }

    // Process keyword results
    for (rank, result) in keyword_results.into_iter().enumerate() {
        let rrf = crate::rrf_term(k, rank);
        let name = result.tool_name.clone();

        if let Some(existing) = fusion_map.get_mut(&name) {
            existing.base.rrf_score += rrf;
            existing.base.keyword_score = result.score;
            existing.boosted_score = existing.base.rrf_score;
        } else {
            fusion_map.insert(
                name.clone(),
                EntityAwareSearchResult {
                    base: HybridSearchResult {
                        tool_name: name,
                        rrf_score: rrf,
                        vector_score: 0.0,
                        keyword_score: result.score,
                    },
                    entity_matches: Vec::new(),
                    boosted_score: rrf,
                },
            );
        }
    }

    // Process entity-aware results (already boosted)
    for result in entity_results {
        let name = result.base.tool_name.clone();
        if let Some(existing) = fusion_map.get_mut(&name) {
            // Blend with existing
            existing.base.rrf_score = existing.base.rrf_score.midpoint(result.boosted_score);
            existing.entity_matches.extend(result.entity_matches);
        } else {
            fusion_map.insert(name, result);
        }
    }

    // Sort and return
    let mut results: Vec<_> = fusion_map.into_values().collect();
    results.sort_by(|a, b| {
        b.boosted_score
            .partial_cmp(&a.boosted_score)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    results
}

/// Constants for entity boosting
pub const ENTITY_WEIGHT: f32 = 0.3;
/// Minimum confidence score for an entity match to be considered
pub const ENTITY_CONFIDENCE_THRESHOLD: f32 = 0.7;
/// Maximum number of entity matches per result
pub const MAX_ENTITY_MATCHES: usize = 10;

#[cfg(test)]
mod tests {
    include!("entity_aware_tests.rs");
}
