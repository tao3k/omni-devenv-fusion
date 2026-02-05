//! Safe I/O and Tokenization
//!
//! Provides high-performance file reading and token counting for Python.

use anyhow;
use omni_io;
use omni_tokenizer;
use pyo3::prelude::*;

/// Options for file discovery.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyDiscoverOptions {
    /// File extensions to include (e.g., [".py", ".md"])
    #[pyo3(get, set)]
    pub extensions: Vec<String>,
    /// Maximum file size in bytes (default: 1MB)
    #[pyo3(get, set)]
    pub max_file_size: u64,
    /// Skip hidden files and directories
    #[pyo3(get, set)]
    pub skip_hidden: bool,
    /// Skip directories by name (e.g., ["target", "node_modules"])
    #[pyo3(get, set)]
    pub skip_dirs: Vec<String>,
    /// Maximum files to return (None for unlimited)
    #[pyo3(get, set)]
    pub max_files: Option<usize>,
    /// Include subdirectories recursively
    #[pyo3(get, set)]
    pub recursive: bool,
}

#[pymethods]
impl PyDiscoverOptions {
    #[new]
    #[pyo3(signature = (extensions, max_file_size = 1048576, skip_hidden = true, skip_dirs = None, max_files = None, recursive = true))]
    fn new(
        extensions: Vec<String>,
        max_file_size: u64,
        skip_hidden: bool,
        skip_dirs: Option<Vec<String>>,
        max_files: Option<usize>,
        recursive: bool,
    ) -> Self {
        Self {
            extensions,
            max_file_size,
            skip_hidden,
            skip_dirs: skip_dirs
                .unwrap_or_else(|| vec!["target".to_string(), "node_modules".to_string()]),
            max_files,
            recursive,
        }
    }
}

impl From<PyDiscoverOptions> for omni_io::DiscoverOptions {
    fn from(py_opts: PyDiscoverOptions) -> Self {
        Self {
            extensions: py_opts.extensions,
            max_file_size: py_opts.max_file_size,
            skip_hidden: py_opts.skip_hidden,
            skip_dirs: py_opts.skip_dirs,
            max_files: py_opts.max_files,
            recursive: py_opts.recursive,
        }
    }
}

/// Safely read a text file with size and binary checks.
/// Releases GIL for CPU-intensive file operations.
#[pyfunction]
#[pyo3(signature = (path, max_bytes = 1048576))]
pub fn read_file_safe(path: String, max_bytes: u64) -> PyResult<String> {
    Python::attach(|py| {
        py.detach(|| omni_io::read_text_safe(path, max_bytes).map_err(|e| anyhow::anyhow!(e)))
    })
    .map_err(|e| pyo3::PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))
}

/// Discover files in a directory matching extensions.
#[pyfunction]
#[pyo3(signature = (root, extensions, max_file_size = 1048576, skip_hidden = true, skip_dirs = None, recursive = true))]
pub fn discover_files(
    root: &str,
    extensions: Vec<String>,
    max_file_size: u64,
    skip_hidden: bool,
    skip_dirs: Option<Vec<String>>,
    recursive: bool,
) -> Vec<String> {
    let skip_dirs =
        skip_dirs.unwrap_or_else(|| vec!["target".to_string(), "node_modules".to_string()]);
    let options = omni_io::DiscoverOptions {
        extensions,
        max_file_size,
        skip_hidden,
        skip_dirs,
        max_files: None,
        recursive,
    };
    omni_io::discover_files(root, &options)
}

/// Discover files in a single directory (non-recursive).
#[pyfunction]
#[pyo3(signature = (dir, extensions, max_file_size = 1048576, skip_hidden = true))]
pub fn discover_files_in_dir(
    dir: &str,
    extensions: Vec<String>,
    max_file_size: u64,
    skip_hidden: bool,
) -> Vec<String> {
    omni_io::discover_files_in_dir(dir, &extensions, max_file_size, skip_hidden)
}

/// Count files matching extensions in a directory.
#[pyfunction]
#[pyo3(signature = (dir, extensions, skip_hidden = true))]
pub fn count_files_in_dir(dir: &str, extensions: Vec<String>, skip_hidden: bool) -> usize {
    omni_io::count_files_in_dir(dir, &extensions, skip_hidden)
}

/// Check if a path should be skipped.
#[pyfunction]
#[pyo3(signature = (path, skip_hidden = true, skip_dirs = None))]
pub fn should_skip_path(path: &str, skip_hidden: bool, skip_dirs: Option<Vec<String>>) -> bool {
    let skip_dirs =
        skip_dirs.unwrap_or_else(|| vec!["target".to_string(), "node_modules".to_string()]);
    omni_io::should_skip_path(path, skip_hidden, &skip_dirs)
}

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
/// Uses cached BPE instance for optimal performance.
#[pyfunction]
pub fn count_tokens(text: &str) -> usize {
    omni_tokenizer::count_tokens(text)
}

/// Truncate text to fit within a maximum token count.
/// Uses cached BPE instance for optimal performance.
#[pyfunction]
#[pyo3(signature = (text, max_tokens))]
pub fn truncate_tokens(text: &str, max_tokens: usize) -> String {
    omni_tokenizer::truncate(text, max_tokens)
}

/// Get PRJ_CONFIG_HOME from Rust side (PRJ_SPEC Compliance).
/// This allows Python to verify that Rust reads the same env var.
#[pyfunction]
pub fn get_config_home() -> String {
    omni_io::get_config_home()
}

/// Get PRJ_DATA_HOME from Rust side.
#[pyfunction]
pub fn get_data_home() -> String {
    omni_io::get_data_home()
}

/// Get PRJ_CACHE_HOME from Rust side.
#[pyfunction]
pub fn get_cache_home() -> String {
    omni_io::get_cache_home()
}
