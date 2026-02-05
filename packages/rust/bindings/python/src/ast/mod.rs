//! AST-based code extraction Python bindings.
//!
//! Provides Python-accessible functions for extracting code elements
//! from source files using ast-grep patterns.

use pyo3::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Code chunk for semantic partitioning (Python binding)
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyCodeChunk {
    /// Chunk identifier
    pub id: String,
    /// Chunk type (function, class, etc.)
    pub chunk_type: String,
    /// Raw code content
    pub content: String,
    /// Byte offset start
    pub start: usize,
    /// Byte offset end
    pub end: usize,
    /// Line number start (1-indexed)
    pub line_start: usize,
    /// Line number end (1-indexed)
    pub line_end: usize,
    /// Captured metadata
    pub metadata: HashMap<String, String>,
    /// Docstring/comment content
    pub docstring: Option<String>,
}

impl From<omni_ast::CodeChunk> for PyCodeChunk {
    fn from(chunk: omni_ast::CodeChunk) -> Self {
        Self {
            id: chunk.id,
            chunk_type: chunk.chunk_type,
            content: chunk.content,
            start: chunk.start,
            end: chunk.end,
            line_start: chunk.line_start,
            line_end: chunk.line_end,
            metadata: chunk.metadata,
            docstring: chunk.docstring,
        }
    }
}

#[pymethods]
impl PyCodeChunk {
    #[getter]
    fn id(&self) -> String {
        self.id.clone()
    }

    #[getter]
    fn chunk_type(&self) -> String {
        self.chunk_type.clone()
    }

    #[getter]
    fn content(&self) -> String {
        self.content.clone()
    }

    #[getter]
    fn start(&self) -> usize {
        self.start
    }

    #[getter]
    fn end(&self) -> usize {
        self.end
    }

    #[getter]
    fn line_start(&self) -> usize {
        self.line_start
    }

    #[getter]
    fn line_end(&self) -> usize {
        self.line_end
    }

    #[getter]
    fn metadata(&self) -> HashMap<String, String> {
        self.metadata.clone()
    }

    #[getter]
    fn docstring(&self) -> Option<String> {
        self.docstring.clone()
    }
}

/// Extract result struct for Python
#[pyclass]
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PyExtractResult {
    /// Matched code text
    pub text: String,
    /// Byte offset start
    pub start: usize,
    /// Byte offset end
    pub end: usize,
    /// Line number start (1-indexed)
    pub line_start: usize,
    /// Line number end (1-indexed)
    pub line_end: usize,
    /// Captured variables
    pub captures: HashMap<String, String>,
}

impl From<omni_ast::ExtractResult> for PyExtractResult {
    fn from(result: omni_ast::ExtractResult) -> Self {
        Self {
            text: result.text,
            start: result.start,
            end: result.end,
            line_start: result.line_start,
            line_end: result.line_end,
            captures: result.captures,
        }
    }
}

#[pymethods]
impl PyExtractResult {
    #[getter]
    fn text(&self) -> String {
        self.text.clone()
    }

    #[getter]
    fn start(&self) -> usize {
        self.start
    }

    #[getter]
    fn end(&self) -> usize {
        self.end
    }

    #[getter]
    fn line_start(&self) -> usize {
        self.line_start
    }

    #[getter]
    fn line_end(&self) -> usize {
        self.line_end
    }

    #[getter]
    fn captures(&self) -> HashMap<String, String> {
        self.captures.clone()
    }
}

/// Extract code elements from content using an ast-grep pattern.
///
/// Args:
///     content: Source code to search
///     pattern: ast-grep pattern (e.g., "def $NAME")
///     language: Programming language (e.g., "python", "rust")
///     captures: Optional list of capture names to include
///
/// Returns:
///     JSON string containing list of extraction results
#[pyfunction]
#[pyo3(signature = (content, pattern, language, captures = None))]
pub fn py_extract_items(
    content: String,
    pattern: String,
    language: String,
    captures: Option<Vec<String>>,
) -> PyResult<String> {
    let lang: omni_ast::Lang = language
        .as_str()
        .try_into()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid language: {}", e)))?;

    let capture_opts: Option<Vec<&str>> = captures
        .as_ref()
        .map(|v| v.iter().map(|s| s.as_str()).collect());

    let results = omni_ast::extract_items(&content, &pattern, lang, capture_opts);

    let py_results: Vec<PyExtractResult> = results.into_iter().map(Into::into).collect();

    serde_json::to_string(&py_results).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization failed: {}", e))
    })
}

