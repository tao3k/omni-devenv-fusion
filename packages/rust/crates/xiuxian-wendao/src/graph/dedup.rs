//! Entity deduplication, normalization, and similarity scoring.

use super::{GraphError, KnowledgeGraph, read_lock};
use crate::entity::Entity;
use serde_json::json;
use std::collections::HashSet;
use unicode_normalization::UnicodeNormalization;

/// Result of deduplication operation.
#[derive(Debug, Clone, Default)]
pub struct DeduplicationResult {
    /// Number of duplicate groups found
    pub duplicate_groups_found: usize,
    /// Number of entities merged (removed)
    pub entities_merged: usize,
}

impl KnowledgeGraph {
    /// Calculate similarity between two entity names (0.0 to 1.0).
    #[must_use]
    pub fn name_similarity(name1: &str, name2: &str) -> f32 {
        let n1 = normalize_name(name1);
        let n2 = normalize_name(name2);

        if n1 == n2 {
            return 1.0;
        }

        // Exact substring match
        if n1.contains(&n2) || n2.contains(&n1) {
            return 0.9;
        }

        // Levenshtein-based similarity
        let max_len = std::cmp::max(n1.len(), n2.len());
        if max_len == 0 {
            return 1.0;
        }

        let distance = levenshtein_distance(&n1, &n2);
        let distance_u16 = u16::try_from(distance).unwrap_or(u16::MAX);
        let max_len_u16 = u16::try_from(max_len).unwrap_or(u16::MAX);
        let similarity = 1.0 - (f32::from(distance_u16) / f32::from(max_len_u16));

        // Apply bonus for word overlap
        let words1: HashSet<&str> = n1.split_whitespace().collect();
        let words2: HashSet<&str> = n2.split_whitespace().collect();
        let overlap_count = words1.intersection(&words2).count();
        let overlap = f32::from(u16::try_from(overlap_count).unwrap_or(u16::MAX));
        let word_bonus = if !words1.is_empty() && !words2.is_empty() {
            let total_words = u16::try_from(words1.len() + words2.len()).unwrap_or(u16::MAX);
            overlap / f32::from(total_words) * 0.2
        } else {
            0.0
        };

        (similarity + word_bonus).clamp(0.0, 1.0)
    }

    /// Find potential duplicate entities.
    #[must_use]
    pub fn find_duplicates(&self, threshold: f32) -> Vec<Vec<String>> {
        let entities = read_lock(&self.entities);
        let names: Vec<(String, String)> = entities
            .values()
            .map(|e| (e.name.clone(), e.id.clone()))
            .collect();

        let mut groups: Vec<Vec<String>> = Vec::new();
        let mut visited: HashSet<String> = HashSet::new();

        for (name, id) in &names {
            if visited.contains(id) {
                continue;
            }

            let mut group: Vec<String> = vec![id.clone()];
            visited.insert(id.clone());

            for (other_name, other_id) in &names {
                if id == other_id || visited.contains(other_id) {
                    continue;
                }

                if Self::name_similarity(name, other_name) >= threshold {
                    group.push(other_id.clone());
                    visited.insert(other_id.clone());
                }
            }

            if group.len() > 1 {
                groups.push(group);
            }
        }

        groups
    }

