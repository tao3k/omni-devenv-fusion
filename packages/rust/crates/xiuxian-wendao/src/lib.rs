//! xiuxian-wendao - High-performance knowledge management library.
//!
//! Module layout (by domain):
//! - `types` / `knowledge_py`: Knowledge entries and categories
//! - `storage` / `storage_py`: `LanceDB` persistence
//! - `sync` / `sync_py`: Incremental file sync engine
//! - `entity` / `graph` / `graph_py`: Knowledge graph (entities, relations, search)
//! - `enhancer` / `enhancer_py`: LinkGraph note enhancement
//! - `link_graph_refs` / `link_graph_refs_py`: LinkGraph entity references
//! - `dependency_indexer` / `dep_indexer_py`: Dependency scanning
//! - `unified_symbol` / `unified_symbol_py`: Cross-language symbol index
//!
//! # Examples
//!
//! ```rust
//! use xiuxian_wendao::{KnowledgeEntry, KnowledgeCategory};
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
//! use xiuxian_wendao::{Entity, Relation, EntityType, RelationType, KnowledgeGraph};
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
pub mod hmas;
pub mod kg_cache;
pub mod link_graph;
pub mod link_graph_py;
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
// Dual-core recall boost (Rust computation, Python thin wrapper)
// ---------------------------------------------------------------------------
mod dual_core;
pub mod dual_core_py;

// ---------------------------------------------------------------------------
// Feature modules (enhancer, link graph refs, dependency, unified symbol)
// ---------------------------------------------------------------------------
pub mod dep_indexer_py;
pub mod dependency_indexer;
pub mod enhancer;
pub mod enhancer_py;
pub mod link_graph_refs;
mod link_graph_refs_py;
pub mod unified_symbol;
pub mod unified_symbol_py;

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
    PyEnhancedNote, PyInferredRelation, PyNoteFrontmatter, link_graph_enhance_note,
    link_graph_enhance_notes_batch, link_graph_parse_frontmatter,
};
pub use entity::{
    Entity, EntitySearchQuery, EntityType, GraphStats, MultiHopOptions, Relation, RelationType,
};
pub use graph::{KnowledgeGraph, QueryIntent, SkillDoc, SkillRegistrationResult, extract_intent};
pub use hmas::{
    HmasConclusionPayload, HmasDigitalThreadPayload, HmasEvidencePayload, HmasRecordKind,
    HmasSourceNode, HmasTaskPayload, HmasValidationIssue, HmasValidationReport,
    validate_blackboard_file, validate_blackboard_markdown,
};
pub use link_graph::{
    LINK_GRAPH_SALIENCY_SCHEMA_VERSION, LinkGraphDirection, LinkGraphDocument, LinkGraphEdgeType,
    LinkGraphHit, LinkGraphIndex, LinkGraphLinkFilter, LinkGraphMatchStrategy, LinkGraphMetadata,
    LinkGraphNeighbor, LinkGraphPprSubgraphMode, LinkGraphRelatedFilter,
    LinkGraphRelatedPprDiagnostics, LinkGraphRelatedPprOptions, LinkGraphSaliencyPolicy,
    LinkGraphSaliencyState, LinkGraphSaliencyTouchRequest, LinkGraphScope, LinkGraphSearchFilters,
    LinkGraphSearchOptions, LinkGraphSortField, LinkGraphSortOrder, LinkGraphSortTerm,
    LinkGraphStats, LinkGraphTagFilter, ParsedLinkGraphQuery, compute_link_graph_saliency,
    parse_search_query, resolve_link_graph_index_runtime, set_link_graph_config_home_override,
    set_link_graph_wendao_config_override, valkey_saliency_del, valkey_saliency_get,
    valkey_saliency_get_with_valkey, valkey_saliency_touch, valkey_saliency_touch_with_valkey,
};
pub use link_graph_py::{
    PyLinkGraphEngine, link_graph_stats_cache_del, link_graph_stats_cache_get,
    link_graph_stats_cache_set,
};
pub use link_graph_refs::{
    LinkGraphEntityRef, LinkGraphRefStats, extract_entity_refs, find_notes_referencing_entity,
    get_ref_stats,
};
pub use link_graph_refs_py::{
    PyLinkGraphEntityRef, PyLinkGraphRefStats, link_graph_count_refs,
    link_graph_extract_entity_refs, link_graph_find_referencing_notes, link_graph_get_ref_stats,
    link_graph_is_valid_ref, link_graph_parse_entity_ref,
};
pub use storage::KnowledgeStorage;
pub use sync::{DiscoveryOptions, FileChange, SyncEngine, SyncManifest, SyncResult};
pub use types::{KnowledgeCategory, KnowledgeEntry, KnowledgeSearchQuery, KnowledgeStats};
pub use unified_symbol::{SymbolSource, UnifiedIndexStats, UnifiedSymbol, UnifiedSymbolIndex};
pub use unified_symbol_py::{PyUnifiedIndexStats, PyUnifiedSymbol, PyUnifiedSymbolIndex};

