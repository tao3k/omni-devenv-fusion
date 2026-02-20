//! omni-core-rs - Python bindings for Omni DevEnv Rust core.
//!
//! Provides high-performance Rust implementations for:
//! - Environment sniffing (OmniSniffer)
//! - File I/O (read_file_safe)
//! - Token counting (count_tokens)
//! - Secret scanning (scan_secrets)
//! - Code navigation (get_file_outline, search_code, search_directory)
//! - Structural refactoring (structural_replace, structural_preview)
//! - Vector Store (PyVectorStore for LanceDB)
//! - Skill Tool Scanner (scan_skill_tools)
//! - Context Assembly (ContextAssembler)

use pyo3::prelude::*;

// ============================================================================
// Module Declarations
// ============================================================================

#[cfg(feature = "assembler")]
pub mod checkpoint;
#[cfg(not(feature = "assembler"))]
pub mod checkpoint;

#[cfg(feature = "assembler")]
mod context;
#[cfg(not(feature = "assembler"))]
mod context;

mod ast;
mod editor;
mod events;
mod executor;
mod io;
mod navigation;
mod sandbox; // NCL-driven sandbox executor
mod scanner;
mod schema; // Schema Registry for Schema Singularity
mod security;
mod sniffer;
mod tags; // Symbol extraction using omni-tags
mod tokenizer; // Add tokenizer module
mod tui;
pub mod utils;
pub mod vector;

#[cfg(feature = "notify")]
mod watcher;
#[cfg(not(feature = "notify"))]
mod watcher; // Empty module when feature disabled

// ============================================================================
// Re-exports from submodules
// ============================================================================

pub use checkpoint::PyCheckpointStore;
pub use checkpoint::PyTimelineEvent;
pub use context::{PyAssemblyResult, PyContextAssembler, PyContextPruner}; // Add PyContextPruner here
pub use editor::{
    PyBatchRefactorStats, batch_structural_replace, structural_apply, structural_preview,
    structural_replace,
};
pub use events::{
    PyEventBus, PyGlobalEventBus, PyOmniEvent, create_event, publish_event, topic_agent_action,
    topic_agent_result, topic_agent_think, topic_file_changed, topic_file_created,
    topic_file_deleted, topic_system_ready,
};
pub use executor::PyOmniCell;
pub use executor::{build_query, build_query_raw};
pub use io::{
    PyDiscoverOptions, count_files_in_dir, count_tokens, discover_files, discover_files_in_dir,
    get_cache_home, get_config_home, get_data_home, read_file_safe, should_skip_path,
    truncate_tokens,
};
pub use navigation::{
    get_file_outline, get_files_outline, search_code, search_directory, search_with_rules,
};
pub use scanner::{
    PySkillMetadata, PySkillScanner, PySyncReport, diff_skills, parse_script_content, scan_paths,
    scan_skill, scan_skill_from_content, scan_skill_tools,
};
pub use security::{
    PySandboxMode, PySandboxResult, PySandboxRunner, PySecurityViolation, check_permission,
    contains_secrets, is_code_safe, scan_code_security, scan_secrets,
};
pub use sniffer::{
    PyEnvironmentSnapshot, PyGlobSniffer, PyOmniSniffer, get_environment_snapshot, py_get_sniffer,
};
pub use utils::run_safe;
pub use vector::{
    PyToolRecord, PyVectorStore, create_vector_store_py, evict_vector_store_cache_py,
};

// Tokenizer exports
pub use tokenizer::{PyMessage, py_chunk_text, py_count_tokens, py_truncate, py_truncate_middle};

// Schema Registry exports (Schema Singularity)
pub use schema::{py_get_registered_types, py_get_schema_json};

// Symbol Extraction (omni-tags)
pub use tags::{
    PySymbol, PySymbolKind, py_extract_symbols, py_get_file_outline, py_parse_symbols,
    py_search_directory, py_search_file, py_search_with_rules,
};

// Knowledge Sync Engine (xiuxian-wendao)
pub use xiuxian_wendao::PyEntity;
pub use xiuxian_wendao::PyEntityType;
pub use xiuxian_wendao::PyKnowledgeGraph;
pub use xiuxian_wendao::PyLinkGraphEngine;
pub use xiuxian_wendao::PyQueryIntent;
pub use xiuxian_wendao::PyRelation;
pub use xiuxian_wendao::PySyncEngine;
pub use xiuxian_wendao::PySyncResult;
pub use xiuxian_wendao::{
    extract_query_intent, invalidate_kg_cache, link_graph_stats_cache_del,
    link_graph_stats_cache_get, link_graph_stats_cache_set, load_kg_from_lance_cached,
};