    /// Merge multiple entities into a single canonical entity.
    ///
    /// # Errors
    ///
    /// Returns [`GraphError::EntityNotFound`] when no IDs can be resolved.
    pub fn merge_entities(
        &self,
        entity_ids: &[String],
        canonical_name: &str,
    ) -> Result<Entity, GraphError> {
        let entities = read_lock(&self.entities);

        let mut merged = None;
        let mut all_aliases: Vec<String> = Vec::new();
        let mut sources: Vec<String> = Vec::new();
        let mut max_confidence: f32 = 0.0;

        for id in entity_ids {
            if let Some(entity) = entities.get(id) {
                if merged.is_none() {
                    merged = Some(entity.clone());
                } else if let Some(current) = &mut merged {
                    for alias in &entity.aliases {
                        if !current.aliases.contains(alias) {
                            all_aliases.push(alias.clone());
                        }
                    }
                    if !current.aliases.contains(&entity.name) {
                        all_aliases.push(entity.name.clone());
                    }

                    if let Some(ref src) = entity.source
                        && !sources.contains(src)
                    {
                        sources.push(src.clone());
                    }

                    max_confidence = max_confidence.max(entity.confidence);
                }
            }
        }

        if let Some(mut canonical) = merged {
            if !canonical_name.is_empty() {
                canonical.name = canonical_name.to_string();
            }
            let mut existing_aliases = canonical.aliases.clone();
            existing_aliases.extend(all_aliases);
            existing_aliases.sort();
            existing_aliases.dedup();
            canonical.aliases = existing_aliases;

            if !sources.is_empty() {
                canonical
                    .metadata
                    .insert("merged_sources".to_string(), json!(sources));
            }

            canonical.confidence = max_confidence.max(canonical.confidence);
            canonical.updated_at = chrono::Utc::now();

            // Remove old entities and add canonical
            drop(entities);

            for id in entity_ids {
                self.remove_entity(id)?;
            }

            self.add_entity(canonical.clone())?;

            Ok(canonical)
        } else {
            Err(GraphError::EntityNotFound(entity_ids.join(", ")))
        }
    }

    /// Auto-deduplicate the graph based on similarity threshold.
    #[must_use]
    pub fn deduplicate(&self, threshold: f32) -> DeduplicationResult {
        let duplicates = self.find_duplicates(threshold);

        let mut merged_count = 0;
        let duplicate_groups = duplicates.len();

        for group in &duplicates {
            if group.len() > 1 {
                let canonical_name = self.find_canonical_name(group);
                if self.merge_entities(group, &canonical_name).is_ok() {
                    merged_count += group.len() - 1;
                }
            }
        }

        DeduplicationResult {
            duplicate_groups_found: duplicate_groups,
            entities_merged: merged_count,
        }
    }

    /// Find the most canonical name from a group of entity IDs.
    fn find_canonical_name(&self, entity_ids: &[String]) -> String {
        let entities = read_lock(&self.entities);

        let mut best: Option<(usize, String)> = None;

        for id in entity_ids {
            if let Some(entity) = entities.get(id) {
                let score = entity.description.len() + entity.aliases.len() * 10;
                if let Some((best_score, _)) = &best {
                    if score > *best_score {
                        best = Some((score, entity.name.clone()));
                    }
                } else {
                    best = Some((score, entity.name.clone()));
                }
            }
        }

        best.map_or_else(
            || entity_ids.first().cloned().unwrap_or_default(),
            |(_, name)| name,
        )
    }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/// Normalize entity name for comparison (Unicode NFKC + lowercase).
fn normalize_name(name: &str) -> String {
    let normalized: String = name.nfkc().collect();
    normalized
        .to_lowercase()
        .trim()
        .replace(|c: char| !c.is_alphanumeric() && c != ' ', "")
}

/// Calculate Levenshtein distance between two strings.
fn levenshtein_distance(a: &str, b: &str) -> usize {
    let a_chars: Vec<char> = a.chars().collect();
    let b_chars: Vec<char> = b.chars().collect();

    let (m, n) = (a_chars.len(), b_chars.len());

    if m == 0 {
        return n;
    }
    if n == 0 {
        return m;
    }

    let mut prev = (0..=n).collect::<Vec<_>>();
    let mut curr = vec![0; n + 1];

    for i in 1..=m {
        curr[0] = i;
        for j in 1..=n {
            let cost = usize::from(a_chars[i - 1] != b_chars[j - 1]);
            let deletion = prev[j] + 1;
            let insertion = curr[j - 1] + 1;
            let substitution = prev[j - 1] + cost;
            curr[j] = deletion.min(insertion).min(substitution);
        }
        std::mem::swap(&mut prev, &mut curr);
    }

    prev[n]
}
