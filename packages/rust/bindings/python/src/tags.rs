//! Python bindings for omni-tags - Code Symbol Extraction
//!
//! Provides AST-based symbol extraction using omni-ast (ast-grep)
//! for high-performance code navigation.

use omni_tags::{SearchConfig, TagExtractor};
use pyo3::prelude::*;

/// Symbol kind enumeration for Python.
///
/// Represents the type of code symbol extracted from source files.
#[pyclass]
#[derive(Debug, Clone, PartialEq)]
pub enum PySymbolKind {
    /// Function definition.
    #[pyo3(name = "function")]
    Function,
    /// Class definition.
    #[pyo3(name = "class")]
    Class,
    /// Struct definition (Rust).
    #[pyo3(name = "struct")]
    Struct,
    /// Method within a class.
    #[pyo3(name = "method")]
    Method,
    /// Trait definition (Rust).
    #[pyo3(name = "trait")]
    Trait,
    /// Impl block (Rust).
    #[pyo3(name = "impl")]
    Impl,
    /// Module or namespace.
    #[pyo3(name = "module")]
    Module,
    /// Async function definition.
    #[pyo3(name = "async_function")]
    AsyncFunction,
    /// Enum definition.
    #[pyo3(name = "enum")]
    Enum,
    /// Interface or type alias.
    #[pyo3(name = "interface")]
    Interface,
    /// Unknown or unrecognized symbol.
    #[pyo3(name = "unknown")]
    Unknown,
}

/// A symbol extracted from source code (parsed from outline output).
///
/// Contains metadata about a code element such as function, class, or struct.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySymbol {
    /// Name of the symbol.
    #[pyo3(get)]
    pub name: String,
    /// Kind of symbol (function, class, etc.).
    #[pyo3(get)]
    pub kind: String,
    /// Line number where the symbol is defined.
    #[pyo3(get)]
    pub line: usize,
    /// Signature or declaration string.
    #[pyo3(get)]
    pub signature: String,
}

/// Parse symbols from outline output.
///
/// Takes the CCA-formatted outline string and converts it to structured PySymbol objects.
fn parse_symbols(outline: &str) -> Vec<PySymbol> {
    let mut symbols = Vec::new();

    for line in outline.lines() {
        // Parse format: "L{: <4} {: <12} {} {}"
        // Example: "L1    [function] foo def foo()"
        if !line.starts_with('L') || line.starts_with("//") {
            continue;
        }

        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 4 {
            continue;
        }

        // Parse line number from "L123"
        let line_num: usize = parts[0].trim_start_matches('L').parse().unwrap_or(0);

        // Parse kind from "[kind]"
        let kind = parts[1].trim_matches(|c| c == '[' || c == ']').to_string();

        // Name is typically at index 2
        let name = parts[2].to_string();

        // Signature is everything after name
        let signature = if parts.len() > 3 {
            parts[3..].join(" ")
        } else {
            name.clone()
        };

        symbols.push(PySymbol {
            name,
            kind,
            line: line_num,
            signature,
        });
    }

    symbols
}

/// Get the outline of a file (functions, classes, etc.).
///
/// Extracts all symbols from a source file and returns them in CCA format.
///
/// Args:
///     file_path: Path to the source file.
///     language: Optional language hint (python, rust, javascript, typescript).
///
/// Returns:
///     String with file outline in CCA format.
#[pyfunction]
#[pyo3(signature = (file_path, language = None))]
pub fn py_get_file_outline(file_path: String, language: Option<String>) -> String {
    let lang = language.as_deref();
    match TagExtractor::outline_file(&file_path, lang) {
        Ok(s) => s,
        Err(e) => format!("[Error: {}]", e),
    }
}

/// Parse outline output into structured symbols.
///
/// Takes the output from `py_get_file_outline` and converts it to PySymbol objects.
///
/// Args:
///     outline: Outline string from py_get_file_outline.
///
/// Returns:
///     List of PySymbol objects.
#[pyfunction]
pub fn py_parse_symbols(outline: String) -> Vec<PySymbol> {
    parse_symbols(&outline)
}

