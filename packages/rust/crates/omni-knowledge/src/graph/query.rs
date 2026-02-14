//! Search and multi-hop traversal algorithms for the KnowledgeGraph.

use super::KnowledgeGraph;
use crate::entity::{Entity, EntityType};
use std::collections::{HashMap, HashSet};

/// Scoring weights for entity search relevance.
const EXACT_NAME_SCORE: f64 = 1.0;
const ALIAS_EXACT_SCORE: f64 = 0.95;
const TOKEN_FULL_OVERLAP_SCORE: f64 = 0.85;
const SUBSTRING_NAME_SCORE: f64 = 0.7;
const ALIAS_SUBSTRING_SCORE: f64 = 0.65;
const TOKEN_PARTIAL_OVERLAP_SCORE: f64 = 0.5;
const DESCRIPTION_MATCH_SCORE: f64 = 0.3;
const FUZZY_MATCH_THRESHOLD: f32 = 0.75;
const FUZZY_MATCH_SCORE: f64 = 0.4;

impl KnowledgeGraph {
    /// Search entities with multi-signal relevance scoring.
    ///
    /// Scoring signals (in priority order):
    /// 1. Exact name match (1.0)
    /// 2. Exact alias match (0.95)
    /// 3. Full token overlap — all query tokens appear in name tokens (0.85)
    /// 4. Name substring match (0.7)
    /// 5. Alias substring match (0.65)
    /// 6. Partial token overlap — some query tokens match name tokens (0.5)
    /// 7. Fuzzy name match — Levenshtein similarity ≥ 0.75 (0.4)
    /// 8. Description substring match (0.3)
    pub fn search_entities(&self, query: &str, limit: i32) -> Vec<Entity> {
        let entities = self.entities.read().unwrap();
        let query_lower = query.to_lowercase();

        if query_lower.is_empty() {
            return Vec::new();
        }

        // Tokenize query: split on whitespace, dots, underscores, hyphens
        let query_tokens: Vec<&str> = query_lower
            .split(|c: char| c.is_whitespace() || c == '.' || c == '_' || c == '-')
            .filter(|t| !t.is_empty() && t.len() >= 2)
            .collect();

        let mut scored: Vec<(f64, Entity)> = Vec::new();

        for entity in entities.values() {
            let name_lower = entity.name.to_lowercase();
            let mut best_score: f64 = 0.0;

            // Signal 1: Exact name match
            if name_lower == query_lower {
                best_score = EXACT_NAME_SCORE;
            }

            // Signal 2: Exact alias match
            if best_score < ALIAS_EXACT_SCORE {
                for alias in &entity.aliases {
                    if alias.to_lowercase() == query_lower {
                        best_score = best_score.max(ALIAS_EXACT_SCORE);
                        break;
                    }
                }
            }

            // Signal 3/6: Token overlap scoring
            if best_score < TOKEN_FULL_OVERLAP_SCORE && !query_tokens.is_empty() {
                let name_tokens: HashSet<&str> = name_lower
                    .split(|c: char| c.is_whitespace() || c == '.' || c == '_' || c == '-')
                    .filter(|t| !t.is_empty() && t.len() >= 2)
                    .collect();

                if !name_tokens.is_empty() {
                    let matched = query_tokens
                        .iter()
                        .filter(|qt| {
                            name_tokens
                                .iter()
                                .any(|nt| nt.contains(*qt) || qt.contains(nt))
                        })
                        .count();

                    if matched == query_tokens.len() && matched > 0 {
                        // All query tokens matched
                        best_score = best_score.max(TOKEN_FULL_OVERLAP_SCORE);
                    } else if matched > 0 {
                        // Partial: scale between 0.3 and TOKEN_PARTIAL_OVERLAP_SCORE
                        let ratio = matched as f64 / query_tokens.len() as f64;
                        let partial = TOKEN_PARTIAL_OVERLAP_SCORE * ratio;
                        best_score = best_score.max(partial);
                    }
                }
            }

            // Signal 4: Name substring match
            if best_score < SUBSTRING_NAME_SCORE {
                if name_lower.contains(&query_lower) || query_lower.contains(&name_lower) {
                    best_score = best_score.max(SUBSTRING_NAME_SCORE);
                }
            }

            // Signal 5: Alias substring match
            if best_score < ALIAS_SUBSTRING_SCORE {
                for alias in &entity.aliases {
                    let alias_lower = alias.to_lowercase();
                    if alias_lower.contains(&query_lower) || query_lower.contains(&alias_lower) {
                        best_score = best_score.max(ALIAS_SUBSTRING_SCORE);
                        break;
                    }
                }
            }

            // Signal 7: Fuzzy name match (Levenshtein)
            if best_score < FUZZY_MATCH_SCORE {
                let sim = KnowledgeGraph::name_similarity(&query_lower, &name_lower);
                if sim >= FUZZY_MATCH_THRESHOLD {
                    best_score = best_score.max(FUZZY_MATCH_SCORE * sim as f64);
                }
            }

            // Signal 8: Description substring match
            if best_score < DESCRIPTION_MATCH_SCORE {
                let desc_lower = entity.description.to_lowercase();
                if desc_lower.contains(&query_lower) {
                    best_score = best_score.max(DESCRIPTION_MATCH_SCORE);
                }
            }

            if best_score > 0.0 {
                // Confidence boost: entities with higher confidence rank higher
                let final_score = best_score * (0.8 + 0.2 * entity.confidence as f64);
                scored.push((final_score, entity.clone()));
            }
        }

        scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        scored.truncate(limit as usize);
        scored.into_iter().map(|(_, e)| e).collect()
    }

