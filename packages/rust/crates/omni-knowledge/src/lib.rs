//! omni-knowledge - High-performance knowledge management library.
//!
//! This crate provides:
//! - KnowledgeEntry type definition
//! - KnowledgeCategory enumeration
//! - Entity and Relation types for knowledge graph
//! - Knowledge graph storage and operations
//! - LanceDB storage operations
//! - Sync engine for incremental updates
//! - PyO3 bindings for Python
//!
//! # Examples
//!
//! ```rust
//! use omni_knowledge::{KnowledgeEntry, KnowledgeCategory};
//!
//! let entry = KnowledgeEntry::new(
//!     "test-001".to_string(),
//!     "Error Handling Pattern".to_string(),
//!     "Best practices for error handling...".to_string(),
//!     KnowledgeCategory::Pattern,
//! ).with_tags(vec!["error".to_string(), "exception".to_string()]);
//! ```
//!
//! # Knowledge Graph Examples
//!
//! ```rust
//! use omni_knowledge::{Entity, Relation, EntityType, RelationType, KnowledgeGraph};
//!
//! let graph = KnowledgeGraph::new();
//!
//! let entity = Entity::new(
//!     "tool:claude-code".to_string(),
//!     "Claude Code".to_string(),
//!     EntityType::Tool,
//!     "AI coding assistant".to_string(),
//! );
//!
//! graph.add_entity(entity).unwrap();
//! ```
use pyo3::prelude::*;
use serde_json::{Value, json, to_string};
use std::collections::HashMap;

pub mod dep_indexer_py;
pub mod dependency_indexer; // Public so dep_indexer_py can access
mod entity;
mod graph;
mod storage;
mod sync;
mod types;
pub mod unified_symbol;
pub mod unified_symbol_py;
pub mod zk;
mod zk_py; // Public for Python bindings

pub use entity::{
    Entity, EntitySearchQuery, EntityType, GraphStats, MultiHopOptions, Relation, RelationType,
};
pub use graph::KnowledgeGraph;
pub use storage::KnowledgeStorage;
pub use sync::{DiscoveryOptions, FileChange, SyncEngine, SyncManifest, SyncResult};
pub use types::{KnowledgeCategory, KnowledgeEntry, KnowledgeSearchQuery, KnowledgeStats};
pub use zk::{
    ZkEntityRef, ZkRefStats, extract_entity_refs, find_notes_referencing_entity, get_ref_stats,
};
pub use zk_py::{
    PyZkEntityRef, PyZkRefStats, zk_count_refs, zk_extract_entity_refs, zk_find_referencing_notes,
    zk_get_ref_stats, zk_is_valid_ref, zk_parse_entity_ref,
};

// Dependency Indexer exports
pub use dep_indexer_py::{
    PyDependencyConfig, PyDependencyIndexResult, PyDependencyIndexer, PyDependencyStats,
    PyExternalDependency, PyExternalSymbol, PySymbolIndex,
};
pub use dependency_indexer::{
    ConfigExternalDependency, DependencyBuildConfig, DependencyConfig, DependencyIndexResult,
    DependencyIndexer, DependencyStats, ExternalSymbol, SymbolIndex, SymbolKind,
};
pub use unified_symbol::{SymbolSource, UnifiedIndexStats, UnifiedSymbol, UnifiedSymbolIndex};
pub use unified_symbol_py::{PyUnifiedIndexStats, PyUnifiedSymbol, PyUnifiedSymbolIndex};

/// Python module definition
#[pymodule]
fn _omni_knowledge(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    // Register types
    m.add_class::<PyKnowledgeCategory>()?;
    m.add_class::<PyKnowledgeEntry>()?;
    m.add_class::<PyKnowledgeStorage>()?;
    m.add_class::<PySyncEngine>()?;
    m.add_class::<PySyncResult>()?;

    // Register knowledge graph types
    m.add_class::<PyEntity>()?;
    m.add_class::<PyRelation>()?;
    m.add_class::<PyKnowledgeGraph>()?;

    // Register zk types (from zk_py module)
    m.add_class::<PyZkEntityRef>()?;
    m.add_class::<PyZkRefStats>()?;

    // Register functions
    m.add_function(wrap_pyfunction!(create_knowledge_entry, _py)?)?;
    m.add_function(wrap_pyfunction!(compute_hash, _py)?)?;

    // Register zk functions (from zk_py module)
    m.add_function(wrap_pyfunction!(zk_extract_entity_refs, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_get_ref_stats, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_parse_entity_ref, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_is_valid_ref, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_count_refs, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_find_referencing_notes, _py)?)?;

    // Register unified symbol index types (from unified_symbol_py module)
    use unified_symbol_py::register_unified_symbol_module;
    register_unified_symbol_module(m)?;

    Ok(())
}

