//! Arrow/Lance persistence for `KnowledgeGraph` entities and relations.
//!
//! Stores entities and relations as Lance tables (Arrow-native) alongside
//! the existing `knowledge.lance` database. This enables:
//! - Columnar filtering (`entity_type`, confidence thresholds)
//! - Vector ANN search over entity embeddings (`Entity.vector` field)
//! - Incremental `merge_insert` (no full-JSON rewrite)
//! - Unified storage with knowledge chunks in the same Lance DB
//!
//! Tables:
//! - `kg_entities`: `id`, `name`, `entity_type`, `description`, `source`, `aliases`,
//!   `confidence`, `vector`, `metadata`
//! - `kg_relations`: `id`, `source`, `target`, `relation_type`, `description`,
//!   `source_doc`, `confidence`, `metadata`

use super::{GraphError, KnowledgeGraph, read_lock};
use crate::entity::{Entity, Relation};
use futures::TryStreamExt;
use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{
    Array, FixedSizeListArray, Float32Array, RecordBatch, RecordBatchIterator, StringArray,
};
use lance::deps::arrow_schema::{ArrowError, DataType, Field, Schema};
use log::info;
use std::path::Path;
use std::sync::Arc;

/// Entity table name inside the knowledge Lance DB.
pub const ENTITY_TABLE: &str = "kg_entities";
/// Relation table name inside the knowledge Lance DB.
pub const RELATION_TABLE: &str = "kg_relations";
/// Default embedding dimension for entity vectors.
pub const DEFAULT_ENTITY_DIMENSION: usize = 1024;
const DEFAULT_ENTITY_DIMENSION_I32: i32 = 1024;

// ---------------------------------------------------------------------------
// Arrow Schema Builders
// ---------------------------------------------------------------------------

/// Build the Arrow schema for the `kg_entities` table.
fn entity_schema(dimension: usize) -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        Field::new("id", DataType::Utf8, false),
        Field::new("name", DataType::Utf8, false),
        Field::new("entity_type", DataType::Utf8, false),
        Field::new("description", DataType::Utf8, true),
        Field::new("source", DataType::Utf8, true),
        Field::new("aliases", DataType::Utf8, true), // JSON array as string
        Field::new("confidence", DataType::Float32, false),
        Field::new(
            "vector",
            DataType::FixedSizeList(
                Arc::new(Field::new("item", DataType::Float32, true)),
                i32::try_from(dimension).unwrap_or(DEFAULT_ENTITY_DIMENSION_I32),
            ),
            true, // nullable: entities without embeddings
        ),
        Field::new("metadata", DataType::Utf8, true), // JSON object as string
        Field::new("created_at", DataType::Utf8, true),
        Field::new("updated_at", DataType::Utf8, true),
    ]))
}

/// Build the Arrow schema for the `kg_relations` table.
fn relation_schema() -> Arc<Schema> {
    Arc::new(Schema::new(vec![
        Field::new("id", DataType::Utf8, false),
        Field::new("source", DataType::Utf8, false),
        Field::new("target", DataType::Utf8, false),
        Field::new("relation_type", DataType::Utf8, false),
        Field::new("description", DataType::Utf8, true),
        Field::new("source_doc", DataType::Utf8, true),
        Field::new("confidence", DataType::Float32, false),
        Field::new("metadata", DataType::Utf8, true), // JSON object as string
    ]))
}

// ---------------------------------------------------------------------------
// Entity → RecordBatch conversion
// ---------------------------------------------------------------------------

