//! Code Navigation - The Cartographer / The Hunter
//!
//! Provides AST-based code navigation and structural search capabilities.

use omni_tags::{SearchConfig, TagExtractor};
use pyo3::prelude::*;

/// Generate a symbolic outline for a file using AST patterns.
/// Returns formatted string showing only definitions (classes, functions, etc.)
/// This is the primary interface for CCA-aligned code navigation.
#[pyfunction]
#[pyo3(signature = (path, language = None))]
pub fn get_file_outline(path: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::outline_file(&path, language)
                .unwrap_or_else(|e| format!("[Error generating outline: {}]", e))
        })
    })
}

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
pub fn search_code(path: String, pattern: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::search_file(&path, &pattern, language)
                .unwrap_or_else(|e| format!("[Search error: {}]", e))
        })
    })
}

/// Search for AST patterns using complex YAML rules.
///
/// This allows for sophisticated queries with constraints like 'inside', 'has', 'not'.
///
/// Args:
///   path: File path to search
///   yaml_rule: ast-grep rule in YAML format
///   language: Optional language hint
#[pyfunction]
#[pyo3(signature = (path, yaml_rule, language = None))]
pub fn search_with_rules(path: String, yaml_rule: String, language: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            TagExtractor::search_with_rules(&path, &yaml_rule, language)
                .unwrap_or_else(|e| format!("[Rule search error: {}]", e))
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
pub fn search_directory(path: String, pattern: String, file_pattern: Option<&str>) -> String {
    Python::attach(|py| {
        py.detach(|| {
            let config = SearchConfig {
                file_pattern: file_pattern.unwrap_or("**/*").to_string(),
                ..Default::default()
            };
            TagExtractor::search_directory(&path, &pattern, config)
                .unwrap_or_else(|e| format!("[Search error: {}]", e))
        })
    })
}
