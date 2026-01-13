use pyo3::prelude::*;
use omni_sniffer::OmniSniffer;
use omni_io::{self, IoError};
use omni_tokenizer;
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
    m.add("VERSION", "0.2.0")?;
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
    Python::with_gil(|py| {
        py.allow_threads(|| {
            omni_io::read_text_safe(path, max_bytes)
                .map_err(|e| anyhow::anyhow!(e))
        })
    }).map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
/// Releases GIL for CPU-intensive tokenization.
#[pyfunction]
fn count_tokens(text: &str) -> usize {
    Python::with_gil(|py| {
        py.allow_threads(|| {
            omni_tokenizer::count_tokens(text)
        })
    })
}

/// Truncate text to fit within a maximum token count.
/// Releases GIL for CPU-intensive tokenization.
#[pyfunction]
#[pyo3(signature = (text, max_tokens))]
fn truncate_tokens(text: &str, max_tokens: usize) -> String {
    Python::with_gil(|py| {
        py.allow_threads(|| {
            omni_tokenizer::truncate(text, max_tokens)
        })
    })
}
