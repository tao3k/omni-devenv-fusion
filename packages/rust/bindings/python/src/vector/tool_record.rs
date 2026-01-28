//! Tool Record - Python bindings for tool metadata

use omni_vector::ToolRecord;
use pyo3::prelude::*;

/// Python wrapper for ToolRecord
/// Represents a discovered tool from script scanning.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyToolRecord {
    #[pyo3(get)]
    tool_name: String,
    #[pyo3(get)]
    description: String,
    #[pyo3(get)]
    skill_name: String,
    #[pyo3(get)]
    file_path: String,
    #[pyo3(get)]
    function_name: String,
    #[pyo3(get)]
    execution_mode: String,
    #[pyo3(get)]
    keywords: Vec<String>,
    #[pyo3(get)]
    input_schema: String,
    #[pyo3(get)]
    docstring: String,
    #[pyo3(get)]
    file_hash: String,
    #[pyo3(get)]
    category: String,
}

impl From<&ToolRecord> for PyToolRecord {
    fn from(record: &ToolRecord) -> Self {
        Self {
            tool_name: record.tool_name.clone(),
            description: record.description.clone(),
            skill_name: record.skill_name.clone(),
            file_path: record.file_path.clone(),
            function_name: record.function_name.clone(),
            execution_mode: record.execution_mode.clone(),
            keywords: record.keywords.clone(),
            input_schema: record.input_schema.clone(),
            docstring: record.docstring.clone(),
            file_hash: record.file_hash.clone(),
            category: record.category.clone(),
        }
    }
}

impl From<ToolRecord> for PyToolRecord {
    fn from(record: ToolRecord) -> Self {
        Self::from(&record)
    }
}
