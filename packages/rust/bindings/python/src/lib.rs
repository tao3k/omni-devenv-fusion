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
//!
//! Phase 53 Vector Store moved to omni-vector-rs package for faster builds.

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
pub use io::{count_tokens, read_file_safe, truncate_tokens};
pub use navigation::{get_file_outline, search_code, search_directory};
pub use scanner::scan_skill_tools;
pub use security::{contains_secrets, scan_secrets};
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

    // Hyper-Immune System (Security)
    m.add_function(pyo3::wrap_pyfunction!(scan_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(contains_secrets, m)?)?;

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

    // Script Scanner (Phase 62)
    m.add_function(pyo3::wrap_pyfunction!(scan_skill_tools, m)?)?;

    m.add("VERSION", "0.5.0")?;
    Ok(())
}
