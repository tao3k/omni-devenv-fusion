//! Knowledge graph storage and operations.
//!
//! Provides in-memory knowledge graph storage with entity and relation management.
//! Supports saving/loading to JSON files for persistence.

use crate::entity::{Entity, GraphStats, Relation, RelationType};
use log::info;
use serde_json::{Value, json, to_string};
use std::collections::{HashMap, HashSet};
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::PathBuf;
use std::sync::{Arc, RwLock};
use thiserror::Error;
use unicode_normalization::UnicodeNormalization;

/// Graph errors.
#[derive(Debug, Error)]
pub enum GraphError {
    #[error("Entity not found: {0}")]
    EntityNotFound(String),
    #[error("Relation already exists: {0}")]
    RelationExists(String),
    #[error("Invalid relation: source={0}, target={1}")]
    InvalidRelation(String, String),
}

/// Knowledge graph storage.
#[derive(Debug, Clone)]
pub struct KnowledgeGraph {
    /// Entities by ID
    entities: Arc<RwLock<HashMap<String, Entity>>>,
    /// Entities by name (for quick lookup)
    entities_by_name: Arc<RwLock<HashMap<String, String>>>,
    /// Relations by ID
    relations: Arc<RwLock<HashMap<String, Relation>>>,
    /// Outgoing relations (entity name -> set of relation IDs)
    outgoing_relations: Arc<RwLock<HashMap<String, HashSet<String>>>>,
    /// Incoming relations (entity name -> set of relation IDs)
    incoming_relations: Arc<RwLock<HashMap<String, HashSet<String>>>>,
    /// Entities by type
    entities_by_type: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

impl Default for KnowledgeGraph {
    fn default() -> Self {
        Self::new()
    }
}

impl KnowledgeGraph {
    /// Create a new knowledge graph.
    pub fn new() -> Self {
        Self {
            entities: Arc::new(RwLock::new(HashMap::new())),
            entities_by_name: Arc::new(RwLock::new(HashMap::new())),
            relations: Arc::new(RwLock::new(HashMap::new())),
            outgoing_relations: Arc::new(RwLock::new(HashMap::new())),
            incoming_relations: Arc::new(RwLock::new(HashMap::new())),
            entities_by_type: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Add an entity.
    pub fn add_entity(&self, entity: Entity) -> Result<(), GraphError> {
        let mut entities = self.entities.write().unwrap();
        let mut entities_by_name = self.entities_by_name.write().unwrap();
        let mut entities_by_type = self.entities_by_type.write().unwrap();

        // Check if entity already exists by name
        let type_str = entity.entity_type.to_string();
        if let Some(existing_id) = entities_by_name.get(&entity.name) {
            // Update existing entity
            if let Some(existing) = entities.get_mut(existing_id) {
                existing.description = entity.description;
                existing.source = entity.source.or(existing.source.clone());
                existing.aliases = entity.aliases;
                existing.confidence = entity.confidence;
                existing.updated_at = entity.updated_at;
                info!("Updated entity: {}", entity.name);
                return Ok(());
            }
        }

        // Add new entity
        let entity_id = entity.id.clone();
        entities.insert(entity_id.clone(), entity.clone());
        entities_by_name.insert(entity.name.clone(), entity_id.clone());

        // Add to type index
        entities_by_type
            .entry(type_str)
            .or_insert_with(Vec::new)
            .push(entity_id.clone());

        info!("Added entity: {} ({})", entity.name, entity.entity_type);
        Ok(())
    }

    /// Add a relation.
    pub fn add_relation(&self, relation: Relation) -> Result<(), GraphError> {
        let mut relations = self.relations.write().unwrap();
        let mut outgoing = self.outgoing_relations.write().unwrap();
        let mut incoming = self.incoming_relations.write().unwrap();

        // Check if relation already exists
        if relations.contains_key(&relation.id) {
            info!("Relation already exists: {}", relation.id);
            return Ok(());
        }

        // Validate that source and target entities exist
        {
            let entities_by_name = self.entities_by_name.read().unwrap();
            if !entities_by_name.contains_key(&relation.source) {
                return Err(GraphError::InvalidRelation(
                    relation.source.clone(),
                    relation.target.clone(),
                ));
            }
            if !entities_by_name.contains_key(&relation.target) {
                return Err(GraphError::InvalidRelation(
                    relation.source.clone(),
                    relation.target.clone(),
                ));
            }
        }

        // Add relation
        let relation_id = relation.id.clone();
        relations.insert(relation_id.clone(), relation.clone());

        // Update outgoing relations
        outgoing
            .entry(relation.source.clone())
            .or_insert_with(HashSet::new)
            .insert(relation_id.clone());

        // Update incoming relations
        incoming
            .entry(relation.target.clone())
            .or_insert_with(HashSet::new)
            .insert(relation_id.clone());

        info!(
            "Added relation: {} -> {} ({})",
            relation.source, relation.target, relation.relation_type
        );
        Ok(())
    }

    /// Get an entity by ID.
    pub fn get_entity(&self, entity_id: &str) -> Option<Entity> {
        self.entities.read().unwrap().get(entity_id).cloned()
    }

    /// Get an entity by name.
    pub fn get_entity_by_name(&self, name: &str) -> Option<Entity> {
        let entities_by_name = self.entities_by_name.read().unwrap();
        if let Some(entity_id) = entities_by_name.get(name) {
            return self.entities.read().unwrap().get(entity_id).cloned();
        }
        None
    }

    /// Search entities.
    pub fn search_entities(&self, query: &str, limit: i32) -> Vec<Entity> {
        let entities = self.entities.read().unwrap();
        let query_lower = query.to_lowercase();

        let mut results: Vec<_> = entities
            .values()
            .filter(|e| {
                e.name.to_lowercase().contains(&query_lower)
                    || e.description.to_lowercase().contains(&query_lower)
            })
            .take(limit as usize)
            .cloned()
            .collect();

        results.sort_by(|a, b| b.confidence.partial_cmp(&a.confidence).unwrap());
        results
    }

    /// Get entities by type.
    pub fn get_entities_by_type(&self, entity_type: &str) -> Vec<Entity> {
        let entities_by_type = self.entities_by_type.read().unwrap();
        let entities = self.entities.read().unwrap();

        if let Some(entity_ids) = entities_by_type.get(entity_type) {
            entity_ids
                .iter()
                .filter_map(|id| entities.get(id).cloned())
                .collect()
        } else {
            Vec::new()
        }
    }

    /// Get relations for an entity.
    pub fn get_relations(
        &self,
        entity_name: Option<&str>,
        relation_type: Option<RelationType>,
    ) -> Vec<Relation> {
        let relations = self.relations.read().unwrap();
        let mut results: Vec<Relation> = relations.values().cloned().collect();

        if let Some(name) = entity_name {
            let name_lower = name.to_lowercase();
            results.retain(|r| {
                r.source.to_lowercase() == name_lower || r.target.to_lowercase() == name_lower
            });
        }

        if let Some(rtype) = relation_type {
            results.retain(|r| r.relation_type == rtype);
        }

        results
    }

    /// Multi-hop search.
    pub fn multi_hop_search(&self, start_name: &str, max_hops: usize) -> Vec<Entity> {
        let mut visited: HashSet<String> = HashSet::new();
        let mut found_entities: Vec<Entity> = Vec::new();
        let mut frontier: Vec<String> = vec![start_name.to_string()];

        let entities_by_name = self.entities_by_name.read().unwrap();
        let entities = self.entities.read().unwrap();
        let outgoing = self.outgoing_relations.read().unwrap();
        let relations = self.relations.read().unwrap();

        for _hop in 0..max_hops {
            let mut next_frontier: Vec<String> = Vec::new();

            for entity_name in &frontier {
                if visited.contains(entity_name) {
                    continue;
                }
                visited.insert(entity_name.clone());

                // Get entity if not already collected
                if let Some(entity_id) = entities_by_name.get(entity_name) {
                    if let Some(entity) = entities.get(entity_id) {
                        if !found_entities.iter().any(|e| e.id == entity.id) {
                            found_entities.push(entity.clone());
                        }
                    }
                }

                // Get neighbors
                if let Some(rel_ids) = outgoing.get(entity_name) {
                    for rel_id in rel_ids {
                        if let Some(relation) = relations.get(rel_id) {
                            if !visited.contains(&relation.target) {
                                next_frontier.push(relation.target.clone());
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

    /// Get graph statistics.
    pub fn get_stats(&self) -> GraphStats {
        let entities = self.entities.read().unwrap();
        let relations = self.relations.read().unwrap();
        let entities_by_type = self.entities_by_type.read().unwrap();

        let mut entities_by_type_count: HashMap<String, i64> = HashMap::new();
        for (etype, eids) in entities_by_type.iter() {
            entities_by_type_count.insert(etype.clone(), eids.len() as i64);
        }

        let mut relations_by_type: HashMap<String, i64> = HashMap::new();
        for rel in relations.values() {
            let rtype = rel.relation_type.to_string();
            *relations_by_type.entry(rtype).or_insert(0) += 1;
        }

        GraphStats {
            total_entities: entities.len() as i64,
            total_relations: relations.len() as i64,
            entities_by_type: entities_by_type_count,
            relations_by_type,
            last_updated: None,
        }
    }

    /// Clear all entities and relations.
    pub fn clear(&mut self) {
        let mut entities = self.entities.write().unwrap();
        let mut entities_by_name = self.entities_by_name.write().unwrap();
        let mut relations = self.relations.write().unwrap();
        let mut outgoing = self.outgoing_relations.write().unwrap();
        let mut incoming = self.incoming_relations.write().unwrap();
        let mut entities_by_type = self.entities_by_type.write().unwrap();

        entities.clear();
        entities_by_name.clear();
        relations.clear();
        outgoing.clear();
        incoming.clear();
        entities_by_type.clear();

        info!("Knowledge graph cleared");
    }

    /// Save graph to JSON file.
    pub fn save_to_file(&self, path: &str) -> Result<(), GraphError> {
        let entities = self.entities.read().unwrap();
        let relations = self.relations.read().unwrap();

        // Build export structure
        let entities_json: Vec<Value> = entities
            .values()
            .map(|e| {
                json!({
                    "id": e.id,
                    "name": e.name,
                    "entity_type": e.entity_type.to_string(),
                    "description": e.description,
                    "source": e.source,
                    "aliases": e.aliases,
                    "confidence": e.confidence,
                    "metadata": e.metadata,
                    "created_at": e.created_at,
                    "updated_at": e.updated_at,
                })
            })
            .collect();

        let relations_json: Vec<Value> = relations
            .values()
            .map(|r| {
                json!({
                    "id": r.id,
                    "source": r.source,
                    "target": r.target,
                    "relation_type": r.relation_type.to_string(),
                    "description": r.description,
                    "source_doc": r.source_doc,
                    "confidence": r.confidence,
                    "metadata": r.metadata,
                })
            })
            .collect();

        let export = json!({
            "version": 1,
            "exported_at": chrono::Utc::now().to_rfc3339(),
            "total_entities": entities_json.len(),
            "total_relations": relations_json.len(),
            "entities": entities_json,
            "relations": relations_json,
        });

        // Write to file
        let path_buf = PathBuf::from(path);
        if let Some(parent) = path_buf.parent() {
            if !parent.exists() {
                if let Err(e) = fs::create_dir_all(parent) {
                    return Err(GraphError::InvalidRelation(
                        parent.to_string_lossy().to_string(),
                        e.to_string(),
                    ));
                }
            }
        }

        let json_str = to_string(&export)
            .map_err(|e| GraphError::InvalidRelation("serialization".to_string(), e.to_string()))?;

        let mut file = File::create(path_buf)
            .map_err(|e| GraphError::InvalidRelation(path.to_string(), e.to_string()))?;

        file.write_all(json_str.as_bytes())
            .map_err(|e| GraphError::InvalidRelation(path.to_string(), e.to_string()))?;

        info!(
            "Knowledge graph saved to: {} ({} entities, {} relations)",
            path,
            entities_json.len(),
            relations_json.len()
        );

        Ok(())
    }

    /// Load graph from JSON file.
    pub fn load_from_file(&mut self, path: &str) -> Result<(), GraphError> {
        let mut file = File::open(path)
            .map_err(|e| GraphError::InvalidRelation(path.to_string(), e.to_string()))?;

        let mut content = String::new();
        file.read_to_string(&mut content)
            .map_err(|e| GraphError::InvalidRelation(path.to_string(), e.to_string()))?;

        let value: Value = serde_json::from_str(&content)
            .map_err(|e| GraphError::InvalidRelation("parse".to_string(), e.to_string()))?;

        // Clear existing data
        self.clear();

        // Parse entities
        if let Some(entities_arr) = value.get("entities").and_then(|v| v.as_array()) {
            for entity_val in entities_arr {
                if let Some(entity) = entity_from_dict(entity_val) {
                    self.add_entity(entity).ok();
                }
            }
        }

        // Parse relations
        if let Some(relations_arr) = value.get("relations").and_then(|v| v.as_array()) {
            for relation_val in relations_arr {
                if let Some(relation) = relation_from_dict(relation_val) {
                    self.add_relation(relation).ok();
                }
            }
        }

        let stats = self.get_stats();
        info!(
            "Knowledge graph loaded from: {} ({} entities, {} relations)",
            path, stats.total_entities, stats.total_relations
        );

        Ok(())
    }

    /// Export graph as JSON string.
    pub fn export_as_json(&self) -> Result<String, GraphError> {
        let entities = self.entities.read().unwrap();
        let relations = self.relations.read().unwrap();

        let entities_json: Vec<Value> = entities
            .values()
            .map(|e| {
                json!({
                    "id": e.id,
                    "name": e.name,
                    "entity_type": e.entity_type.to_string(),
                    "description": e.description,
                    "source": e.source,
                    "aliases": e.aliases,
                    "confidence": e.confidence,
                })
            })
            .collect();

        let relations_json: Vec<Value> = relations
            .values()
            .map(|r| {
                json!({
                    "id": r.id,
                    "source": r.source,
                    "target": r.target,
                    "relation_type": r.relation_type.to_string(),
                    "description": r.description,
                    "source_doc": r.source_doc,
                    "confidence": r.confidence,
                })
            })
            .collect();

        let export = json!({
            "version": 1,
            "exported_at": chrono::Utc::now().to_rfc3339(),
            "total_entities": entities_json.len(),
            "total_relations": relations_json.len(),
            "entities": entities_json,
            "relations": relations_json,
        });

        to_string(&export)
            .map_err(|e| GraphError::InvalidRelation("export".to_string(), e.to_string()))
    }

    /// Get all entities as a vector.
    pub fn get_all_entities(&self) -> Vec<Entity> {
        self.entities.read().unwrap().values().cloned().collect()
    }

    /// Get all relations as a vector.
    pub fn get_all_relations(&self) -> Vec<Relation> {
        self.relations.read().unwrap().values().cloned().collect()
    }

    // =========================================================================
    // Entity Deduplication & Normalization
    // =========================================================================

    /// Normalize entity name for comparison.
    fn normalize_name(name: &str) -> String {
        // Unicode normalization (NFKC)
        let normalized: String = name.nfkc().collect();
        // Lowercase, trim, remove special chars
        normalized
            .to_lowercase()
            .trim()
            .replace(|c: char| !c.is_alphanumeric() && c != ' ', "")
    }

    /// Calculate similarity between two entity names (0.0 to 1.0).
    pub fn name_similarity(name1: &str, name2: &str) -> f32 {
        let n1 = Self::normalize_name(name1);
        let n2 = Self::normalize_name(name2);

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

        let distance = Self::levenshtein_distance(&n1, &n2);
        let similarity = 1.0 - (distance as f32 / max_len as f32);

        // Apply bonus for word overlap
        let words1: HashSet<&str> = n1.split_whitespace().collect();
        let words2: HashSet<&str> = n2.split_whitespace().collect();
        let overlap = words1.intersection(&words2).count() as f32;
        let word_bonus = if !words1.is_empty() && !words2.is_empty() {
            overlap / (words1.len() + words2.len()) as f32 * 0.2
        } else {
            0.0
        };

        (similarity + word_bonus).min(1.0).max(0.0)
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
                let cost = if a_chars[i - 1] == b_chars[j - 1] {
                    0
                } else {
                    1
                };
                let deletion = prev[j] + 1;
                let insertion = curr[j - 1] + 1;
                let substitution = prev[j - 1] + cost;
                curr[j] = deletion.min(insertion).min(substitution);
            }
            std::mem::swap(&mut prev, &mut curr);
        }

        prev[n]
    }

    /// Find potential duplicate entities.
    pub fn find_duplicates(&self, threshold: f32) -> Vec<Vec<String>> {
        let entities = self.entities.read().unwrap();
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
    pub fn merge_entities(
        &self,
        entity_ids: &[String],
        canonical_name: &str,
    ) -> Result<Entity, GraphError> {
        let entities = self.entities.read().unwrap();

        let mut merged = None;
        let mut all_aliases: Vec<String> = Vec::new();
        let mut sources: Vec<String> = Vec::new();
        let mut max_confidence: f32 = 0.0;

        for id in entity_ids {
            if let Some(entity) = entities.get(id) {
                if merged.is_none() {
                    merged = Some(entity.clone());
                } else if let Some(current) = &mut merged {
                    // Merge aliases
                    for alias in &entity.aliases {
                        if !current.aliases.contains(alias) {
                            all_aliases.push(alias.clone());
                        }
                    }
                    if !current.aliases.contains(&entity.name) {
                        all_aliases.push(entity.name.clone());
                    }

                    // Collect sources
                    if let Some(ref src) = entity.source {
                        if !sources.contains(src) {
                            sources.push(src.clone());
                        }
                    }

                    // Keep higher confidence
                    max_confidence = max_confidence.max(entity.confidence);
                }
            }
        }

        if let Some(mut canonical) = merged {
            if !canonical_name.is_empty() {
                canonical.name = canonical_name.to_string();
            }
            // Merge aliases into canonical
            let mut existing_aliases = canonical.aliases.clone();
            existing_aliases.extend(all_aliases);
            existing_aliases.sort();
            existing_aliases.dedup();
            canonical.aliases = existing_aliases;

            // Add sources to description or metadata
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

    /// Remove an entity by ID.
    pub fn remove_entity(&self, entity_id: &str) -> Result<(), GraphError> {
        let mut entities = self.entities.write().unwrap();
        let mut entities_by_name = self.entities_by_name.write().unwrap();
        let mut entities_by_type = self.entities_by_type.write().unwrap();
        let mut relations = self.relations.write().unwrap();
        let mut outgoing = self.outgoing_relations.write().unwrap();
        let mut incoming = self.incoming_relations.write().unwrap();

        if let Some(entity) = entities.remove(entity_id) {
            // Remove from name index
            entities_by_name.remove(&entity.name);

            // Remove from type index
            if let Some(ids) = entities_by_type.get_mut(&entity.entity_type.to_string()) {
                ids.retain(|id| id != entity_id);
            }

            // Remove relations involving this entity
            let rel_ids_to_remove: Vec<String> = relations
                .keys()
                .filter(|id| {
                    if let Some(rel) = relations.get(id.as_str()) {
                        rel.source == entity.name || rel.target == entity.name
                    } else {
                        false
                    }
                })
                .cloned()
                .collect();

            for rid in rel_ids_to_remove {
                relations.remove(&rid);
                outgoing.remove(&entity.name);
                incoming.remove(&entity.name);
            }

            info!("Removed entity: {} ({})", entity.name, entity_id);
            Ok(())
        } else {
            Err(GraphError::EntityNotFound(entity_id.to_string()))
        }
    }

    /// Auto-deduplicate the graph based on similarity threshold.
    pub fn deduplicate(&self, threshold: f32) -> DeduplicationResult {
        let duplicates = self.find_duplicates(threshold);

        let mut merged_count = 0;
        let duplicate_groups = duplicates.len();

        for group in &duplicates {
            if group.len() > 1 {
                // Use the most common name as canonical
                let canonical_name = self.find_canonical_name(group);
                if self.merge_entities(group, &canonical_name).is_ok() {
                    merged_count += group.len() - 1; // -1 because we keep one
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
        let entities = self.entities.read().unwrap();

        // Find the most complete entity (longest description, most aliases)
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

        best.map(|(_, name)| name)
            .unwrap_or_else(|| entity_ids.first().map(|id| id.clone()).unwrap_or_default())
    }
}

/// Result of deduplication operation.
#[derive(Debug, Clone, Default)]
pub struct DeduplicationResult {
    /// Number of duplicate groups found
    pub duplicate_groups_found: usize,
    /// Number of entities merged (removed)
    pub entities_merged: usize,
}

/// Create a knowledge graph from JSON dict.
pub fn entity_from_dict(data: &serde_json::Value) -> Option<Entity> {
    let name = data.get("name")?.as_str()?.to_string();
    let entity_type = parse_entity_type(data.get("entity_type")?.as_str()?);
    let description = data
        .get("description")
        .map(|v| v.as_str().unwrap_or("").to_string())
        .unwrap_or_default();

    let id = format!(
        "{}:{}",
        entity_type.to_string().to_lowercase(),
        name.to_lowercase().replace(" ", "_")
    );

    let entity = Entity::new(id, name, entity_type, description)
        .with_source(
            data.get("source")
                .map(|v| v.as_str().map(|s| s.to_string()))
                .flatten(),
        )
        .with_aliases(
            data.get("aliases")
                .map(|v| {
                    v.as_array()
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|x| x.as_str().map(|s| s.to_string()))
                                .collect()
                        })
                        .unwrap_or_default()
                })
                .unwrap_or_default(),
        )
        .with_confidence(
            data.get("confidence")
                .map(|v| v.as_f64().unwrap_or(1.0) as f32)
                .unwrap_or(1.0),
        );

    Some(entity)
}

/// Create a relation from JSON dict.
pub fn relation_from_dict(data: &serde_json::Value) -> Option<Relation> {
    let source = data.get("source")?.as_str()?.to_string();
    let target = data.get("target")?.as_str()?.to_string();
    let relation_type = parse_relation_type(data.get("relation_type")?.as_str()?);
    let description = data
        .get("description")
        .map(|v| v.as_str().unwrap_or("").to_string())
        .unwrap_or_default();

    let relation = Relation::new(source.clone(), target.clone(), relation_type, description)
        .with_source_doc(
            data.get("source_doc")
                .map(|v| v.as_str().map(|s| s.to_string()))
                .flatten(),
        )
        .with_confidence(
            data.get("confidence")
                .map(|v| v.as_f64().unwrap_or(1.0) as f32)
                .unwrap_or(1.0),
        );

    Some(relation)
}

fn parse_entity_type(s: &str) -> crate::entity::EntityType {
    match s.to_uppercase().as_str() {
        "PERSON" => crate::entity::EntityType::Person,
        "ORGANIZATION" => crate::entity::EntityType::Organization,
        "CONCEPT" => crate::entity::EntityType::Concept,
        "PROJECT" => crate::entity::EntityType::Project,
        "TOOL" => crate::entity::EntityType::Tool,
        "SKILL" => crate::entity::EntityType::Skill,
        "LOCATION" => crate::entity::EntityType::Location,
        "EVENT" => crate::entity::EntityType::Event,
        "DOCUMENT" => crate::entity::EntityType::Document,
        "CODE" => crate::entity::EntityType::Code,
        "API" => crate::entity::EntityType::Api,
        "ERROR" => crate::entity::EntityType::Error,
        "PATTERN" => crate::entity::EntityType::Pattern,
        _ => crate::entity::EntityType::Other(s.to_string()),
    }
}

fn parse_relation_type(s: &str) -> RelationType {
    match s.to_uppercase().as_str() {
        "WORKS_FOR" => RelationType::WorksFor,
        "PART_OF" => RelationType::PartOf,
        "USES" => RelationType::Uses,
        "DEPENDS_ON" => RelationType::DependsOn,
        "SIMILAR_TO" => RelationType::SimilarTo,
        "LOCATED_IN" => RelationType::LocatedIn,
        "CREATED_BY" => RelationType::CreatedBy,
        "DOCUMENTED_IN" => RelationType::DocumentedIn,
        "RELATED_TO" => RelationType::RelatedTo,
        "IMPLEMENTS" => RelationType::Implements,
        "EXTENDS" => RelationType::Extends,
        "CONTAINS" => RelationType::Contains,
        _ => RelationType::Other(s.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::entity::{Entity, EntityType, Relation, RelationType};

    #[test]
    fn test_add_entity() {
        let graph = KnowledgeGraph::new();

        let entity = Entity::new(
            "person:john_doe".to_string(),
            "John Doe".to_string(),
            EntityType::Person,
            "A developer".to_string(),
        );

        assert!(graph.add_entity(entity).is_ok());
        assert_eq!(graph.get_stats().total_entities, 1);
    }

    #[test]
    fn test_add_relation() {
        let graph = KnowledgeGraph::new();

        // Add entities first
        let entity1 = Entity::new(
            "person:john_doe".to_string(),
            "John Doe".to_string(),
            EntityType::Person,
            "A developer".to_string(),
        );
        let entity2 = Entity::new(
            "organization:acme".to_string(),
            "Acme Corp".to_string(),
            EntityType::Organization,
            "A company".to_string(),
        );

        graph.add_entity(entity1).unwrap();
        graph.add_entity(entity2).unwrap();

        // Add relation
        let relation = Relation::new(
            "John Doe".to_string(),
            "Acme Corp".to_string(),
            RelationType::WorksFor,
            "Works at the company".to_string(),
        );

        assert!(graph.add_relation(relation).is_ok());
        assert_eq!(graph.get_stats().total_relations, 1);
    }

    #[test]
    fn test_multi_hop_search() {
        let graph = KnowledgeGraph::new();

        // Create a chain: A -> B -> C -> D
        let entities = vec![
            ("A", EntityType::Concept),
            ("B", EntityType::Concept),
            ("C", EntityType::Concept),
            ("D", EntityType::Concept),
        ];

        for (name, etype) in &entities {
            let entity = Entity::new(
                format!("concept:{}", name),
                name.to_string(),
                etype.clone(),
                format!("Concept {}", name),
            );
            graph.add_entity(entity).unwrap();
        }

        // Create chain
        for i in 0..entities.len() - 1 {
            let relation = Relation::new(
                entities[i].0.to_string(),
                entities[i + 1].0.to_string(),
                RelationType::RelatedTo,
                "Related".to_string(),
            );
            graph.add_relation(relation).unwrap();
        }

        // Search from A with 2 hops should find B and C
        let results = graph.multi_hop_search("A", 2);
        assert!(results.len() >= 2);

        // Search from A with 3 hops should find D too
        let results = graph.multi_hop_search("A", 3);
        assert!(results.len() >= 3);
    }

    #[test]
    fn test_entity_from_dict() {
        let data = json!({
            "name": "Claude Code",
            "entity_type": "TOOL",
            "description": "AI coding assistant",
            "source": "docs/tools.md",
            "aliases": ["claude", "claude-dev"],
            "confidence": 0.95
        });

        let entity = entity_from_dict(&data).unwrap();
        assert_eq!(entity.name, "Claude Code");
        assert!(matches!(entity.entity_type, EntityType::Tool));
        assert_eq!(entity.aliases.len(), 2);
    }

    #[test]
    fn test_save_and_load_graph() {
        use tempfile::TempDir;

        let temp_dir = TempDir::new().unwrap();
        let graph_path = temp_dir.path().join("test_graph.json");

        // Create a graph with entities and relations
        {
            let graph = KnowledgeGraph::new();

            let entity1 = Entity::new(
                "tool:python".to_string(),
                "Python".to_string(),
                EntityType::Skill,
                "Programming language".to_string(),
            );
            let entity2 = Entity::new(
                "tool:claude-code".to_string(),
                "Claude Code".to_string(),
                EntityType::Tool,
                "AI coding assistant".to_string(),
            );

            graph.add_entity(entity1).unwrap();
            graph.add_entity(entity2).unwrap();

            let relation = Relation::new(
                "Claude Code".to_string(),
                "Python".to_string(),
                RelationType::Uses,
                "Claude Code uses Python".to_string(),
            );
            graph.add_relation(relation).unwrap();

            // Save the graph
            graph.save_to_file(graph_path.to_str().unwrap()).unwrap();
        }

        // Load the graph from file
        {
            let mut graph = KnowledgeGraph::new();
            graph.load_from_file(graph_path.to_str().unwrap()).unwrap();

            // Verify entities were loaded
            let stats = graph.get_stats();
            assert_eq!(stats.total_entities, 2);
            assert_eq!(stats.total_relations, 1);

            // Verify entity can be found
            let python = graph.get_entity_by_name("Python");
            assert!(python.is_some());
            assert_eq!(python.unwrap().entity_type, EntityType::Skill);

            // Verify relation was loaded
            let relations = graph.get_relations(None, None);
            assert_eq!(relations.len(), 1);
            assert_eq!(relations[0].source, "Claude Code");
        }
    }

    #[test]
    fn test_export_as_json() {
        let graph = KnowledgeGraph::new();

        let entity = Entity::new(
            "project:omni".to_string(),
            "Omni Dev Fusion".to_string(),
            EntityType::Project,
            "Development environment".to_string(),
        );

        graph.add_entity(entity).unwrap();

        let json = graph.export_as_json().unwrap();
        assert!(json.contains("Omni Dev Fusion"));
        assert!(json.contains("entities"));
        assert!(json.contains("relations"));
    }

    #[test]
    fn test_export_import_roundtrip() {
        use tempfile::TempDir;

        let temp_dir = TempDir::new().unwrap();
        let graph_path = temp_dir.path().join("roundtrip.json");

        // Create graph with various entity types
        let graph1 = KnowledgeGraph::new();

        let entities = vec![
            ("Python", EntityType::Skill),
            ("Rust", EntityType::Skill),
            ("Claude Code", EntityType::Tool),
            ("Omni Dev Fusion", EntityType::Project),
        ];

        for (name, etype) in &entities {
            let entity = Entity::new(
                format!(
                    "{}:{}",
                    etype.to_string().to_lowercase(),
                    name.to_lowercase().replace(" ", "_")
                ),
                name.to_string(),
                etype.clone(),
                format!("Description of {}", name),
            );
            graph1.add_entity(entity).unwrap();
        }

        // Add relations
        let relations = vec![
            ("Claude Code", "Python", RelationType::Uses),
            ("Claude Code", "Rust", RelationType::Uses),
            ("Omni Dev Fusion", "Claude Code", RelationType::CreatedBy),
        ];

        for (source, target, rtype) in &relations {
            let relation = Relation::new(
                source.to_string(),
                target.to_string(),
                rtype.clone(),
                format!("{} -> {}", source, target),
            );
            graph1.add_relation(relation).unwrap();
        }

        // Export and save
        graph1.save_to_file(graph_path.to_str().unwrap()).unwrap();

        // Load into new graph
        let mut graph2 = KnowledgeGraph::new();
        graph2.load_from_file(graph_path.to_str().unwrap()).unwrap();

        // Verify stats match
        let stats1 = graph1.get_stats();
        let stats2 = graph2.get_stats();
        assert_eq!(stats1.total_entities, stats2.total_entities);
        assert_eq!(stats1.total_relations, stats2.total_relations);
    }
}