/// Knowledge category Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeCategory {
    inner: KnowledgeCategory,
}

#[pymethods]
impl PyKnowledgeCategory {
    #[classattr]
    const PATTERN: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Pattern,
    };

    #[classattr]
    const SOLUTION: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Solution,
    };

    #[classattr]
    const ERROR: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Error,
    };

    #[classattr]
    const TECHNIQUE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Technique,
    };

    #[classattr]
    const NOTE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Note,
    };

    #[classattr]
    const REFERENCE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Reference,
    };

    #[classattr]
    const ARCHITECTURE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Architecture,
    };

    #[classattr]
    const WORKFLOW: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Workflow,
    };

    #[new]
    fn new(category: &str) -> PyResult<Self> {
        match category {
            "patterns" | "pattern" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Pattern,
            }),
            "solutions" | "solution" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Solution,
            }),
            "errors" | "error" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Error,
            }),
            "techniques" | "technique" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Technique,
            }),
            "notes" | "note" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Note,
            }),
            "references" | "reference" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Reference,
            }),
            "architecture" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Architecture,
            }),
            "workflows" | "workflow" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Workflow,
            }),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown category: {}",
                category
            ))),
        }
    }

    #[getter]
    fn value(&self) -> String {
        match self.inner {
            KnowledgeCategory::Pattern => "patterns".to_string(),
            KnowledgeCategory::Solution => "solutions".to_string(),
            KnowledgeCategory::Error => "errors".to_string(),
            KnowledgeCategory::Technique => "techniques".to_string(),
            KnowledgeCategory::Note => "notes".to_string(),
            KnowledgeCategory::Reference => "references".to_string(),
            KnowledgeCategory::Architecture => "architecture".to_string(),
            KnowledgeCategory::Workflow => "workflows".to_string(),
        }
    }

    fn __str__(&self) -> String {
        self.value()
    }
}

/// Knowledge entry Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeEntry {
    inner: KnowledgeEntry,
}

#[pymethods]
impl PyKnowledgeEntry {
    #[new]
    #[pyo3(signature = (id, title, content, category))]
    fn new(id: &str, title: &str, content: &str, category: PyKnowledgeCategory) -> Self {
        Self {
            inner: KnowledgeEntry::new(
                id.to_string(),
                title.to_string(),
                content.to_string(),
                category.inner,
            ),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn title(&self) -> String {
        self.inner.title.clone()
    }

    #[getter]
    fn content(&self) -> String {
        self.inner.content.clone()
    }

    #[getter]
    fn category(&self) -> PyKnowledgeCategory {
        PyKnowledgeCategory {
            inner: self.inner.category.clone(),
        }
    }

    #[getter]
    fn tags(&self) -> Vec<String> {
        self.inner.tags.clone()
    }

    #[getter]
    fn source(&self) -> Option<String> {
        self.inner.source.clone()
    }

    #[getter]
    fn version(&self) -> i32 {
        self.inner.version
    }

    #[setter]
    fn set_tags(&mut self, tags: Vec<String>) {
        self.inner.tags = tags;
    }

    #[setter]
    fn set_source(&mut self, source: Option<String>) {
        self.inner.source = source;
    }

    fn add_tag(&mut self, tag: String) {
        self.inner.add_tag(tag);
    }

    fn to_dict(&self) -> PyResult<String> {
        let value = json!({
            "id": self.inner.id,
            "title": self.inner.title,
            "content": self.inner.content,
            "category": self.category().value(),
            "tags": self.inner.tags,
            "source": self.inner.source,
            "version": self.inner.version,
        });
        Ok(to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }
}

/// Knowledge storage Python wrapper
#[pyclass]
#[derive(Debug)]
pub struct PyKnowledgeStorage {
    inner: KnowledgeStorage,
}

#[pymethods]
impl PyKnowledgeStorage {
    #[new]
    #[pyo3(signature = (path, table_name))]
    fn new(path: &str, table_name: &str) -> Self {
        Self {
            inner: KnowledgeStorage::new(path, table_name),
        }
    }

    #[getter]
    fn path(&self) -> String {
        self.inner.path().to_string_lossy().to_string()
    }

    #[getter]
    fn table_name(&self) -> String {
        self.inner.table_name().to_string()
    }

    fn init(&self) -> PyResult<()> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.init())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(())
    }

    fn upsert(&self, entry: &PyKnowledgeEntry) -> PyResult<bool> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.upsert(&entry.inner))
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(true)
    }

    fn text_search(&self, query: &str, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = runtime
            .block_on(self.inner.search_text(query, limit))
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|inner| PyKnowledgeEntry { inner })
            .collect())
    }

    fn vector_search(&self, query_vector: Vec<f32>, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = runtime
            .block_on(self.inner.search(&query_vector, limit))
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|inner| PyKnowledgeEntry { inner })
            .collect())
    }

    fn search(&self, query: &str, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        self.text_search(query, limit)
    }

    fn count(&self) -> PyResult<i64> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.count())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    fn clear(&self) -> PyResult<()> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.clear())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(())
    }
}

