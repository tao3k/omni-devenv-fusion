//! omni-core-rs - Python bindings for Omni DevEnv Rust core.
//!
//! Provides high-performance Rust implementations for:
//! - Environment sniffing (OmniSniffer)
//! - File I/O (read_file_safe)
//! - Token counting (count_tokens)
//! - Secret scanning (scan_secrets)
//! - Code navigation (get_file_outline, search_code, search_directory)

use pyo3::prelude::*;
use omni_sniffer::OmniSniffer;
use omni_io;
use omni_tokenizer;
use omni_security::SecretScanner;
use omni_tags::TagExtractor;
use anyhow;

/// Python wrapper for EnvironmentSnapshot.
/// Uses omni_types::EnvironmentSnapshot for type unification.
#[pyclass]
#[derive(serde::Serialize)]
struct PyEnvironmentSnapshot {
    git_branch: String,
    git_modified: usize,
    git_staged: usize,
    active_context_lines: usize,
    dirty_files: Vec<String>,
    timestamp: f64,
}

#[pymethods]
impl PyEnvironmentSnapshot {
    #[getter]
    fn git_branch(&self) -> String {
        self.git_branch.clone()
    }

    #[getter]
    fn git_modified(&self) -> usize {
        self.git_modified
    }

    #[getter]
    fn git_staged(&self) -> usize {
        self.git_staged
    }

    #[getter]
    fn active_context_lines(&self) -> usize {
        self.active_context_lines
    }

    #[getter]
    fn dirty_files(&self) -> Vec<String> {
        self.dirty_files.clone()
    }

    #[getter]
    fn timestamp(&self) -> f64 {
        self.timestamp
    }

    fn to_prompt_string(&self) -> String {
        let dirty_desc = if self.dirty_files.is_empty() {
            "Clean".to_string()
        } else {
            let count = self.dirty_files.len();
            let preview = self.dirty_files.iter().take(3).cloned().collect::<Vec<_>>().join(", ");
            if count > 3 {
                format!("{count} files ({preview}, ...)")
            } else {
                format!("{count} files ({preview})")
            }
        };

        format!(
            "[LIVE ENVIRONMENT STATE]\n\
            - Git: Branch: {} | Modified: {} | Staged: {} | Status: {}\n\
            - Active Context: {} lines in SCRATCHPAD.md",
            self.git_branch,
            self.git_modified,
            self.git_staged,
            dirty_desc,
            self.active_context_lines
        )
    }

