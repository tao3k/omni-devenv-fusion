//! omni-knowledge - High-performance knowledge management library.
//!
//! Module layout (by domain):
//! - `types` / `knowledge_py`: Knowledge entries and categories
//! - `storage` / `storage_py`: LanceDB persistence
//! - `sync` / `sync_py`: Incremental file sync engine
//! - `entity` / `graph` / `graph_py`: Knowledge graph (entities, relations, search)
//! - `enhancer` / `enhancer_py`: ZK note enhancement
//! - `zk` / `zk_py`: Zettelkasten entity references
//! - `dependency_indexer` / `dep_indexer_py`: Dependency scanning
//! - `unified_symbol` / `unified_symbol_py`: Cross-language symbol index
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

// ---------------------------------------------------------------------------
// Core domain modules
// ---------------------------------------------------------------------------
mod entity;
pub mod graph;
mod storage;
mod sync;
mod types;

// ---------------------------------------------------------------------------
// PyO3 binding modules (one per domain)
// ---------------------------------------------------------------------------
pub mod graph_py;
pub mod knowledge_py;
pub mod storage_py;
pub mod sync_py;

// ---------------------------------------------------------------------------
// Feature modules (enhancer, zk, dependency, unified symbol)
// ---------------------------------------------------------------------------
pub mod dep_indexer_py;
pub mod dependency_indexer;
pub mod enhancer;
pub mod enhancer_py;
pub mod unified_symbol;
pub mod unified_symbol_py;
pub mod zk;
mod zk_py;

// ---------------------------------------------------------------------------
// Public re-exports (crate API)
// ---------------------------------------------------------------------------
pub use dep_indexer_py::{
    PyDependencyConfig, PyDependencyIndexResult, PyDependencyIndexer, PyDependencyStats,
    PyExternalDependency, PyExternalSymbol, PySymbolIndex,
};
pub use dependency_indexer::{
    ConfigExternalDependency, DependencyBuildConfig, DependencyConfig, DependencyIndexResult,
    DependencyIndexer, DependencyStats, ExternalSymbol, SymbolIndex, SymbolKind,
};
pub use enhancer::{
    EnhancedNote, EntityRefData, InferredRelation, NoteFrontmatter, NoteInput, RefStatsData,
    enhance_note, enhance_notes_batch, parse_frontmatter,
};
pub use enhancer_py::{
    PyEnhancedNote, PyInferredRelation, PyNoteFrontmatter, zk_enhance_note, zk_enhance_notes_batch,
    zk_parse_frontmatter,
};
pub use entity::{
    Entity, EntitySearchQuery, EntityType, GraphStats, MultiHopOptions, Relation, RelationType,
};
pub use graph::{KnowledgeGraph, QueryIntent, SkillDoc, SkillRegistrationResult, extract_intent};
pub use storage::KnowledgeStorage;
pub use sync::{DiscoveryOptions, FileChange, SyncEngine, SyncManifest, SyncResult};
pub use types::{KnowledgeCategory, KnowledgeEntry, KnowledgeSearchQuery, KnowledgeStats};
pub use unified_symbol::{SymbolSource, UnifiedIndexStats, UnifiedSymbol, UnifiedSymbolIndex};
pub use unified_symbol_py::{PyUnifiedIndexStats, PyUnifiedSymbol, PyUnifiedSymbolIndex};
pub use zk::{
    ZkEntityRef, ZkRefStats, extract_entity_refs, find_notes_referencing_entity, get_ref_stats,
};
pub use zk_py::{
    PyZkEntityRef, PyZkRefStats, zk_count_refs, zk_extract_entity_refs, zk_find_referencing_notes,
    zk_get_ref_stats, zk_is_valid_ref, zk_parse_entity_ref,
};

// Re-export PyO3 types for convenience
pub use graph_py::{
    PyEntity, PyEntityType, PyKnowledgeGraph, PyQueryIntent, PyRelation, PySkillDoc,
    extract_query_intent,
};
pub use knowledge_py::{PyKnowledgeCategory, PyKnowledgeEntry, create_knowledge_entry};
pub use storage_py::PyKnowledgeStorage;
pub use sync_py::{PySyncEngine, PySyncResult, compute_hash};

// ---------------------------------------------------------------------------
// Python module registration
// ---------------------------------------------------------------------------

/// Python module definition — delegates to domain-specific binding modules.
#[pymodule]
fn _omni_knowledge(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    // Knowledge types
    m.add_class::<knowledge_py::PyKnowledgeCategory>()?;
    m.add_class::<knowledge_py::PyKnowledgeEntry>()?;
    m.add_function(wrap_pyfunction!(knowledge_py::create_knowledge_entry, _py)?)?;

    // Storage
    m.add_class::<storage_py::PyKnowledgeStorage>()?;

    // Sync
    m.add_class::<sync_py::PySyncEngine>()?;
    m.add_class::<sync_py::PySyncResult>()?;
    m.add_function(wrap_pyfunction!(sync_py::compute_hash, _py)?)?;

    // Knowledge graph
    m.add_class::<graph_py::PyEntity>()?;
    m.add_class::<graph_py::PyRelation>()?;
    m.add_class::<graph_py::PyKnowledgeGraph>()?;
    m.add_class::<graph_py::PySkillDoc>()?;
    m.add_class::<graph_py::PyQueryIntent>()?;
    m.add_function(wrap_pyfunction!(graph_py::extract_query_intent, _py)?)?;

    // ZK entity references
    m.add_class::<PyZkEntityRef>()?;
    m.add_class::<PyZkRefStats>()?;
    m.add_function(wrap_pyfunction!(zk_extract_entity_refs, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_get_ref_stats, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_parse_entity_ref, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_is_valid_ref, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_count_refs, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_find_referencing_notes, _py)?)?;

    // Enhancer
    m.add_class::<PyEnhancedNote>()?;
    m.add_class::<PyNoteFrontmatter>()?;
    m.add_class::<PyInferredRelation>()?;
    m.add_function(wrap_pyfunction!(zk_enhance_note, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_enhance_notes_batch, _py)?)?;
    m.add_function(wrap_pyfunction!(zk_parse_frontmatter, _py)?)?;

    // Unified symbol index
    unified_symbol_py::register_unified_symbol_module(m)?;

    Ok(())
}