fn entities_to_batch(entities: &[&Entity], dimension: usize) -> Result<RecordBatch, ArrowError> {
    let schema = entity_schema(dimension);

    let ids: Vec<&str> = entities.iter().map(|e| e.id.as_str()).collect();
    let names: Vec<&str> = entities.iter().map(|e| e.name.as_str()).collect();
    let types: Vec<String> = entities.iter().map(|e| e.entity_type.to_string()).collect();
    let type_refs: Vec<&str> = types.iter().map(String::as_str).collect();
    let descs: Vec<&str> = entities.iter().map(|e| e.description.as_str()).collect();
    let sources: Vec<Option<&str>> = entities.iter().map(|e| e.source.as_deref()).collect();
    let aliases_json: Vec<String> = entities
        .iter()
        .map(|e| serde_json::to_string(&e.aliases).unwrap_or_else(|_| "[]".to_string()))
        .collect();
    let alias_refs: Vec<&str> = aliases_json.iter().map(String::as_str).collect();
    let confidences: Vec<f32> = entities.iter().map(|e| e.confidence).collect();
    let metadata_json: Vec<String> = entities
        .iter()
        .map(|e| serde_json::to_string(&e.metadata).unwrap_or_else(|_| "{}".to_string()))
        .collect();
    let meta_refs: Vec<&str> = metadata_json.iter().map(String::as_str).collect();
    let created: Vec<String> = entities.iter().map(|e| e.created_at.to_rfc3339()).collect();
    let created_refs: Vec<&str> = created.iter().map(String::as_str).collect();
    let updated: Vec<String> = entities.iter().map(|e| e.updated_at.to_rfc3339()).collect();
    let updated_refs: Vec<&str> = updated.iter().map(String::as_str).collect();

    // Build vector column (FixedSizeList<Float32>)
    // Entities without embeddings get zero vectors (same pattern as checkpoint store).
    let dim_i32 = i32::try_from(dimension).unwrap_or_else(|_| {
        i32::try_from(DEFAULT_ENTITY_DIMENSION).unwrap_or(DEFAULT_ENTITY_DIMENSION_I32)
    });
    let flat_values: Vec<f32> = entities
        .iter()
        .flat_map(|e| match &e.vector {
            Some(v) if v.len() == dimension => v.clone(),
            Some(v) => {
                let mut padded = vec![0.0f32; dimension];
                let copy_len = v.len().min(dimension);
                padded[..copy_len].copy_from_slice(&v[..copy_len]);
                padded
            }
            None => vec![0.0f32; dimension],
        })
        .collect();
    let vector_array = FixedSizeListArray::try_new(
        Arc::new(Field::new("item", DataType::Float32, true)),
        dim_i32,
        Arc::new(Float32Array::from(flat_values)),
        None, // non-null; zero-vector signals "no embedding"
    )?;

    RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(ids)) as _,
            Arc::new(StringArray::from(names)) as _,
            Arc::new(StringArray::from(type_refs)) as _,
            Arc::new(StringArray::from(descs)) as _,
            Arc::new(StringArray::from(sources)) as _,
            Arc::new(StringArray::from(alias_refs)) as _,
            Arc::new(Float32Array::from(confidences)) as _,
            Arc::new(vector_array) as _,
            Arc::new(StringArray::from(meta_refs)) as _,
            Arc::new(StringArray::from(created_refs)) as _,
            Arc::new(StringArray::from(updated_refs)) as _,
        ],
    )
}

// ---------------------------------------------------------------------------
// Relation → RecordBatch conversion
// ---------------------------------------------------------------------------

fn relations_to_batch(relations: &[&Relation]) -> Result<RecordBatch, ArrowError> {
    let schema = relation_schema();

    let ids: Vec<&str> = relations.iter().map(|r| r.id.as_str()).collect();
    let sources: Vec<&str> = relations.iter().map(|r| r.source.as_str()).collect();
    let targets: Vec<&str> = relations.iter().map(|r| r.target.as_str()).collect();
    let types: Vec<String> = relations
        .iter()
        .map(|r| r.relation_type.to_string())
        .collect();
    let type_refs: Vec<&str> = types.iter().map(String::as_str).collect();
    let descs: Vec<&str> = relations.iter().map(|r| r.description.as_str()).collect();
    let source_docs: Vec<Option<&str>> =
        relations.iter().map(|r| r.source_doc.as_deref()).collect();
    let confidences: Vec<f32> = relations.iter().map(|r| r.confidence).collect();
    let metadata_json: Vec<String> = relations
        .iter()
        .map(|r| serde_json::to_string(&r.metadata).unwrap_or_else(|_| "{}".to_string()))
        .collect();
    let meta_refs: Vec<&str> = metadata_json.iter().map(String::as_str).collect();

    RecordBatch::try_new(
        schema,
        vec![
            Arc::new(StringArray::from(ids)) as _,
            Arc::new(StringArray::from(sources)) as _,
            Arc::new(StringArray::from(targets)) as _,
            Arc::new(StringArray::from(type_refs)) as _,
            Arc::new(StringArray::from(descs)) as _,
            Arc::new(StringArray::from(source_docs)) as _,
            Arc::new(Float32Array::from(confidences)) as _,
            Arc::new(StringArray::from(meta_refs)) as _,
        ],
    )
}

// ---------------------------------------------------------------------------
// RecordBatch → Entity / Relation reconstruction
// ---------------------------------------------------------------------------