    fn to_json(&self) -> String {
        serde_json::to_string(&self).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for OmniSniffer.
#[pyclass]
struct PyOmniSniffer {
    sniffer: OmniSniffer,
}

#[pymethods]
impl PyOmniSniffer {
    #[new]
    fn new(project_root: &str) -> Self {
        Self {
            sniffer: OmniSniffer::new(project_root),
        }
    }

    /// Get environment snapshot (high-performance Rust implementation)
    fn get_snapshot(&self) -> PyEnvironmentSnapshot {
        let snapshot = self.sniffer.get_snapshot();
        PyEnvironmentSnapshot {
            git_branch: snapshot.git_branch,
            git_modified: snapshot.git_modified,
            git_staged: snapshot.git_staged,
            active_context_lines: snapshot.active_context_lines,
            dirty_files: snapshot.dirty_files,
            timestamp: snapshot.timestamp,
        }
    }

    /// Quick git status check (lightweight)
    fn git_status(&self) -> PyResult<(String, usize, usize)> {
        let (branch, modified, staged, _) = self.sniffer.scan_git()
            .map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Git error: {e}")))?;
        Ok((branch, modified, staged))
    }
}

/// Python module initialization
#[pymodule]
fn omni_core_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyOmniSniffer>()?;
    m.add_class::<PyEnvironmentSnapshot>()?;
    m.add_function(pyo3::wrap_pyfunction!(py_get_sniffer, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(get_environment_snapshot, m)?)?;
    // Phase 47: Iron Lung functions
    m.add_function(pyo3::wrap_pyfunction!(read_file_safe, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(count_tokens, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(truncate_tokens, m)?)?;
    // Phase 49: Hyper-Immune System
    m.add_function(pyo3::wrap_pyfunction!(scan_secrets, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(contains_secrets, m)?)?;
    // Phase 50: The Cartographer
    m.add_function(pyo3::wrap_pyfunction!(get_file_outline, m)?)?;
    // Phase 51: The Hunter - Structural Code Search
    m.add_function(pyo3::wrap_pyfunction!(search_code, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(search_directory, m)?)?;
    m.add("VERSION", "0.3.0")?;
    Ok(())
}

#[pyfunction]
#[pyo3(signature = (project_root=None))]
/// Convenience function to get a sniffer for the current directory
fn py_get_sniffer(project_root: Option<&str>) -> PyOmniSniffer {
    let root = project_root.unwrap_or(".");
    PyOmniSniffer::new(root)
}

/// Get environment snapshot as a formatted prompt string.
/// This is the primary interface for Phase 43 Holographic Agent.
#[pyfunction]
#[pyo3(signature = (root_path="."))]
fn get_environment_snapshot(root_path: &str) -> String {
    let sniffer = OmniSniffer::new(root_path);
    let snapshot = sniffer.get_snapshot();
    snapshot.to_prompt_string()
}

// ============================================================================
// Phase 47: The Iron Lung - Safe I/O and Tokenization
// ============================================================================

/// Safely read a text file with size and binary checks.
/// Releases GIL for CPU-intensive file operations.
#[pyfunction]
#[pyo3(signature = (path, max_bytes = 1048576))]
fn read_file_safe(path: String, max_bytes: u64) -> PyResult<String> {
    Python::attach(|py| {
        py.detach(|| {
            omni_io::read_text_safe(path, max_bytes)
                .map_err(|e| anyhow::anyhow!(e))
        })
    }).map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
/// Releases GIL for CPU-intensive tokenization.
#[pyfunction]
fn count_tokens(text: &str) -> usize {
    Python::attach(|py| {
        py.detach(|| {
            omni_tokenizer::count_tokens(text)
        })
    })
}

/// Truncate text to fit within a maximum token count.
/// Releases GIL for CPU-intensive tokenization.
#[pyfunction]
#[pyo3(signature = (text, max_tokens))]
fn truncate_tokens(text: &str, max_tokens: usize) -> String {
    Python::attach(|py| {
        py.detach(|| {
            omni_tokenizer::truncate(text, max_tokens)
        })
    })
}

// ============================================================================
// Phase 49: The Hyper-Immune System - Secret Scanning
// ============================================================================

/// Scan content for secrets (AWS keys, Stripe keys, Slack tokens, etc.)
/// Returns a violation message if secrets are found, None if clean.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
fn scan_secrets(content: &str) -> Option<String> {
    Python::attach(|py| {
        py.detach(|| {
            SecretScanner::scan(content).map(|v| {
                format!("[SECURITY VIOLATION] Found {}: {}", v.rule_id, v.description)
            })
        })
    })
}

/// Check if content contains any secrets (boolean check only).
/// More efficient than scan_secrets when you only need a boolean result.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
fn contains_secrets(content: &str) -> bool {
    Python::attach(|py| {
        py.detach(|| {
            SecretScanner::contains_secrets(content)
        })
    })
}

// ============================================================================
// Phase 50: The Cartographer - AST-based Code Navigation
// ============================================================================

/// Generate a symbolic outline for a file using AST patterns.
/// Returns formatted string showing only definitions (classes, functions, etc.)
/// This is the primary interface for CCA-aligned code navigation.
#[pyfunction]
#[pyo3(signature = (path, language = None))]
fn get_file_outline(path: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::outline_file(&path, language)
                .unwrap_or_else(|e| format!("[Error generating outline: {}]", e))
        })
    })
}

// ============================================================================
// Phase 51: The Hunter - Structural Code Search
// ============================================================================

/// Search for AST patterns in a single file using ast-grep syntax.
///
/// Examples:
/// - Find all function calls: "connect($ARGS)"
/// - Find class definitions: "class $NAME"
/// - Find method definitions: "def $NAME($PARAMS)"
///
/// Returns formatted string with match locations and captured variables.
#[pyfunction]
#[pyo3(signature = (path, pattern, language = None))]
fn search_code(path: String, pattern: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::search_file(&path, &pattern, language)
                .unwrap_or_else(|e| format!("[Search error: {}]", e))
        })
    })
}

/// Search for AST patterns recursively in a directory.
///
/// Args:
///   path: Directory to search in
///   pattern: ast-grep pattern (e.g., "connect($ARGS)", "class $NAME")
///   file_pattern: Optional glob pattern for files (e.g., "**/*.py")
#[pyfunction]
#[pyo3(signature = (path, pattern, file_pattern = None))]
fn search_directory(path: String, pattern: String, file_pattern: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            let config = omni_tags::SearchConfig {
                file_pattern: file_pattern.unwrap_or("**/*").to_string(),
                ..Default::default()
            };
            TagExtractor::search_directory(&path, &pattern, config)
                .unwrap_or_else(|e| format!("[Search error: {}]", e))
        })
    })
}