    /// Multi-hop search: traverse both outgoing AND incoming relations.
    ///
    /// Unlike the previous version (outgoing only), this walks edges
    /// bidirectionally to discover entities connected in either direction.
    pub fn multi_hop_search(&self, start_name: &str, max_hops: usize) -> Vec<Entity> {
        let mut visited: HashSet<String> = HashSet::new();
        let mut found_entities: Vec<Entity> = Vec::new();
        let mut frontier: Vec<String> = vec![start_name.to_string()];

        let entities_by_name = self.entities_by_name.read().unwrap();
        let entities = self.entities.read().unwrap();
        let outgoing = self.outgoing_relations.read().unwrap();
        let incoming = self.incoming_relations.read().unwrap();
        let relations = self.relations.read().unwrap();

        for _hop in 0..max_hops {
            let mut next_frontier: Vec<String> = Vec::new();

            for entity_name in &frontier {
                if visited.contains(entity_name) {
                    continue;
                }
                visited.insert(entity_name.clone());

                if let Some(entity_id) = entities_by_name.get(entity_name) {
                    if let Some(entity) = entities.get(entity_id) {
                        if !found_entities.iter().any(|e| e.id == entity.id) {
                            found_entities.push(entity.clone());
                        }
                    }
                }

                // Walk outgoing relations (source → target)
                if let Some(rel_ids) = outgoing.get(entity_name) {
                    for rel_id in rel_ids {
                        if let Some(relation) = relations.get(rel_id) {
                            if !visited.contains(&relation.target) {
                                next_frontier.push(relation.target.clone());
                            }
                        }
                    }
                }

                // Walk incoming relations (target ← source)
                if let Some(rel_ids) = incoming.get(entity_name) {
                    for rel_id in rel_ids {
                        if let Some(relation) = relations.get(rel_id) {
                            if !visited.contains(&relation.source) {
                                next_frontier.push(relation.source.clone());
                            }
                        }
                    }
                }
            }

            if next_frontier.is_empty() {
                break;
            }
            frontier = next_frontier;
        }

        found_entities
    }

