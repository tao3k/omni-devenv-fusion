//! Structural Editor - The Surgeon / The Ouroboros
//!
//! Provides AST-based structural search and replace capabilities.

use crate::utils::run_safe;
use omni_edit::{BatchConfig, BatchRefactorStats, StructuralEditor};
use pyo3::prelude::*;
use std::path::Path;

/// Result of batch structural refactoring.
#[pyclass]
pub struct PyBatchRefactorStats {
    #[pyo3(get)]
    files_scanned: usize,
    #[pyo3(get)]
    files_changed: usize,
    #[pyo3(get)]
    replacements: usize,
    #[pyo3(get)]
    modified_files: Vec<String>,
    #[pyo3(get)]
    errors: Vec<String>,
}

impl From<BatchRefactorStats> for PyBatchRefactorStats {
    fn from(stats: BatchRefactorStats) -> Self {
        Self {
            files_scanned: stats.files_scanned,
            files_changed: stats.files_changed,
            replacements: stats.replacements,
            modified_files: stats.modified_files,
            errors: stats
                .errors
                .into_iter()
                .map(|(k, v)| format!("{}: {}", k, v))
                .collect(),
        }
    }
}

/// Perform structural replace on content using ast-grep patterns.
///
/// This is the pure function that operates on content strings.
/// Use structural_preview or structural_apply for file operations.
///
/// Args:
///   content: Source code content
///   pattern: ast-grep pattern to match (e.g., "connect($ARGS)")
///   replacement: Replacement pattern (e.g., "async_connect($ARGS)")
///   language: Programming language (python, rust, javascript, typescript)
///
/// Returns:
///   Formatted string showing diff and edit locations, or error message.
///
/// Examples:
///   structural_replace("x = connect(a, b)", "connect($ARGS)", "safe_connect($ARGS)", "python")
///   # Returns diff showing "x = safe_connect(a, b)"
#[pyfunction]
pub fn structural_replace(
    content: &str,
    pattern: &str,
    replacement: &str,
    language: &str,
) -> String {
    run_safe(|| {
        Python::attach(|py| {
            Ok(py.detach(|| {
                match StructuralEditor::replace(content, pattern, replacement, language) {
                    Ok(result) => StructuralEditor::format_result(&result, None),
                    Err(e) => format!("[Structural replace error: {}]", e),
                }
            }))
        })
    })
    .unwrap_or_else(|e| format!("[Rust panic caught: {}]", e))
}

/// Preview structural replace on a file (no modification).
///
/// Returns diff showing what changes would be made without modifying the file.
///
/// Args:
///   path: Path to the source file
///   pattern: ast-grep pattern to match
///   replacement: Replacement pattern
///   language: Optional language hint (auto-detected if None)
///
/// Returns:
///   Formatted string showing diff and edit locations.
#[pyfunction]
#[pyo3(signature = (path, pattern, replacement, language = None))]
pub fn structural_preview(
    path: String,
    pattern: &str,
    replacement: &str,
    language: Option<&str>,
) -> String {
    run_safe(|| {
        Python::attach(|py| {
            Ok(py.detach(|| {
                match StructuralEditor::preview(&path, pattern, replacement, language) {
                    Ok(result) => StructuralEditor::format_result(&result, Some(&path)),
                    Err(e) => format!("[Structural preview error: {}]", e),
                }
            }))
        })
    })
    .unwrap_or_else(|e| format!("[Rust panic caught: {}]", e))
}

/// Apply structural replace to a file (modifies the file).
///
/// **CAUTION**: This modifies the file in place. Use structural_preview first to verify changes.
///
/// Args:
///   path: Path to the source file
///   pattern: ast-grep pattern to match
///   replacement: Replacement pattern
///   language: Optional language hint (auto-detected if None)
///
/// Returns:
///   Formatted string showing applied changes and diff.
#[pyfunction]
#[pyo3(signature = (path, pattern, replacement, language = None))]
pub fn structural_apply(
    path: String,
    pattern: &str,
    replacement: &str,
    language: Option<&str>,
) -> String {
    run_safe(|| {
        Python::attach(|py| {
            Ok(py.detach(
                || match StructuralEditor::apply(&path, pattern, replacement, language) {
                    Ok(result) => {
                        let mut output = StructuralEditor::format_result(&result, Some(&path));
                        if result.count > 0 {
                            output.push_str("\n[FILE MODIFIED]\n");
                        }
                        output
                    }
                    Err(e) => format!("[Structural apply error: {}]", e),
                },
            ))
        })
    })
    .unwrap_or_else(|e| format!("[Rust panic caught: {}]", e))
}

/// Perform batch structural refactoring across a directory.
///
/// This is the "heavy equipment" function that processes thousands of files
/// in parallel using Rust's rayon thread pool.
///
/// Args:
///   root_path: Root directory to start searching
///   search_pattern: ast-grep pattern to match (e.g., `print($ARGS)`)
///   rewrite_pattern: Replacement pattern (e.g., `logger.info($ARGS)`)
///   file_pattern: Glob pattern for files (e.g., `**/*.py`)
///   dry_run: If true, only preview changes (default: true)
///
/// Returns:
///   PyBatchRefactorStats with statistics about the operation.
#[pyfunction]
#[pyo3(signature = (root_path, search_pattern, rewrite_pattern, file_pattern = "**/*.py", dry_run = true))]
pub fn batch_structural_replace(
    root_path: String,
    search_pattern: String,
    rewrite_pattern: String,
    file_pattern: &str,
    dry_run: bool,
) -> PyResult<PyBatchRefactorStats> {
    run_safe(|| {
        Python::attach(|py| {
            Ok(py.detach(|| {
                let config = BatchConfig {
                    file_pattern: file_pattern.to_string(),
                    dry_run,
                    ..Default::default()
                };

                let stats = StructuralEditor::batch_replace(
                    Path::new(&root_path),
                    &search_pattern,
                    &rewrite_pattern,
                    &config,
                );

                Ok(PyBatchRefactorStats::from(stats))
            }))
        })
    })
    .unwrap_or_else(|e| {
        // Return stats with error message
        Ok(PyBatchRefactorStats {
            files_scanned: 0,
            files_changed: 0,
            replacements: 0,
            modified_files: vec![],
            errors: vec![format!("Rust panic during batch operation: {}", e)],
        })
    })
}
