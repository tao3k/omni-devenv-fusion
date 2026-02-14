//! JSON persistence: save, load, export, and dict-based parsing.

use super::{GraphError, KnowledgeGraph};
use crate::entity::{Entity, EntityType, Relation, RelationType};
use log::info;
use serde_json::{Value, json, to_string};
use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::PathBuf;

impl KnowledgeGraph {
    /// Save graph to a JSON file.
    pub fn save_to_file(&self, path: &str) -> Result<(), GraphError> {
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

        self.clear();

        if let Some(entities_arr) = value.get("entities").and_then(|v| v.as_array()) {
            for entity_val in entities_arr {
                if let Some(entity) = entity_from_dict(entity_val) {
                    self.add_entity(entity).ok();
                }
            }
        }

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
}

// ---------------------------------------------------------------------------
// Dict-based entity/relation parsing (used by load_from_file and Python)
// ---------------------------------------------------------------------------

/// Create an Entity from a JSON dict.
pub fn entity_from_dict(data: &Value) -> Option<Entity> {
    let name = data.get("name")?.as_str()?.to_string();
    let entity_type = parse_entity_type_str(data.get("entity_type")?.as_str()?);
    let description = data
        .get("description")
        .map(|v| v.as_str().unwrap_or("").to_string())
        .unwrap_or_default();

    let id = format!(
        "{}:{}",
        entity_type.to_string().to_lowercase(),
        name.to_lowercase().replace(' ', "_")
    );

    let entity = Entity::new(id, name, entity_type, description)
        .with_source(
            data.get("source")
                .and_then(|v| v.as_str().map(|s| s.to_string())),
        )
        .with_aliases(
            data.get("aliases")
                .and_then(|v| {
                    v.as_array().map(|arr| {
                        arr.iter()
                            .filter_map(|x| x.as_str().map(|s| s.to_string()))
                            .collect()
                    })
                })
                .unwrap_or_default(),
        )
        .with_confidence(
            data.get("confidence")
                .and_then(|v| v.as_f64())
                .unwrap_or(1.0) as f32,
        );

    Some(entity)
}

/// Create a Relation from a JSON dict.
pub fn relation_from_dict(data: &Value) -> Option<Relation> {
    let source = data.get("source")?.as_str()?.to_string();
    let target = data.get("target")?.as_str()?.to_string();
    let relation_type = parse_relation_type_str(data.get("relation_type")?.as_str()?);
    let description = data
        .get("description")
        .map(|v| v.as_str().unwrap_or("").to_string())
        .unwrap_or_default();

    let relation = Relation::new(source, target, relation_type, description)
        .with_source_doc(
            data.get("source_doc")
                .and_then(|v| v.as_str().map(|s| s.to_string())),
        )
        .with_confidence(
            data.get("confidence")
                .and_then(|v| v.as_f64())
                .unwrap_or(1.0) as f32,
        );

    Some(relation)
}

// ---------------------------------------------------------------------------
// Type parsers
// ---------------------------------------------------------------------------

pub(crate) fn parse_entity_type_str(s: &str) -> EntityType {
    match s.to_uppercase().as_str() {
        "PERSON" => EntityType::Person,
        "ORGANIZATION" => EntityType::Organization,
        "CONCEPT" => EntityType::Concept,
        "PROJECT" => EntityType::Project,
        "TOOL" => EntityType::Tool,
        "SKILL" => EntityType::Skill,
        "LOCATION" => EntityType::Location,
        "EVENT" => EntityType::Event,
        "DOCUMENT" => EntityType::Document,
        "CODE" => EntityType::Code,
        "API" => EntityType::Api,
        "ERROR" => EntityType::Error,
        "PATTERN" => EntityType::Pattern,
        _ => EntityType::Other(s.to_string()),
    }
}

pub(crate) fn parse_relation_type_str(s: &str) -> RelationType {
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
