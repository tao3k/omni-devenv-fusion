//! Environment Sniffer - High-performance Rust environment detection
//!
//! This module provides Python bindings for:
//! - OmniSniffer: Git state and active context detection
//! - PyGlobSniffer: High-performance GlobSet-based context detection (1600+ rules)
//!
//! The GlobSet engine compiles all patterns into a single DFA, enabling
//! O(1) pattern matching per file instead of O(Rules) loops.

use omni_sniffer::{OmniSniffer, SnifferEngine, SnifferRule};
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyDict, PyList};

/// Python wrapper for EnvironmentSnapshot.
/// Uses omni_types::EnvironmentSnapshot for type unification.
#[pyclass]
#[derive(serde::Serialize)]
pub struct PyEnvironmentSnapshot {
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
            let preview = self
                .dirty_files
                .iter()
                .take(3)
                .cloned()
                .collect::<Vec<_>>()
                .join(", ");
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
pub struct PyOmniSniffer {
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
        let (branch, modified, staged, _) = self.sniffer.scan_git().map_err(|e| {
            pyo3::PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Git error: {e}"))
        })?;
        Ok((branch, modified, staged))
    }
}

/// Convenience function to get a sniffer for the current directory
#[pyfunction]
#[pyo3(signature = (project_root=None))]
pub fn py_get_sniffer(project_root: Option<&str>) -> PyOmniSniffer {
    let root = project_root.unwrap_or(".");
    PyOmniSniffer::new(root)
}

/// Get environment snapshot as a formatted prompt string.
/// This is the primary interface for Holographic Agent.
#[pyfunction]
#[pyo3(signature = (root_path="."))]
pub fn get_environment_snapshot(root_path: &str) -> String {
    let sniffer = OmniSniffer::new(root_path);
    let snapshot = sniffer.get_snapshot();
    snapshot.to_prompt_string()
}

// ============================================================================
// High-Performance GlobSet Sniffer (Rust-Native Cortex)
// ============================================================================

/// Python wrapper for the high-performance GlobSet-based sniffer.
///
/// Compiles 1600+ patterns into a single DFA for O(1) matching per file.
///
/// # Example
///
/// ```python
/// from omni_core_rs import PyGlobSniffer
///
/// rules = [
///     {"id": "python", "patterns": ["*.py", "pyproject.toml"]},
///     {"id": "rust", "patterns": ["*.rs", "Cargo.toml"]},
/// ]
///
/// sniffer = PyGlobSniffer(rules)
/// contexts = sniffer.sniff_workspace("/path/to/project", max_depth=5)
/// ```
#[pyclass]
#[derive(Clone)]
pub struct PyGlobSniffer {
    engine: SnifferEngine,
}

#[pymethods]
impl PyGlobSniffer {
    /// Create a new GlobSniffer from rules.
    ///
    /// Args:
    ///     rules: List of dicts with 'id', 'patterns', and optional 'weight'
    ///
    /// Example:
    ///     rules = [
    ///         {"id": "python", "patterns": ["*.py"], "weight": 1.0},
    ///         {"id": "rust", "patterns": ["*.rs"], "weight": 1.0},
    ///     ]
    #[new]
    #[pyo3(signature = (rules))]
    pub fn new(_py: Python, rules: Bound<'_, PyList>) -> PyResult<Self> {
        let mut rust_rules: Vec<SnifferRule> = Vec::with_capacity(rules.len());

        for item in rules.iter() {
            let rule_dict: Bound<'_, PyDict> = item.extract()?;

            // get_item returns Result<Option<Bound<PyAny>>, PyErr>
            let id: String = if let Ok(Some(id_any)) = rule_dict.get_item("id") {
                id_any.extract()?
            } else {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Rule missing 'id' field",
                ));
            };

            let patterns_any: Bound<'_, PyAny> =
                if let Ok(Some(patterns_item)) = rule_dict.get_item("patterns") {
                    patterns_item
                } else {
                    return Err(pyo3::exceptions::PyValueError::new_err(
                        "Rule missing 'patterns' field",
                    ));
                };

            let patterns: Vec<String> = if patterns_any.is_instance_of::<PyList>() {
                let patterns_list: Bound<'_, PyList> = patterns_any.extract()?;
                patterns_list
                    .iter()
                    .map(|p: Bound<'_, PyAny>| p.extract::<String>())
                    .collect::<Result<Vec<_>, _>>()?
            } else {
                vec![patterns_any.extract::<String>()?]
            };

            let weight: f32 = match rule_dict.get_item("weight") {
                Ok(Some(w)) => w.extract::<f32>().unwrap_or(1.0),
                _ => 1.0,
            };

            rust_rules.push(SnifferRule::with_weight(id, patterns, weight));
        }

        let engine = SnifferEngine::new(rust_rules).map_err(|e| {
            pyo3::exceptions::PyValueError::new_err(format!(
                "Failed to compile glob patterns: {}",
                e
            ))
        })?;

        Ok(PyGlobSniffer { engine })
    }

    /// Create from JSON string (for loading from LanceDB).
    ///
    /// Args:
    ///     json_str: JSON array of rule objects
    #[staticmethod]
    #[pyo3(signature = (json_str))]
    pub fn from_json(json_str: &str) -> PyResult<Self> {
        let engine = SnifferEngine::from_json(json_str)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {}", e)))?;
        Ok(PyGlobSniffer { engine })
    }

    /// Get pattern and context counts.
    #[getter]
    fn pattern_count(&self) -> usize {
        self.engine.pattern_count()
    }

    #[getter]
    fn context_count(&self) -> usize {
        self.engine.context_count()
    }

    /// Scan workspace directory for active contexts.
    ///
    /// Uses parallel WalkDir + GlobSet for high performance.
    ///
    /// Args:
    ///     root_path: Directory to scan
    ///     max_depth: Maximum directory depth (default: 5)
    ///
    /// Returns:
    ///     List of context IDs sorted alphabetically
    fn sniff_workspace(&self, root_path: String, max_depth: Option<usize>) -> Vec<String> {
        let depth = max_depth.unwrap_or(5);
        self.engine.sniff_path(&root_path, depth)
    }

    /// Scan with scoring (contexts sorted by weight).
    ///
    /// Args:
    ///     root_path: Directory to scan
    ///     max_depth: Maximum directory depth (default: 5)
    ///
    /// Returns:
    ///     List of (context_id, score) tuples sorted by score descending
    fn sniff_workspace_with_scores(
        &self,
        root_path: String,
        max_depth: Option<usize>,
    ) -> Vec<(String, f32)> {
        let depth = max_depth.unwrap_or(5);
        self.engine.sniff_path_with_scores(&root_path, depth)
    }

    /// Check a single file path (for file watcher events).
    ///
    /// Args:
    ///     relative_path: File path relative to workspace root
    ///
    /// Returns:
    ///     List of matching context IDs
    fn sniff_file(&self, relative_path: String) -> Vec<String> {
        self.engine.sniff_file(&relative_path)
    }

    /// Check a single file with scoring.
    ///
    /// Args:
    ///     relative_path: File path relative to workspace root
    ///
    /// Returns:
    ///     List of (context_id, weight) tuples
    fn sniff_file_with_weights(&self, relative_path: String) -> Vec<(String, f32)> {
        self.engine.sniff_file_with_weights(&relative_path)
    }

    /// Quick check if any context would be detected.
    ///
    /// Faster than full scan - stops at first match.
    fn has_any_context(&self, root_path: String, max_depth: Option<usize>) -> bool {
        let depth = max_depth.unwrap_or(5);
        self.engine.has_any_context(&root_path, depth)
    }
}
