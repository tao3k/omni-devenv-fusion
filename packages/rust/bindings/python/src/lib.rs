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

use pyo3::prelude::*;

// ============================================================================
// Module Declarations
// ============================================================================

mod editor;
mod io;
mod navigation;
mod scanner;
mod security;
mod sniffer;
mod vector;

// ============================================================================
// Re-exports from submodules
// ============================================================================

pub use editor::{
    PyBatchRefactorStats, batch_structural_replace, structural_apply, structural_preview,
    structural_replace,
};
pub use io::{
    count_tokens, get_cache_home, get_config_home, get_data_home, read_file_safe, truncate_tokens,
};
pub use navigation::{get_file_outline, search_code, search_directory};
pub use scanner::{
    PySkillMetadata, export_skill_index, get_skill_index_schema, scan_skill,
    scan_skill_from_content, scan_skill_tools,
};
pub use security::{check_permission, contains_secrets, scan_secrets};
pub use sniffer::{PyEnvironmentSnapshot, PyOmniSniffer, get_environment_snapshot, py_get_sniffer};
pub use vector::{PyToolRecord, PyVectorStore, create_vector_store};

// ============================================================================
// Python Module Initialization
// ============================================================================

/// Python module initialization
#[pymodule]
fn omni_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Sniffer module
    m.add_class::<PyOmniSniffer>()?;
    m.add_class::<PyEnvironmentSnapshot>()?;
    m.add_function(pyo3::wrap_pyfunction!(py_get_sniffer, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_environment_snapshot, m)?)?;

    // Iron Lung functions (I/O and Tokenization)
    m.add_function(pyo3::wrap_pyfunction!(read_file_safe, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(count_tokens, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(truncate_tokens, m)?)?;

    // Hyper-Immune System (Security) + Permission Gatekeeper
    m.add_function(pyo3::wrap_pyfunction!(scan_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(contains_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(check_permission, m)?)?;

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

    // Script Scanner
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_tools, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(export_skill_index, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_skill_index_schema, m)?)?;

    // SKILL.md Frontmatter Parser
    m.add_function(pyo3::wrap_pyfunction!(scan_skill, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_from_content, m)?)?;
    m.add_class::<PySkillMetadata>()?;

    // Rust Bridge Config Sync (PRJ_SPEC Compliance)
    m.add_function(pyo3::wrap_pyfunction!(get_config_home, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_data_home, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_cache_home, m)?)?;

    m.add("VERSION", "0.5.0")?;
    Ok(())
}
