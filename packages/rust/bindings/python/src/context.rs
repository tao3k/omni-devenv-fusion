//! Python bindings for Context Assembler.
//!
//! Provides Python API for assembling skill context with parallel I/O,
//! template rendering, and token counting.

use omni_tokenizer::{ContextPruner, Message};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::path::PathBuf;

/// Result of assembling skill context.
#[pyclass(name = "AssemblyResult")]
pub struct PyAssemblyResult {
    /// The assembled content string with template variables rendered.
    #[pyo3(get)]
    pub content: String,
    /// Token count of the assembled content.
    #[pyo3(get)]
    pub token_count: usize,
    /// List of reference file paths that could not be read.
    #[pyo3(get)]
    pub missing_refs: Vec<String>,
}

/// Context assembler for skill protocols.
///
/// Combines parallel I/O, template rendering, and token counting
/// for efficient context hydration.
///
/// # Example
///
/// ```python
/// from omni_core_rs import ContextAssembler
///
/// assembler = ContextAssembler()
/// content, tokens, missing = assembler.assemble(
///     "/path/to/SKILL.md",
///     ["/path/to/ref.md"],
///     '{"name": "World"}'
/// )
/// ```
#[pyclass(name = "ContextAssembler")]
pub struct PyContextAssembler {
    inner: omni_io::ContextAssembler,
}

#[pymethods]
impl PyContextAssembler {
    #[new]
    fn new() -> Self {
        Self {
            inner: omni_io::ContextAssembler::new(),
        }
    }

    /// Assemble skill context from main file and references.
    ///
    /// # Arguments
    ///
    /// * `main_path` - Path to the main SKILL.md file
    /// * `ref_paths` - List of paths to reference files
    /// * `variables_json` - JSON string with template variables
    ///
    /// # Returns
    ///
    /// Tuple of (content, token_count, missing_refs)
    fn assemble(
        &self,
        main_path: String,
        ref_paths: Vec<String>,
        variables_json: String,
    ) -> PyResult<(String, usize, Vec<String>)> {
        let m_path = PathBuf::from(main_path);
        let r_paths: Vec<PathBuf> = ref_paths.into_iter().map(PathBuf::from).collect();

        let variables: serde_json::Value = serde_json::from_str(&variables_json)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

        let result = self
            .inner
            .assemble_skill(m_path, r_paths, variables)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

        let missing: Vec<String> = result
            .missing_refs
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect();

        Ok((result.content, result.token_count, missing))
    }

    /// Assemble skill context and return structured result.
    ///
    /// # Returns
    ///
    /// AssemblyResult object with content, token_count, and missing_refs
    fn assemble_structured(
        &self,
        main_path: String,
        ref_paths: Vec<String>,
        variables_json: String,
    ) -> PyResult<PyAssemblyResult> {
        let m_path = PathBuf::from(main_path);
        let r_paths: Vec<PathBuf> = ref_paths.into_iter().map(PathBuf::from).collect();

        let variables: serde_json::Value = serde_json::from_str(&variables_json)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

        let result = self
            .inner
            .assemble_skill(m_path, r_paths, variables)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyIOError, _>(e.to_string()))?;

        let missing: Vec<String> = result
            .missing_refs
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect();

        Ok(PyAssemblyResult {
            content: result.content,
            token_count: result.token_count,
            missing_refs: missing,
        })
    }
}

/// Context pruner for message history compression.
#[pyclass]
pub struct PyContextPruner {
    inner: ContextPruner,
}

#[pymethods]
impl PyContextPruner {
    #[new]
    fn new(window_size: usize, max_tool_output: usize) -> Self {
        Self {
            inner: ContextPruner::new(window_size, max_tool_output),
        }
    }

    fn compress(&self, py: Python, messages: Py<PyAny>) -> PyResult<Py<PyAny>> {
        // Modern PyO3 API: bind() to get Bound<PyAny>, then cast
        let list = messages
            .bind(py)
            .cast::<PyList>()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyTypeError, _>(e.to_string()))?;

        let mut rust_msgs = Vec::with_capacity(list.len());

        for item in list {
            let dict = item.cast::<PyDict>().map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyTypeError, _>(format!("Item not a dict: {}", e))
            })?;

            let role: String = dict
                .get_item("role")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing role"))?
                .extract()?;

            let content: String = dict
                .get_item("content")?
                .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing content"))?
                .extract()?;

            rust_msgs.push(Message { role, content });
        }

        // Run Logic in Rust
        let processed = self.inner.compress(rust_msgs);

        // Rust Vec<Message> -> Python List[Dict]
        let result_list = PyList::empty(py);
        for msg in processed {
            let dict = PyDict::new(py);
            dict.set_item("role", msg.role)?;
            dict.set_item("content", msg.content)?;
            result_list.append(dict)?;
        }

        Ok(result_list.into())
    }
}
