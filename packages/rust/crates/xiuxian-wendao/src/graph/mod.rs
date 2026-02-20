//! Knowledge graph storage and operations.
//!
//! Modular design:
//! - `mod.rs`: Core `KnowledgeGraph` struct, CRUD, basic accessors
//! - `query.rs`: Search and multi-hop traversal algorithms
//! - `intent.rs`: Lightweight query intent extractor (action/target/context)
//! - `persistence.rs`: JSON save/load, entity/relation parsing
//! - `lance_persistence.rs`: Arrow/Lance save/load (columnar, vector-ready)
//! - `dedup.rs`: Entity deduplication and normalization
//! - `skill_registry.rs`: Bulk skill entity registration (Bridge 4)

mod dedup;
mod intent;
pub(crate) mod lance_persistence;
mod persistence;
mod query;
mod skill_registry;

use crate::entity::{Entity, GraphStats, Relation, RelationType};
use log::info;
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, PoisonError, RwLock, RwLockReadGuard, RwLockWriteGuard};
use thiserror::Error;

// Re-export sub-module public items
pub use dedup::DeduplicationResult;
pub use intent::{QueryIntent, extract_intent};
pub use persistence::{entity_from_dict, relation_from_dict};
pub use skill_registry::{SkillDoc, SkillRegistrationResult};

pub(super) fn read_lock<T>(lock: &RwLock<T>) -> RwLockReadGuard<'_, T> {
    lock.read().unwrap_or_else(PoisonError::into_inner)
}

pub(super) fn write_lock<T>(lock: &RwLock<T>) -> RwLockWriteGuard<'_, T> {
    lock.write().unwrap_or_else(PoisonError::into_inner)
}

fn saturating_usize_to_i64(value: usize) -> i64 {
    i64::try_from(value).unwrap_or(i64::MAX)
}

/// Graph errors.
#[derive(Debug, Error)]
pub enum GraphError {
    /// The requested entity was not found.
    #[error("Entity not found: {0}")]
    EntityNotFound(String),
    /// A relation with this ID already exists.
    #[error("Relation already exists: {0}")]
    RelationExists(String),
    /// The relation references invalid source/target entities.
    #[error("Invalid relation: source={0}, target={1}")]
    InvalidRelation(String, String),
}

/// Knowledge graph storage.
#[derive(Debug, Clone)]
pub struct KnowledgeGraph {
    /// Entities by ID
    pub(crate) entities: Arc<RwLock<HashMap<String, Entity>>>,
    /// Entities by name (for quick lookup)
    pub(crate) entities_by_name: Arc<RwLock<HashMap<String, String>>>,
    /// Relations by ID
    pub(crate) relations: Arc<RwLock<HashMap<String, Relation>>>,
    /// Outgoing relations (entity name -> set of relation IDs)
    pub(crate) outgoing_relations: Arc<RwLock<HashMap<String, HashSet<String>>>>,
    /// Incoming relations (entity name -> set of relation IDs)
    pub(crate) incoming_relations: Arc<RwLock<HashMap<String, HashSet<String>>>>,
    /// Entities by type
    pub(crate) entities_by_type: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

impl Default for KnowledgeGraph {
    fn default() -> Self {
        Self::new()
    }
}

impl KnowledgeGraph {
    /// Create a new knowledge graph.
    #[must_use]
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
    ///
    /// Returns `true` if newly added, `false` if updated in place.
    ///
    /// # Errors
    ///
    /// This currently never returns an error and is modeled as `Result` for API compatibility.
    #[allow(clippy::unnecessary_wraps)]
    pub fn add_entity(&self, entity: Entity) -> Result<bool, GraphError> {
        let mut entities = write_lock(&self.entities);
        let mut entities_by_name = write_lock(&self.entities_by_name);
        let mut entities_by_type = write_lock(&self.entities_by_type);

        let type_str = entity.entity_type.to_string();
        if let Some(existing_id) = entities_by_name.get(&entity.name)
            && let Some(existing) = entities.get_mut(existing_id)
        {
            existing.description = entity.description;
            existing.source = entity.source.or(existing.source.clone());
            existing.aliases = entity.aliases;
            existing.confidence = entity.confidence;
            existing.updated_at = entity.updated_at;
            info!("Updated entity: {}", entity.name);
            return Ok(false);
        }

        let entity_id = entity.id.clone();
        entities.insert(entity_id.clone(), entity.clone());
        entities_by_name.insert(entity.name.clone(), entity_id.clone());

        entities_by_type
            .entry(type_str)
            .or_default()
            .push(entity_id.clone());

        info!("Added entity: {} ({})", entity.name, entity.entity_type);
        Ok(true)
    }