// Session Window (omni-window, 1k–10k scale)
pub use omni_window::PySessionWindow;

// Self-Evolving Memory (omni-memory)
pub use omni_memory::{
    PyEpisode, PyEpisodeStore, PyIntentEncoder, PyQTable, PyStoreConfig, PyTwoPhaseConfig,
    PyTwoPhaseSearch, create_episode, create_episode_store, create_episode_with_embedding,
    create_intent_encoder, create_q_table, create_two_phase_search, py_calculate_score,
};

// Dependency Indexer (External crate symbol search)
pub use xiuxian_wendao::PyDependencyConfig;
pub use xiuxian_wendao::PyDependencyIndexResult;
pub use xiuxian_wendao::PyDependencyIndexer;
pub use xiuxian_wendao::PyDependencyStats;
pub use xiuxian_wendao::PyExternalSymbol;
pub use xiuxian_wendao::PySymbolIndex;

// LinkGraph Entity Reference Extraction (Rust-accelerated)
pub use xiuxian_wendao::PyLinkGraphEntityRef;
pub use xiuxian_wendao::PyLinkGraphRefStats;
pub use xiuxian_wendao::link_graph_count_refs;
pub use xiuxian_wendao::link_graph_extract_entity_refs;

// LinkGraph Note Enhancement (Rust-accelerated)
pub use xiuxian_wendao::PyEnhancedNote;
pub use xiuxian_wendao::PyInferredRelation;
pub use xiuxian_wendao::PyNoteFrontmatter;
pub use xiuxian_wendao::link_graph_enhance_note;
pub use xiuxian_wendao::link_graph_enhance_notes_batch;
pub use xiuxian_wendao::link_graph_find_referencing_notes;
pub use xiuxian_wendao::link_graph_get_ref_stats;
pub use xiuxian_wendao::link_graph_is_valid_ref;
pub use xiuxian_wendao::link_graph_parse_entity_ref;
pub use xiuxian_wendao::link_graph_parse_frontmatter;

// Dual-core recall boost (LinkGraph proximity, Rust computation)
pub use xiuxian_wendao::dual_core_py::apply_link_graph_proximity_boost_py;

// AST Extraction
pub use ast::{
    PyCodeChunk, PyExtractResult, py_chunk_code, py_extract_items, py_extract_skeleton,
    py_get_supported_languages, py_is_language_supported,
};

// Watcher module exports (notify feature)
#[cfg(feature = "notify")]
pub use watcher::{
    PyFileEvent, PyFileEventReceiver, PyFileWatcherHandle, PyWatcherConfig, py_start_file_watcher,
    py_subscribe_file_events, py_watch_path,
};

// ============================================================================
// Python Module Initialization
// ============================================================================

