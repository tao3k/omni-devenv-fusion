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

mod editor;
mod events;
mod io;
mod navigation;
mod scanner;
mod security;
mod sniffer;
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
pub use io::{
    count_tokens, get_cache_home, get_config_home, get_data_home, read_file_safe, truncate_tokens,
};
pub use navigation::{get_file_outline, search_code, search_directory};
pub use scanner::{
    PySkillMetadata, PySyncReport, diff_skills, export_skill_index, get_skill_index_schema,
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
pub use vector::{PyToolRecord, PyVectorStore, create_vector_store};

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
    m.add_function(pyo3::wrap_pyfunction!(search_code, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(search_directory, m)?)?;

    // Surgeon (Structural Refactoring)
    m.add_function(pyo3::wrap_pyfunction!(structural_replace, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(structural_preview, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(structural_apply, m)?)?;

    // Ouroboros (Batch Refactoring)
    m.add_function(pyo3::wrap_pyfunction!(batch_structural_replace, m)?)?;
    m.add_class::<PyBatchRefactorStats>()?;

    // Vector Store (omni-vector bindings)
    m.add_function(pyo3::wrap_pyfunction!(create_vector_store, m)?)?;
    m.add_class::<PyVectorStore>()?;
    m.add_class::<PyToolRecord>()?;

    // Checkpoint Store (LanceDB-based state persistence)
    m.add_function(pyo3::wrap_pyfunction!(
        checkpoint::create_checkpoint_store,
        m
    )?)?;
    m.add_class::<PyCheckpointStore>()?;

    // Context Assembler (Parallel I/O + Templating + Token Counting)
    m.add_class::<PyContextAssembler>()?;
    m.add_class::<PyAssemblyResult>()?;
    m.add_class::<PyContextPruner>()?; // Add PyContextPruner here

    // Script Scanner
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_tools, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(export_skill_index, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_skill_index_schema, m)?)?;

    // SKILL.md Frontmatter Parser
    m.add_function(pyo3::wrap_pyfunction!(scan_skill, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_from_content, m)?)?;
    m.add_class::<PySkillMetadata>()?;

    // Skill Sync
    m.add_function(pyo3::wrap_pyfunction!(diff_skills, m)?)?;
    m.add_class::<PySyncReport>()?;

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

    m.add("VERSION", "0.5.0")?;
    Ok(())
}