    /// Add a relation.
    ///
    /// # Errors
    ///
    /// Returns [`GraphError::InvalidRelation`] if source/target entities do not exist.
    #[allow(clippy::needless_pass_by_value)]
    pub fn add_relation(&self, relation: Relation) -> Result<(), GraphError> {
        let mut relations = write_lock(&self.relations);
        let mut outgoing = write_lock(&self.outgoing_relations);
        let mut incoming = write_lock(&self.incoming_relations);

        if relations.contains_key(&relation.id) {
            info!("Relation already exists: {}", relation.id);
            return Ok(());
        }

        {
            let entities_by_name = read_lock(&self.entities_by_name);
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

        let relation_id = relation.id.clone();
        relations.insert(relation_id.clone(), relation.clone());

        outgoing
            .entry(relation.source.clone())
            .or_default()
            .insert(relation_id.clone());

        incoming
            .entry(relation.target.clone())
            .or_default()
            .insert(relation_id.clone());

        info!(
            "Added relation: {} -> {} ({})",
            relation.source, relation.target, relation.relation_type
        );
        Ok(())
    }

    /// Get an entity by ID.
    #[must_use]
    pub fn get_entity(&self, entity_id: &str) -> Option<Entity> {
        read_lock(&self.entities).get(entity_id).cloned()
    }

    /// Get an entity by name.
    #[must_use]
    pub fn get_entity_by_name(&self, name: &str) -> Option<Entity> {
        let entities_by_name = read_lock(&self.entities_by_name);
        if let Some(entity_id) = entities_by_name.get(name) {
            return read_lock(&self.entities).get(entity_id).cloned();
        }
        None
    }

    /// Get entities by type.
    #[must_use]
    pub fn get_entities_by_type(&self, entity_type: &str) -> Vec<Entity> {
        let entities_by_type = read_lock(&self.entities_by_type);
        let entities = read_lock(&self.entities);

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
    #[must_use]
    pub fn get_relations(
        &self,
        entity_name: Option<&str>,
        relation_type: Option<RelationType>,
    ) -> Vec<Relation> {
        let relations = read_lock(&self.relations);
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

    /// Get graph statistics.
    #[must_use]
    pub fn get_stats(&self) -> GraphStats {
        let entities = read_lock(&self.entities);
        let relations = read_lock(&self.relations);
        let entities_by_type = read_lock(&self.entities_by_type);

        let mut entities_by_type_count: HashMap<String, i64> = HashMap::new();
        for (etype, eids) in entities_by_type.iter() {
            entities_by_type_count.insert(etype.clone(), saturating_usize_to_i64(eids.len()));
        }

        let mut relations_by_type: HashMap<String, i64> = HashMap::new();
        for rel in relations.values() {
            let rtype = rel.relation_type.to_string();
            *relations_by_type.entry(rtype).or_insert(0) += 1;
        }

        GraphStats {
            total_entities: saturating_usize_to_i64(entities.len()),
            total_relations: saturating_usize_to_i64(relations.len()),
            entities_by_type: entities_by_type_count,
            relations_by_type,
            last_updated: None,
        }
    }

    /// Clear all entities and relations.
    pub fn clear(&mut self) {
        write_lock(&self.entities).clear();
        write_lock(&self.entities_by_name).clear();
        write_lock(&self.relations).clear();
        write_lock(&self.outgoing_relations).clear();
        write_lock(&self.incoming_relations).clear();
        write_lock(&self.entities_by_type).clear();
        info!("Knowledge graph cleared");
    }

    /// Get all entities as a vector.
    #[must_use]
    pub fn get_all_entities(&self) -> Vec<Entity> {
        read_lock(&self.entities).values().cloned().collect()
    }

    /// Get all relations as a vector.
    #[must_use]
    pub fn get_all_relations(&self) -> Vec<Relation> {
        read_lock(&self.relations).values().cloned().collect()
    }

    /// Remove an entity by ID.
    ///
    /// # Errors
    ///
    /// Returns [`GraphError::EntityNotFound`] if the entity ID is absent.
    pub fn remove_entity(&self, entity_id: &str) -> Result<(), GraphError> {
        let mut entities = write_lock(&self.entities);
        let mut entities_by_name = write_lock(&self.entities_by_name);
        let mut entities_by_type = write_lock(&self.entities_by_type);
        let mut relations = write_lock(&self.relations);
        let mut outgoing = write_lock(&self.outgoing_relations);
        let mut incoming = write_lock(&self.incoming_relations);

        if let Some(entity) = entities.remove(entity_id) {
            entities_by_name.remove(&entity.name);

            if let Some(ids) = entities_by_type.get_mut(&entity.entity_type.to_string()) {
                ids.retain(|id| id != entity_id);
            }

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
}
