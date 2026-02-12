//! Entity-Aware Search Enhancement
//!
//! Integrates knowledge graph entities with vector/keyword search for improved recall.
//! When entities are provided, they boost results that contain or are related to those entities.

use crate::HybridSearchResult;
use crate::skill::ToolSearchResult;

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
    /// How the entity was matched (name_match, metadata_match, etc.)
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

    // Build entity lookup map by lowercase name for O(1) access
    let mut entity_map: std::collections::HashMap<String, &EntityMatch> =
        std::collections::HashMap::new();
    for entity in &entities {
        entity_map.insert(entity.entity_name.to_lowercase(), entity);
    }

    let mut aware_results: Vec<EntityAwareSearchResult> = Vec::new();

    for result in results {
        let tool_name_lower = result.tool_name.to_lowercase();
        let mut matched_entities: Vec<EntityMatch> = Vec::new();
        let mut matched_names: std::collections::HashSet<String> = std::collections::HashSet::new();

        // Check 1: Direct name match in tool name (O(n) with cached lowercase)
        for cached in &cached_entities {
            if tool_name_lower.contains(&cached.name_lower) {
                matched_entities.push(cached.original.clone());
                matched_names.insert(cached.name_lower.clone());
            }
        }

        // Check 2: Metadata entity mentions
        if let Some(meta_list) = metadata {
            for meta in meta_list {
                if let Some(content) = meta.get("content").and_then(|c| c.as_str()) {
                    let content_lower = content.to_lowercase();
                    for cached in &cached_entities {
                        // Check if not already matched (O(1) with HashSet)
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

        // Calculate entity boost
        let entity_boost: f32 = if !matched_entities.is_empty() {
            let avg_confidence: f32 = matched_entities.iter().map(|e| e.confidence).sum::<f32>()
                / matched_entities.len() as f32;
            let match_bonus = (matched_entities.len() as f32) * entity_weight * 0.5;
            avg_confidence * entity_weight + match_bonus
        } else {
            0.0
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
        let rrf = 1.0 / (k + (rank as f32) + 1.0);
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
        let rrf = 1.0 / (k + (rank as f32) + 1.0);
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
            existing.base.rrf_score = (existing.base.rrf_score + result.boosted_score) / 2.0;
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