/// Create a knowledge entry from Python.
#[pyfunction]
#[pyo3(signature = (title, content, category, tags, source))]
fn create_knowledge_entry(
    title: &str,
    content: &str,
    category: PyKnowledgeCategory,
    tags: Vec<String>,
    source: Option<&str>,
) -> PyResult<PyKnowledgeEntry> {
    let entry = KnowledgeEntry::new(
        uuid::Uuid::new_v4().to_string(),
        title.to_string(),
        content.to_string(),
        category.inner,
    )
    .with_tags(tags)
    .with_source(source.map(|s| s.to_string()));

    Ok(PyKnowledgeEntry { inner: entry })
}

/// Sync result Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySyncResult {
    /// Wrapped sync result payload from Rust core.
    pub inner: SyncResult,
}

#[pymethods]
impl PySyncResult {
    #[getter]
    fn added(&self) -> Vec<String> {
        self.inner
            .added
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    #[getter]
    fn modified(&self) -> Vec<String> {
        self.inner
            .modified
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    #[getter]
    fn deleted(&self) -> Vec<String> {
        self.inner
            .deleted
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    #[getter]
    fn unchanged(&self) -> usize {
        self.inner.unchanged
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "added": self.added(),
            "modified": self.modified(),
            "deleted": self.deleted(),
            "unchanged": self.unchanged(),
        });
        to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Sync engine Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySyncEngine {
    inner: SyncEngine,
}

#[pymethods]
impl PySyncEngine {
    #[new]
    #[pyo3(signature = (project_root, manifest_path))]
    fn new(project_root: &str, manifest_path: &str) -> Self {
        Self {
            inner: SyncEngine::new(project_root, manifest_path),
        }
    }

    fn load_manifest(&self) -> PyResult<String> {
        let manifest = self.inner.load_manifest();
        Ok(serde_json::to_string(&manifest.0).unwrap_or_default())
    }

    fn save_manifest(&self, manifest_json: &str) -> PyResult<()> {
        let manifest: HashMap<String, String> = serde_json::from_str(manifest_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let manifest = SyncManifest(manifest);
        self.inner
            .save_manifest(&manifest)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    fn discover_files(&self) -> Vec<String> {
        self.inner
            .discover_files()
            .into_iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    fn compute_diff(&self, manifest_json: &str) -> PyResult<PySyncResult> {
        let manifest: HashMap<String, String> = serde_json::from_str(manifest_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let manifest = SyncManifest(manifest);

        let files = self.inner.discover_files();
        let result = self.inner.compute_diff(&manifest, &files);

        Ok(PySyncResult { inner: result })
    }
}

/// Compute hash from content using xxhash (fast).
#[pyfunction]
#[pyo3(signature = (content))]
pub fn compute_hash(content: &str) -> String {
    SyncEngine::compute_hash(content)
}

// =============================================================================
// Knowledge Graph PyO3 Bindings
// =============================================================================

/// Python wrapper for Entity type
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyEntityType;

/// Python wrapper for Entity
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyEntity {
    inner: Entity,
}

#[pymethods]
impl PyEntity {
    #[new]
    #[pyo3(signature = (name, entity_type, description))]
    fn new(name: &str, entity_type: &str, description: &str) -> Self {
        let etype = parse_entity_type(entity_type);
        let id = format!(
            "{}:{}",
            etype.to_string().to_lowercase(),
            name.to_lowercase().replace(" ", "_")
        );
        Self {
            inner: Entity::new(id, name.to_string(), etype, description.to_string()),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn name(&self) -> String {
        self.inner.name.clone()
    }

    #[getter]
    fn entity_type(&self) -> String {
        self.inner.entity_type.to_string()
    }

    #[getter]
    fn description(&self) -> String {
        self.inner.description.clone()
    }

    #[getter]
    fn source(&self) -> Option<String> {
        self.inner.source.clone()
    }

    #[getter]
    fn aliases(&self) -> Vec<String> {
        self.inner.aliases.clone()
    }

    #[getter]
    fn confidence(&self) -> f32 {
        self.inner.confidence
    }

    fn to_dict(&self) -> PyResult<String> {
        let value = json!({
            "id": self.inner.id,
            "name": self.inner.name,
            "entity_type": self.inner.entity_type.to_string(),
            "description": self.inner.description,
            "source": self.inner.source,
            "aliases": self.inner.aliases,
            "confidence": self.inner.confidence,
        });
        Ok(serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }
}

/// Python wrapper for Relation
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyRelation {
    inner: Relation,
}

#[pymethods]
impl PyRelation {
    #[new]
    #[pyo3(signature = (source, target, relation_type, description))]
    fn new(source: &str, target: &str, relation_type: &str, description: &str) -> Self {
        let rtype = parse_relation_type(relation_type);
        Self {
            inner: Relation::new(
                source.to_string(),
                target.to_string(),
                rtype,
                description.to_string(),
            ),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn source(&self) -> String {
        self.inner.source.clone()
    }

    #[getter]
    fn target(&self) -> String {
        self.inner.target.clone()
    }

    #[getter]
    fn relation_type(&self) -> String {
        self.inner.relation_type.to_string()
    }

    #[getter]
    fn description(&self) -> String {
        self.inner.description.clone()
    }

    #[getter]
    fn confidence(&self) -> f32 {
        self.inner.confidence
    }

    fn to_dict(&self) -> PyResult<String> {
        let value = json!({
            "id": self.inner.id,
            "source": self.inner.source,
            "target": self.inner.target,
            "relation_type": self.inner.relation_type.to_string(),
            "description": self.inner.description,
            "source_doc": self.inner.source_doc,
            "confidence": self.inner.confidence,
        });
        Ok(serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }
}

/// Python wrapper for KnowledgeGraph
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeGraph {
    inner: KnowledgeGraph,
}

#[pymethods]
impl PyKnowledgeGraph {
    #[new]
    fn new() -> Self {
        Self {
            inner: KnowledgeGraph::new(),
        }
    }

    fn add_entity(&self, entity: PyEntity) -> PyResult<()> {
        self.inner
            .add_entity(entity.inner)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn add_relation(&self, relation: PyRelation) -> PyResult<()> {
        self.inner
            .add_relation(relation.inner)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn search_entities(&self, query: &str, limit: i32) -> Vec<PyEntity> {
        self.inner
            .search_entities(query, limit)
            .into_iter()
            .map(|e| PyEntity { inner: e })
            .collect()
    }

    fn get_entity(&self, entity_id: &str) -> Option<PyEntity> {
        self.inner
            .get_entity(entity_id)
            .map(|e| PyEntity { inner: e })
    }

    fn get_entity_by_name(&self, name: &str) -> Option<PyEntity> {
        self.inner
            .get_entity_by_name(name)
            .map(|e| PyEntity { inner: e })
    }

    fn get_relations(
        &self,
        entity_name: Option<&str>,
        relation_type: Option<&str>,
    ) -> Vec<PyRelation> {
        let rtype = relation_type.map(parse_relation_type);
        self.inner
            .get_relations(entity_name, rtype)
            .into_iter()
            .map(|r| PyRelation { inner: r })
            .collect()
    }

    fn multi_hop_search(&self, start_name: &str, max_hops: usize) -> Vec<PyEntity> {
        self.inner
            .multi_hop_search(start_name, max_hops)
            .into_iter()
            .map(|e| PyEntity { inner: e })
            .collect()
    }

    fn get_stats(&self) -> PyResult<String> {
        let stats = self.inner.get_stats();
        let value = json!({
            "total_entities": stats.total_entities,
            "total_relations": stats.total_relations,
            "entities_by_type": stats.entities_by_type,
            "relations_by_type": stats.relations_by_type,
        });
        Ok(serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }

    fn clear(&mut self) {
        self.inner.clear()
    }

    fn save_to_file(&self, path: &str) -> PyResult<()> {
        self.inner
            .save_to_file(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    fn load_from_file(&mut self, path: &str) -> PyResult<()> {
        self.inner
            .load_from_file(path)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    fn export_as_json(&self) -> PyResult<String> {
        self.inner
            .export_as_json()
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn get_all_entities_json(&self) -> PyResult<String> {
        let entities = self.inner.get_all_entities();
        let entities_json: Vec<Value> = entities
            .into_iter()
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
        serde_json::to_string(&entities_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn get_all_relations_json(&self) -> PyResult<String> {
        let relations = self.inner.get_all_relations();
        let relations_json: Vec<Value> = relations
            .into_iter()
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
        serde_json::to_string(&relations_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }
}

/// Parse entity type from string
fn parse_entity_type(s: &str) -> EntityType {
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

/// Parse relation type from string
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
