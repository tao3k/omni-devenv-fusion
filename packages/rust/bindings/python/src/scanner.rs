//! Script Scanner - Phase 62: Direct Python Bindings
//!
//! Provides direct Python bindings for scanning skill tools.

use crate::vector::PyToolRecord;
use omni_vector::ScriptScanner;
use pyo3::prelude::*;
use std::path::Path;

/// Scan a skills directory and return discovered tools.
///
/// This function uses the Rust ast-grep scanner to find all Python functions
/// decorated with @skill_command in the skill scripts directory.
///
/// Args:
///   base_path: Base directory containing skills (e.g., "assets/skills")
///
/// Returns:
///   List of PyToolRecord objects with discovered tools
#[pyfunction]
#[pyo3(signature = (base_path))]
pub fn scan_skill_tools(base_path: String) -> Vec<PyToolRecord> {
    let scanner = ScriptScanner::new();
    let skills_path = Path::new(&base_path);

    if !skills_path.exists() {
        return Vec::new();
    }

    match scanner.scan_all(skills_path) {
        Ok(tools) => tools.into_iter().map(|t| t.into()).collect(),
        Err(_) => Vec::new(),
    }
}