fn batch_to_entities(batch: &RecordBatch) -> Vec<Entity> {
    let n = batch.num_rows();
    let Some(ids) = batch.column(0).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(names) = batch.column(1).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(types) = batch.column(2).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(descs) = batch.column(3).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(sources) = batch.column(4).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(aliases_col) = batch.column(5).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(confs) = batch.column(6).as_any().downcast_ref::<Float32Array>() else {
        return Vec::new();
    };
    let Some(vector_col) = batch
        .column(7)
        .as_any()
        .downcast_ref::<FixedSizeListArray>()
    else {
        return Vec::new();
    };
    let Some(meta_col) = batch.column(8).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(created_col) = batch.column(9).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(updated_col) = batch.column(10).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };

    let mut entities = Vec::with_capacity(n);
    for i in 0..n {
        let entity_type = super::persistence::parse_entity_type_str(types.value(i));
        let aliases: Vec<String> = serde_json::from_str(aliases_col.value(i)).unwrap_or_default();
        let metadata: std::collections::HashMap<String, serde_json::Value> =
            serde_json::from_str(meta_col.value(i)).unwrap_or_default();

        // Extract vector if not null
        let vector = if vector_col.is_valid(i) {
            let inner = vector_col.value(i);
            if let Some(float_arr) = inner.as_any().downcast_ref::<Float32Array>() {
                let vals: Vec<f32> = float_arr.values().to_vec();
                if vals.iter().any(|v| *v != 0.0) {
                    Some(vals)
                } else {
                    None
                }
            } else {
                None
            }
        } else {
            None
        };

        let created_at = chrono::DateTime::parse_from_rfc3339(created_col.value(i))
            .map_or_else(|_| chrono::Utc::now(), |dt| dt.with_timezone(&chrono::Utc));
        let updated_at = chrono::DateTime::parse_from_rfc3339(updated_col.value(i))
            .map_or_else(|_| chrono::Utc::now(), |dt| dt.with_timezone(&chrono::Utc));

        let mut entity = Entity::new(
            ids.value(i).to_string(),
            names.value(i).to_string(),
            entity_type,
            descs.value(i).to_string(),
        )
        .with_aliases(aliases)
        .with_confidence(confs.value(i));

        if sources.is_valid(i) && !sources.value(i).is_empty() {
            entity = entity.with_source(Some(sources.value(i).to_string()));
        }
        entity.vector = vector;
        entity.metadata = metadata;
        entity.created_at = created_at;
        entity.updated_at = updated_at;

        entities.push(entity);
    }
    entities
}

fn batch_to_relations(batch: &RecordBatch) -> Vec<Relation> {
    let n = batch.num_rows();
    let Some(ids) = batch.column(0).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(sources) = batch.column(1).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(targets) = batch.column(2).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(types) = batch.column(3).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(descs) = batch.column(4).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(source_docs) = batch.column(5).as_any().downcast_ref::<StringArray>() else {
        return Vec::new();
    };
    let Some(confs) = batch.column(6).as_any().downcast_ref::<Float32Array>() else {
        return Vec::new();
    };

    let mut relations = Vec::with_capacity(n);
    for i in 0..n {
        let rel_type = super::persistence::parse_relation_type_str(types.value(i));
        let mut rel = Relation::new(
            sources.value(i).to_string(),
            targets.value(i).to_string(),
            rel_type,
            descs.value(i).to_string(),
        )
        .with_confidence(confs.value(i));

        if source_docs.is_valid(i) && !source_docs.value(i).is_empty() {
            rel = rel.with_source_doc(Some(source_docs.value(i).to_string()));
        }
        // Override auto-generated ID with stored ID
        rel.id = ids.value(i).to_string();

        relations.push(rel);
    }
    relations
}

// ---------------------------------------------------------------------------
// KnowledgeGraph Lance save / load
// ---------------------------------------------------------------------------