/// Parse language string and return supported status.
///
/// Args:
///     language: Programming language string
///
/// Returns:
///     True if language is supported, False otherwise
#[pyfunction]
pub fn py_is_language_supported(language: String) -> bool {
    <&str as TryInto<omni_ast::Lang>>::try_into(language.as_str()).is_ok()
}

/// Get list of supported languages.
///
/// Returns:
///     List of supported language names
#[pyfunction]
pub fn py_get_supported_languages() -> Vec<String> {
    vec![
        "python".to_string(),
        "rust".to_string(),
        "javascript".to_string(),
        "typescript".to_string(),
        "bash".to_string(),
        "go".to_string(),
        "java".to_string(),
        "c".to_string(),
        "cpp".to_string(),
        "csharp".to_string(),
        "ruby".to_string(),
        "swift".to_string(),
        "kotlin".to_string(),
        "lua".to_string(),
        "php".to_string(),
        "json".to_string(),
        "yaml".to_string(),
        "toml".to_string(),
        "markdown".to_string(),
        "dockerfile".to_string(),
        "html".to_string(),
        "css".to_string(),
        "sql".to_string(),
    ]
}

/// Chunk source code into semantic units based on AST patterns.
///
/// Args:
///     content: Source code content
///     file_path: Path to the file (for ID generation)
///     language: Programming language (e.g., "python", "rust")
///     patterns: AST patterns to match (e.g., ["def $NAME", "class $NAME"])
///     min_lines: Minimum lines for a chunk to be included (default: 1)
///     max_lines: Maximum lines for a chunk (0 = no limit, default: 0)
///
/// Returns:
///     List of CodeChunk objects
#[pyfunction]
#[pyo3(signature = (content, file_path, language, patterns, min_lines = 1, max_lines = 0))]
pub fn py_chunk_code(
    content: String,
    file_path: String,
    language: String,
    patterns: Vec<String>,
    min_lines: usize,
    max_lines: usize,
) -> PyResult<Vec<PyCodeChunk>> {
    let lang: omni_ast::Lang = language
        .as_str()
        .try_into()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid language: {}", e)))?;

    let pattern_refs: Vec<&str> = patterns.iter().map(|s| s.as_str()).collect();

    let chunks = omni_ast::chunk_code(
        &content,
        &file_path,
        lang,
        &pattern_refs,
        min_lines,
        max_lines,
    )
    .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("Chunking failed: {}", e)))?;

    Ok(chunks.into_iter().map(Into::into).collect())
}

/// Extract skeleton (signatures + docstrings) from source code.
///
/// This function extracts only structural definitions (function signatures,
/// class definitions) along with their docstrings, removing implementation bodies.
/// Ideal for lightweight semantic indexing where full code content is not needed.
///
/// Args:
///     content: Source code content
///     language: Programming language (e.g., "python", "rust")
///
/// Returns:
///     JSON string containing {"skeleton": "...", "items_count": N}
#[pyfunction]
#[pyo3(signature = (content, language))]
pub fn py_extract_skeleton(content: String, language: String) -> PyResult<String> {
    let lang: omni_ast::Lang = language
        .as_str()
        .try_into()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid language: {}", e)))?;

    let skeleton = omni_ast::extract_skeleton(&content, lang);

    // Count items (separated by double newlines)
    let items_count = skeleton.split("\n\n").filter(|s| !s.is_empty()).count();

    let result = serde_json::json!({
        "skeleton": skeleton,
        "items_count": items_count,
    });

    serde_json::to_string(&result).map_err(|e| {
        pyo3::exceptions::PyRuntimeError::new_err(format!("JSON serialization failed: {}", e))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use pyo3::types::PyList;

    #[test]
    fn test_extract_items_python() {
        let content = r#"
def hello(name: str) -> str:
    return f"Hello, {name}!"

def goodbye():
    pass
"#;

        let json = py_extract_items(
            content.to_string(),
            "def $NAME".to_string(),
            "python".to_string(),
            None,
        )
        .unwrap();

        let results: Vec<PyExtractResult> = serde_json::from_str(&json).unwrap();
        assert_eq!(results.len(), 2);
    }
}
