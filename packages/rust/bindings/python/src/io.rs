//! Safe I/O and Tokenization
//!
//! Provides high-performance file reading and token counting for Python.

use anyhow;
use omni_io;
use omni_tokenizer;
use pyo3::prelude::*;

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