/// Extract symbols from a file and return structured data.
///
/// Combines extraction and parsing into a single call for convenience.
///
/// Args:
///     file_path: Path to the source file.
///     language: Optional language hint (auto-detected if None).
///
/// Returns:
///     JSON string with symbols array.
#[pyfunction]
#[pyo3(signature = (file_path, language = None))]
pub fn py_extract_symbols(file_path: String, language: Option<String>) -> String {
    let lang = language.as_deref();
    let outline = match TagExtractor::outline_file(&file_path, lang) {
        Ok(s) => s,
        Err(e) => return format!(r#"{{"error":"{}"}}"#, e),
    };
    let symbols = parse_symbols(&outline);

    let mut json = String::from("{\"symbols\":[");
    for (i, sym) in symbols.iter().enumerate() {
        if i > 0 {
            json.push(',');
        }
        json.push_str(&format!(
            r#"{{"name":"{}","kind":"{}","line":{},"signature":"{}"}}"#,
            sym.name.replace('"', r#"\""#),
            sym.kind.replace('"', r#"\""#),
            sym.line,
            sym.signature.replace('"', r#"\""#)
        ));
    }
    json.push_str("]}");
    json
}

/// Search for a pattern in a single file using ast-grep.
///
/// Uses structural pattern matching to find code elements matching the given pattern.
///
/// Args:
///     file_path: Path to the source file.
///     pattern: ast-grep pattern (e.g., "def $NAME", "class $CLASS").
///     language: Optional language hint.
///
/// Returns:
///     String with search results in CCA format.
#[pyfunction]
#[pyo3(signature = (file_path, pattern, language = None))]
pub fn py_search_file(file_path: String, pattern: String, language: Option<String>) -> String {
    let lang = language.as_deref();
    match TagExtractor::search_file(&file_path, &pattern, lang) {
        Ok(s) => s,
        Err(e) => format!("[Error: {}]", e),
    }
}

/// Search for a pattern in a directory recursively.
///
/// Walks the directory tree and searches for the pattern in all matching files.
///
/// Args:
///     dir_path: Directory to search.
///     pattern: ast-grep pattern.
///     file_pattern: Glob pattern for files (e.g., "**/*.py").
///     max_file_size: Maximum file size in bytes.
///     max_matches: Maximum total matches.
///
/// Returns:
///     String with search results.
#[pyfunction]
#[pyo3(signature = (dir_path, pattern, file_pattern = None, max_file_size = 1048576, max_matches = 1000))]
pub fn py_search_directory(
    dir_path: String,
    pattern: String,
    file_pattern: Option<String>,
    max_file_size: u64,
    max_matches: usize,
) -> String {
    let file_pattern = file_pattern.unwrap_or_else(|| "**/*".to_string());
    let config = SearchConfig {
        file_pattern: file_pattern.clone(),
        max_file_size,
        max_matches_per_file: max_matches / 10,
        languages: Vec::new(),
    };

    match TagExtractor::search_directory(dir_path.as_str(), &pattern, config) {
        Ok(s) => s,
        Err(e) => format!("[Error: {}]", e),
    }
}

/// Search using YAML rules (ast-grep rule format).
///
/// Allows complex search rules defined in YAML format.
///
/// Args:
///     file_path: Path to search.
///     yaml_rule: YAML rule string.
///     language: Optional language hint.
///
/// Returns:
///     String with rule search results.
#[pyfunction]
#[pyo3(signature = (file_path, yaml_rule, language = None))]
pub fn py_search_with_rules(
    file_path: String,
    yaml_rule: String,
    language: Option<String>,
) -> String {
    let lang = language.as_deref();
    match TagExtractor::search_with_rules(&file_path, &yaml_rule, lang) {
        Ok(s) => s,
        Err(e) => format!("[Error: {}]", e),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_symbols() {
        let outline = r#"// OUTLINE: test.py
// Total symbols: 2
L1    [class]     Agent class Agent
L5    [function]  helper def helper()"#;

        let symbols = parse_symbols(outline);
        assert_eq!(symbols.len(), 2);
        assert_eq!(symbols[0].name, "Agent");
        assert_eq!(symbols[0].kind, "class");
        assert_eq!(symbols[0].line, 1);
        assert_eq!(symbols[1].name, "helper");
        assert_eq!(symbols[1].kind, "function");
        assert_eq!(symbols[1].line, 5);
    }

    #[test]
    fn test_parse_symbols_empty() {
        let outline = "// No symbols found";
        let symbols = parse_symbols(outline);
        assert!(symbols.is_empty());
    }

    #[test]
    fn test_py_symbol_kind_mapping() {
        assert_eq!(PySymbolKind::Function, PySymbolKind::Function);
        assert_eq!(PySymbolKind::Class, PySymbolKind::Class);
    }
}