    /// Query-time tool relevance scoring.
    ///
    /// Given a set of query terms, find TOOL entities connected to those terms
    /// via the KnowledgeGraph and return a relevance score for each tool.
    ///
    /// Algorithm:
    /// 1. For each query term, search for matching entities (exact + keyword + substring + fuzzy).
    /// 2. From each matched entity, walk outgoing/incoming relations (1-2 hops).
    /// 3. Collect all reachable TOOL entities and accumulate a score based on
    ///    hop distance and relation type.
    ///
    /// Returns: Vec<(tool_name, score)> sorted by score descending, capped at `limit`.
    pub fn query_tool_relevance(
        &self,
        query_terms: &[String],
        max_hops: usize,
        limit: usize,
    ) -> Vec<(String, f64)> {
        let entities_by_name = self.entities_by_name.read().unwrap();
        let entities = self.entities.read().unwrap();
        let outgoing = self.outgoing_relations.read().unwrap();
        let incoming = self.incoming_relations.read().unwrap();
        let relations = self.relations.read().unwrap();

        // Phase 1: Find seed entities matching query terms
        let mut seed_entities: Vec<(String, f64)> = Vec::new();
        for term in query_terms {
            let term_lower = term.to_lowercase();
            if term_lower.is_empty() {
                continue;
            }

            // Exact name match
            if entities_by_name.contains_key(&term_lower) {
                seed_entities.push((term_lower.clone(), 1.0));
            }

            // Keyword concept match
            let keyword_name = format!("keyword:{}", term_lower);
            if entities_by_name.contains_key(&keyword_name) {
                seed_entities.push((keyword_name.clone(), 0.8));
            }

            // Alias match: check all entities for alias hits
            for entity in entities.values() {
                for alias in &entity.aliases {
                    if alias.to_lowercase() == term_lower {
                        let ename = entity.name.clone();
                        if !seed_entities.iter().any(|(n, _)| n == &ename) {
                            seed_entities.push((ename, 0.85));
                        }
                        break;
                    }
                }
            }

            // Substring search in entity names (limited)
            for name in entities_by_name.keys() {
                if name.contains(&term_lower) && name != &term_lower && name != &keyword_name {
                    if !seed_entities.iter().any(|(n, _)| n == name) {
                        seed_entities.push((name.clone(), 0.5));
                    }
                }
            }

            // Token overlap: split entity names by . _ - and check partial match
            for (name, _) in entities_by_name.iter() {
                let name_tokens: Vec<&str> = name
                    .split(|c: char| c == '.' || c == '_' || c == '-')
                    .filter(|t| !t.is_empty())
                    .collect();
                if name_tokens
                    .iter()
                    .any(|nt| *nt == term_lower || nt.contains(&*term_lower))
                {
                    if !seed_entities.iter().any(|(n, _)| n == name) {
                        seed_entities.push((name.clone(), 0.4));
                    }
                }
            }
        }

        if seed_entities.is_empty() {
            return Vec::new();
        }

        // Phase 2: Walk graph from seeds, collect TOOL entities with scores
        let mut tool_scores: HashMap<String, f64> = HashMap::new();

        for (seed_name, base_score) in &seed_entities {
            let mut visited: HashSet<String> = HashSet::new();
            let mut frontier: Vec<(String, f64)> = vec![(seed_name.clone(), *base_score)];

            for hop in 0..max_hops {
                let decay = match hop {
                    0 => 1.0,
                    1 => 0.5,
                    _ => 0.25,
                };
                let mut next_frontier: Vec<(String, f64)> = Vec::new();

                for (entity_name, score) in &frontier {
                    if visited.contains(entity_name) {
                        continue;
                    }
                    visited.insert(entity_name.clone());

                    // Check if this entity is a TOOL
                    if let Some(entity_id) = entities_by_name.get(entity_name) {
                        if let Some(entity) = entities.get(entity_id) {
                            if entity.entity_type == EntityType::Tool {
                                let entry = tool_scores.entry(entity.name.clone()).or_insert(0.0);
                                *entry = (*entry + score * decay).min(2.0);
                            }
                        }
                    }

                    // Walk outgoing relations
                    if let Some(rel_ids) = outgoing.get(entity_name) {
                        for rel_id in rel_ids {
                            if let Some(rel) = relations.get(rel_id) {
                                if !visited.contains(&rel.target) {
                                    let bonus = if rel.relation_type
                                        == crate::entity::RelationType::Contains
                                    {
                                        0.2
                                    } else {
                                        0.0
                                    };
                                    next_frontier.push((rel.target.clone(), score * decay + bonus));
                                }
                            }
                        }
                    }

                    // Walk incoming relations (reverse edges)
                    if let Some(rel_ids) = incoming.get(entity_name) {
                        for rel_id in rel_ids {
                            if let Some(rel) = relations.get(rel_id) {
                                if !visited.contains(&rel.source) {
                                    next_frontier.push((rel.source.clone(), score * decay));
                                }
                            }
                        }
                    }
                }

                if next_frontier.is_empty() {
                    break;
                }
                frontier = next_frontier;
            }
        }

        let mut results: Vec<(String, f64)> = tool_scores.into_iter().collect();
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(limit);
        results
    }
}