impl KnowledgeGraph {
    /// Save the graph to Lance tables inside the given directory.
    ///
    /// Creates or overwrites `kg_entities` and `kg_relations` tables.
    /// The `lance_dir` should be the knowledge.lance DB path.
    ///
    /// # Errors
    ///
    /// Returns [`GraphError::InvalidRelation`] when directory creation, Arrow conversion,
    /// or Lance write operations fail.
    pub async fn save_to_lance(&self, lance_dir: &str, dimension: usize) -> Result<(), GraphError> {
        let base = Path::new(lance_dir);
        std::fs::create_dir_all(base)
            .map_err(|e| GraphError::InvalidRelation(lance_dir.to_string(), e.to_string()))?;

        // -- Entities --
        let entity_batch = {
            let entities_guard = read_lock(&self.entities);
            let entity_refs: Vec<&Entity> = entities_guard.values().collect();
            entities_to_batch(&entity_refs, dimension)
                .map_err(|e| GraphError::InvalidRelation("entity_batch".into(), e.to_string()))?
        };

        let entity_uri = base.join(ENTITY_TABLE).to_string_lossy().into_owned();
        // Remove old table if present
        if Path::new(&entity_uri).exists() {
            let _ = std::fs::remove_dir_all(&entity_uri);
        }
        let e_schema = entity_schema(dimension);
        let e_batches: Vec<Result<RecordBatch, ArrowError>> = vec![Ok(entity_batch)];
        let e_iter = RecordBatchIterator::new(e_batches, e_schema);
        Dataset::write(Box::new(e_iter), &entity_uri, Some(WriteParams::default()))
            .await
            .map_err(|e| GraphError::InvalidRelation("entity_write".into(), e.to_string()))?;

        // -- Relations --
        let relation_batch = {
            let relations_guard = read_lock(&self.relations);
            let relation_refs: Vec<&Relation> = relations_guard.values().collect();
            relations_to_batch(&relation_refs)
                .map_err(|e| GraphError::InvalidRelation("relation_batch".into(), e.to_string()))?
        };

        let relation_uri = base.join(RELATION_TABLE).to_string_lossy().into_owned();
        if Path::new(&relation_uri).exists() {
            let _ = std::fs::remove_dir_all(&relation_uri);
        }
        let r_schema = relation_schema();
        let r_batches: Vec<Result<RecordBatch, ArrowError>> = vec![Ok(relation_batch)];
        let r_iter = RecordBatchIterator::new(r_batches, r_schema);
        Dataset::write(
            Box::new(r_iter),
            &relation_uri,
            Some(WriteParams::default()),
        )
        .await
        .map_err(|e| GraphError::InvalidRelation("relation_write".into(), e.to_string()))?;

        let stats = self.get_stats();
        info!(
            "Knowledge graph saved to Lance: {} ({} entities, {} relations)",
            lance_dir, stats.total_entities, stats.total_relations
        );

        Ok(())
    }

    /// Load the graph from Lance tables inside the given directory.
    ///
    /// Reads `kg_entities` and `kg_relations` tables. Replaces current
    /// in-memory graph contents. Falls back gracefully if tables don't exist.
    ///
    /// # Errors
    ///
    /// Returns [`GraphError::InvalidRelation`] if Lance table open/scan/collect fails.
    pub async fn load_from_lance(&mut self, lance_dir: &str) -> Result<(), GraphError> {
        let base = Path::new(lance_dir);
        self.clear();

        // -- Entities --
        let entity_uri = base.join(ENTITY_TABLE).to_string_lossy().into_owned();
        if Path::new(&entity_uri).exists() {
            let dataset = Dataset::open(&entity_uri)
                .await
                .map_err(|e| GraphError::InvalidRelation("entity_open".into(), e.to_string()))?;

            let scanner = dataset.scan();
            let batches = scanner
                .try_into_stream()
                .await
                .map_err(|e| GraphError::InvalidRelation("entity_scan".into(), e.to_string()))?;

            let record_batches: Vec<RecordBatch> = batches
                .try_collect()
                .await
                .map_err(|e| GraphError::InvalidRelation("entity_collect".into(), e.to_string()))?;

            for batch in &record_batches {
                let entities = batch_to_entities(batch);
                for entity in entities {
                    self.add_entity(entity).ok();
                }
            }
        }

        // -- Relations --
        let relation_uri = base.join(RELATION_TABLE).to_string_lossy().into_owned();
        if Path::new(&relation_uri).exists() {
            let dataset = Dataset::open(&relation_uri)
                .await
                .map_err(|e| GraphError::InvalidRelation("relation_open".into(), e.to_string()))?;

            let scanner = dataset.scan();
            let batches = scanner
                .try_into_stream()
                .await
                .map_err(|e| GraphError::InvalidRelation("relation_scan".into(), e.to_string()))?;

            let record_batches: Vec<RecordBatch> = batches.try_collect().await.map_err(|e| {
                GraphError::InvalidRelation("relation_collect".into(), e.to_string())
            })?;

            for batch in &record_batches {
                let relations = batch_to_relations(batch);
                for relation in relations {
                    self.add_relation(relation).ok();
                }
            }
        }

        let stats = self.get_stats();
        info!(
            "Knowledge graph loaded from Lance: {} ({} entities, {} relations)",
            lance_dir, stats.total_entities, stats.total_relations
        );

        Ok(())
    }
}