// Re-export PyO3 types for convenience
pub use graph_py::{
    PyEntity, PyEntityType, PyKnowledgeGraph, PyQueryIntent, PyRelation, PySkillDoc,
    extract_query_intent, invalidate_kg_cache, load_kg_from_lance_cached,
};
pub use knowledge_py::{PyKnowledgeCategory, PyKnowledgeEntry, create_knowledge_entry};
pub use storage_py::PyKnowledgeStorage;
pub use sync_py::{PySyncEngine, PySyncResult, compute_hash};

// ---------------------------------------------------------------------------
// Python module registration
// ---------------------------------------------------------------------------

/// Python module definition — delegates to domain-specific binding modules.
#[pymodule]
fn _xiuxian_wendao(py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    // Knowledge types
    m.add_class::<knowledge_py::PyKnowledgeCategory>()?;
    m.add_class::<knowledge_py::PyKnowledgeEntry>()?;
    m.add_function(wrap_pyfunction!(knowledge_py::create_knowledge_entry, py)?)?;

    // Storage
    m.add_class::<storage_py::PyKnowledgeStorage>()?;

    // Sync
    m.add_class::<sync_py::PySyncEngine>()?;
    m.add_class::<sync_py::PySyncResult>()?;
    m.add_function(wrap_pyfunction!(sync_py::compute_hash, py)?)?;

    // Knowledge graph
    m.add_class::<graph_py::PyEntity>()?;
    m.add_class::<graph_py::PyRelation>()?;
    m.add_class::<graph_py::PyKnowledgeGraph>()?;
    m.add_class::<graph_py::PySkillDoc>()?;
    m.add_class::<graph_py::PyQueryIntent>()?;
    m.add_function(wrap_pyfunction!(graph_py::extract_query_intent, py)?)?;
    m.add_function(wrap_pyfunction!(graph_py::invalidate_kg_cache, py)?)?;
    m.add_function(wrap_pyfunction!(graph_py::load_kg_from_lance_cached, py)?)?;
    m.add_class::<link_graph_py::PyLinkGraphEngine>()?;
    m.add_function(wrap_pyfunction!(
        link_graph_py::link_graph_stats_cache_get,
        py
    )?)?;
    m.add_function(wrap_pyfunction!(
        link_graph_py::link_graph_stats_cache_set,
        py
    )?)?;
    m.add_function(wrap_pyfunction!(
        link_graph_py::link_graph_stats_cache_del,
        py
    )?)?;

    // LinkGraph entity references
    m.add_class::<PyLinkGraphEntityRef>()?;
    m.add_class::<PyLinkGraphRefStats>()?;
    m.add_function(wrap_pyfunction!(link_graph_extract_entity_refs, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_get_ref_stats, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_parse_entity_ref, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_is_valid_ref, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_count_refs, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_find_referencing_notes, py)?)?;

    // Enhancer
    m.add_class::<PyEnhancedNote>()?;
    m.add_class::<PyNoteFrontmatter>()?;
    m.add_class::<PyInferredRelation>()?;
    m.add_function(wrap_pyfunction!(link_graph_enhance_note, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_enhance_notes_batch, py)?)?;
    m.add_function(wrap_pyfunction!(link_graph_parse_frontmatter, py)?)?;

    // Dual-core recall boost (LinkGraph proximity)
    m.add_function(wrap_pyfunction!(
        dual_core_py::apply_link_graph_proximity_boost_py,
        py
    )?)?;

    // Unified symbol index
    unified_symbol_py::register_unified_symbol_module(m)?;

    Ok(())
}