/// Python module initialization
#[pymodule]
fn omni_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Sniffer module
    m.add_class::<PyOmniSniffer>()?;
    m.add_class::<PyEnvironmentSnapshot>()?;
    m.add_class::<PyGlobSniffer>()?;
    m.add_function(pyo3::wrap_pyfunction!(py_get_sniffer, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_environment_snapshot, m)?)?;

    // Event Bus (Rust-Native Pub/Sub)
    m.add_class::<PyEventBus>()?;
    m.add_class::<PyGlobalEventBus>()?;
    m.add_class::<PyOmniEvent>()?;
    m.add_function(pyo3::wrap_pyfunction!(publish_event, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(create_event, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_file_changed, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_file_created, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_file_deleted, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_agent_think, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_agent_action, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_agent_result, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(topic_system_ready, m)?)?;

    // Iron Lung functions (I/O and Tokenization)
    m.add_function(pyo3::wrap_pyfunction!(read_file_safe, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(count_tokens, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(truncate_tokens, m)?)?;

    // File Discovery (Rust-based high-performance file traversal)
    m.add_function(pyo3::wrap_pyfunction!(discover_files, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(discover_files_in_dir, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(count_files_in_dir, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(should_skip_path, m)?)?;
    m.add_class::<PyDiscoverOptions>()?;

    // Hyper-Immune System (Security) + Permission Gatekeeper + Sandbox
    m.add_function(pyo3::wrap_pyfunction!(scan_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(contains_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(scan_code_security, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(is_code_safe, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(check_permission, m)?)?;
    m.add_class::<PySecurityViolation>()?;
    m.add_class::<PySandboxMode>()?;
    m.add_class::<PySandboxResult>()?;
    m.add_class::<PySandboxRunner>()?;

    // Cartographer and Hunter (Code Navigation)
    m.add_function(pyo3::wrap_pyfunction!(get_file_outline, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_files_outline, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(search_code, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(search_directory, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(search_with_rules, m)?)?;

    // Surgeon (Structural Refactoring)
    m.add_function(pyo3::wrap_pyfunction!(structural_replace, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(structural_preview, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(structural_apply, m)?)?;

    // Ouroboros (Batch Refactoring)
    m.add_function(pyo3::wrap_pyfunction!(batch_structural_replace, m)?)?;
    m.add_class::<PyBatchRefactorStats>()?;

    // Session Window (omni-window)
    m.add_class::<PySessionWindow>()?;

    // Vector Store (omni-vector bindings)
    m.add_function(pyo3::wrap_pyfunction!(create_vector_store_py, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(evict_vector_store_cache_py, m)?)?;
    m.add_class::<PyVectorStore>()?;
    m.add_class::<PyToolRecord>()?;

    // Checkpoint Store (LanceDB-based state persistence)
    m.add_function(pyo3::wrap_pyfunction!(
        checkpoint::create_checkpoint_store,
        m
    )?)?;
    m.add_class::<PyCheckpointStore>()?;
    m.add_class::<PyTimelineEvent>()?;

    // Context Assembler (Parallel I/O + Templating + Token Counting)
    m.add_class::<PyContextAssembler>()?;
    m.add_class::<PyAssemblyResult>()?;
    m.add_class::<PyContextPruner>()?;

    // Tokenizer (High-performance token counting and context pruning)
    m.add_function(pyo3::wrap_pyfunction!(py_count_tokens, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_chunk_text, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_truncate, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_truncate_middle, m)?)?;
    m.add_class::<tokenizer::PyContextPruner>()?;
    m.add_class::<tokenizer::PyMessage>()?;

    // AST Extraction (Project Cerebellum - High Precision Context)
    m.add_function(pyo3::wrap_pyfunction!(py_extract_items, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_extract_skeleton, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_is_language_supported, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_get_supported_languages, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_chunk_code, m)?)?;
    m.add_class::<ast::PyExtractResult>()?;
    m.add_class::<ast::PyCodeChunk>()?;

    // Script Scanner
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_tools, m)?)?;

    // SKILL.md Frontmatter Parser
    m.add_function(pyo3::wrap_pyfunction!(scan_skill, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_from_content, m)?)?;
    m.add_class::<PySkillMetadata>()?;

    // PySkillScanner - Holographic Registry Foundation
    m.add_class::<PySkillScanner>()?;

    // OmniCell - Nushell Native Bridge (File System Replacement)
    m.add_class::<executor::PyOmniCell>()?;
    m.add_function(pyo3::wrap_pyfunction!(build_query, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(build_query_raw, m)?)?;

    // Skill Sync
    m.add_function(pyo3::wrap_pyfunction!(diff_skills, m)?)?;
    m.add_class::<PySyncReport>()?;

    // Virtual Path Scanner (Testing & API support)
    m.add_function(pyo3::wrap_pyfunction!(scan_paths, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(parse_script_content, m)?)?;

    // Schema Registry - Dynamic JSON Schema Generation (Schema Singularity)
    m.add_function(pyo3::wrap_pyfunction!(py_get_schema_json, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_get_registered_types, m)?)?;

    // Rust Bridge Config Sync (PRJ_SPEC Compliance)
    m.add_function(pyo3::wrap_pyfunction!(get_config_home, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_data_home, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_cache_home, m)?)?;

    // File Watcher (notify feature - Replaced Python watchdog with Rust-native implementation)
    #[cfg(feature = "notify")]
    {
        m.add_function(pyo3::wrap_pyfunction!(py_watch_path, m)?)?;
        m.add_function(pyo3::wrap_pyfunction!(py_start_file_watcher, m)?)?;
        m.add_function(pyo3::wrap_pyfunction!(py_subscribe_file_events, m)?)?;
        m.add_class::<PyFileWatcherHandle>()?;
        m.add_class::<PyFileEventReceiver>()?;
        m.add_class::<PyWatcherConfig>()?;
        m.add_class::<PyFileEvent>()?;
    }

    // Knowledge Sync Engine (xiuxian-wendao)
    m.add_class::<PySyncEngine>()?;
    m.add_class::<PySyncResult>()?;
    m.add_function(pyo3::wrap_pyfunction!(xiuxian_wendao::compute_hash, m)?)?;

    // Knowledge Graph (xiuxian-wendao)
    m.add_class::<xiuxian_wendao::PyKnowledgeGraph>()?;
    m.add_class::<xiuxian_wendao::PyEntity>()?;
    m.add_class::<xiuxian_wendao::PyRelation>()?;
    m.add_class::<xiuxian_wendao::PyEntityType>()?;
    m.add_class::<xiuxian_wendao::PyQueryIntent>()?;
    m.add_class::<xiuxian_wendao::PyLinkGraphEngine>()?;
    m.add_function(pyo3::wrap_pyfunction!(extract_query_intent, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(invalidate_kg_cache, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(load_kg_from_lance_cached, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_stats_cache_get, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_stats_cache_set, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_stats_cache_del, m)?)?;

    // LinkGraph Entity Reference Extraction (Rust-accelerated)
    m.add_function(pyo3::wrap_pyfunction!(link_graph_extract_entity_refs, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_get_ref_stats, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_parse_entity_ref, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_is_valid_ref, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_count_refs, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(
        link_graph_find_referencing_notes,
        m
    )?)?;
    m.add_class::<xiuxian_wendao::PyLinkGraphEntityRef>()?;
    m.add_class::<xiuxian_wendao::PyLinkGraphRefStats>()?;

    // LinkGraph Note Enhancement (Rust-accelerated)
    m.add_class::<xiuxian_wendao::PyEnhancedNote>()?;
    m.add_class::<xiuxian_wendao::PyNoteFrontmatter>()?;
    m.add_class::<xiuxian_wendao::PyInferredRelation>()?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_enhance_note, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_enhance_notes_batch, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(link_graph_parse_frontmatter, m)?)?;

    // Dual-core recall boost (LinkGraph proximity)
    m.add_function(pyo3::wrap_pyfunction!(
        apply_link_graph_proximity_boost_py,
        m
    )?)?;

    // Dependency Indexer (External crate symbol search)
    use xiuxian_wendao::dep_indexer_py::register_dependency_indexer_module;
    register_dependency_indexer_module(m)?;

    // Unified Symbol Index (Project + External dependency search)
    use xiuxian_wendao::unified_symbol_py::register_unified_symbol_module;
    // NCL-driven Sandbox Executor (omni-sandbox)
    m.add_function(pyo3::wrap_pyfunction!(sandbox::sandbox_detect_platform, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(
        sandbox::sandbox_is_nsjail_available,
        m
    )?)?;
    m.add_function(pyo3::wrap_pyfunction!(
        sandbox::sandbox_is_seatbelt_available,
        m
    )?)?;
    m.add_class::<sandbox::ExecutionResult>()?;
    m.add_class::<sandbox::SandboxConfig>()?;
    m.add_class::<sandbox::MountConfig>()?;
    m.add_class::<sandbox::NsJailExecutor>()?;
    m.add_class::<sandbox::SeatbeltExecutor>()?;

    register_unified_symbol_module(m)?;

    // Self-Evolving Memory (omni-memory)
    m.add_class::<PyEpisode>()?;
    m.add_class::<PyQTable>()?;
    m.add_class::<PyIntentEncoder>()?;
    m.add_class::<PyStoreConfig>()?;
    m.add_class::<PyEpisodeStore>()?;
    m.add_class::<PyTwoPhaseConfig>()?;
    m.add_class::<PyTwoPhaseSearch>()?;
    m.add_function(pyo3::wrap_pyfunction!(create_episode, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(create_q_table, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(create_intent_encoder, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(create_episode_store, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(create_two_phase_search, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(py_calculate_score, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(create_episode_with_embedding, m)?)?;

    m.add("VERSION", "0.5.0")?;
    Ok(())
}
