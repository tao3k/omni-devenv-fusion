//! `PyO3` bindings for `UnifiedSymbolIndex`.
//!
//! This module provides Python bindings for searching across both project symbols
//! and external dependency symbols in a unified way.

use crate::unified_symbol::{SymbolSource, UnifiedIndexStats, UnifiedSymbol, UnifiedSymbolIndex};
use omni_macros::py_from;
use pyo3::prelude::*;

/// Python wrapper for `UnifiedSymbol`
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyUnifiedSymbol {
    inner: UnifiedSymbol,
}

#[pymethods]
impl PyUnifiedSymbol {
    #[new]
    #[pyo3(signature = (name, kind, location, source, crate_name))]
    fn new(name: &str, kind: &str, location: &str, source: &str, crate_name: &str) -> Self {
        let _source = if source == "project" {
            SymbolSource::Project
        } else {
            SymbolSource::External(source.to_string())
        };
        Self {
            inner: UnifiedSymbol::new_external(name, kind, location, crate_name),
        }
    }

    #[getter]
    fn name(&self) -> String {
        self.inner.name.clone()
    }

    #[getter]
    fn kind(&self) -> String {
        self.inner.kind.clone()
    }

    #[getter]
    fn location(&self) -> String {
        self.inner.location.clone()
    }

    #[getter]
    fn crate_name(&self) -> String {
        self.inner.crate_name.clone()
    }

    #[getter]
    fn is_external(&self) -> bool {
        self.inner.is_external()
    }

    #[getter]
    fn is_project(&self) -> bool {
        self.inner.is_project()
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "name": self.inner.name,
            "kind": self.inner.kind,
            "location": self.inner.location,
            "source": if self.inner.is_external() { "external" } else { "project" },
            "crate_name": self.inner.crate_name,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for `UnifiedIndexStats`
#[pyclass]
#[derive(Debug, Default, Clone)]
pub struct PyUnifiedIndexStats {
    inner: UnifiedIndexStats,
}

// Generate From<UnifiedIndexStats> for PyUnifiedIndexStats.
py_from!(PyUnifiedIndexStats, UnifiedIndexStats);

#[pymethods]
impl PyUnifiedIndexStats {
    #[new]
    #[pyo3(signature = (total_symbols, project_symbols, external_symbols, external_crates, project_files_with_externals))]
    fn new(
        total_symbols: usize,
        project_symbols: usize,
        external_symbols: usize,
        external_crates: usize,
        project_files_with_externals: usize,
    ) -> Self {
        Self {
            inner: UnifiedIndexStats {
                total_symbols,
                project_symbols,
                external_symbols,
                external_crates,
                project_files_with_externals,
            },
        }
    }

    #[getter]
    fn total_symbols(&self) -> usize {
        self.inner.total_symbols
    }

    #[getter]
    fn project_symbols(&self) -> usize {
        self.inner.project_symbols
    }

    #[getter]
    fn external_symbols(&self) -> usize {
        self.inner.external_symbols
    }

    #[getter]
    fn external_crates(&self) -> usize {
        self.inner.external_crates
    }

    #[getter]
    fn project_files_with_externals(&self) -> usize {
        self.inner.project_files_with_externals
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "total_symbols": self.inner.total_symbols,
            "project_symbols": self.inner.project_symbols,
            "external_symbols": self.inner.external_symbols,
            "external_crates": self.inner.external_crates,
            "project_files_with_externals": self.inner.project_files_with_externals,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for `UnifiedSymbolIndex`
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyUnifiedSymbolIndex {
    inner: UnifiedSymbolIndex,
}

#[pymethods]
impl PyUnifiedSymbolIndex {
    #[new]
    #[pyo3(signature = ())]
    fn new() -> Self {
        Self {
            inner: UnifiedSymbolIndex::new(),
        }
    }

    /// Add a project symbol.
    #[pyo3(signature = (name, kind, location, crate_name))]
    fn add_project_symbol(&mut self, name: &str, kind: &str, location: &str, crate_name: &str) {
        self.inner
            .add_project_symbol(name, kind, location, crate_name);
    }

    /// Add an external dependency symbol.
    #[pyo3(signature = (name, kind, location, crate_name))]
    fn add_external_symbol(&mut self, name: &str, kind: &str, location: &str, crate_name: &str) {
        self.inner
            .add_external_symbol(name, kind, location, crate_name);
    }

    /// Record usage of an external symbol in a project file.
    #[pyo3(signature = (crate_name, symbol_name, project_file))]
    fn record_external_usage(&mut self, crate_name: &str, symbol_name: &str, project_file: &str) {
        self.inner
            .record_external_usage(crate_name, symbol_name, project_file);
    }

    /// Search across both project and external symbols.
    #[pyo3(signature = (pattern, limit))]
    fn search_unified(&self, pattern: &str, limit: usize) -> Vec<PyUnifiedSymbol> {
        self.inner
            .search_unified(pattern, limit)
            .into_iter()
            .map(|s| PyUnifiedSymbol { inner: s.clone() })
            .collect()
    }

    /// Search only project symbols.
    #[pyo3(signature = (pattern, limit))]
    fn search_project(&self, pattern: &str, limit: usize) -> Vec<PyUnifiedSymbol> {
        self.inner
            .search_project(pattern, limit)
            .into_iter()
            .map(|s| PyUnifiedSymbol { inner: s.clone() })
            .collect()
    }

    /// Search only external symbols.
    #[pyo3(signature = (pattern, limit))]
    fn search_external(&self, pattern: &str, limit: usize) -> Vec<PyUnifiedSymbol> {
        self.inner
            .search_external(pattern, limit)
            .into_iter()
            .map(|s| PyUnifiedSymbol { inner: s.clone() })
            .collect()
    }

    /// Search within a specific crate.
    #[pyo3(signature = (crate_name, pattern, limit))]
    fn search_crate(&self, crate_name: &str, pattern: &str, limit: usize) -> Vec<PyUnifiedSymbol> {
        self.inner
            .search_crate(crate_name, pattern, limit)
            .into_iter()
            .map(|s| PyUnifiedSymbol { inner: s.clone() })
            .collect()
    }

    /// Find where an external crate's symbols are used in the project.
    #[pyo3(signature = (crate_name))]
    fn find_external_usage(&self, crate_name: &str) -> Vec<String> {
        self.inner
            .find_external_usage(crate_name)
            .into_iter()
            .map(std::string::ToString::to_string)
            .collect()
    }

    /// Get all external crates used in the project.
    fn get_external_crates(&self) -> Vec<String> {
        self.inner
            .get_external_crates()
            .into_iter()
            .map(std::string::ToString::to_string)
            .collect()
    }

    /// Get all project crates.
    fn get_project_crates(&self) -> Vec<String> {
        self.inner
            .get_project_crates()
            .into_iter()
            .map(std::string::ToString::to_string)
            .collect()
    }

    /// Get statistics.
    fn stats(&self) -> PyUnifiedIndexStats {
        self.inner.stats().into()
    }

    /// Get stats as JSON.
    fn stats_json(&self) -> String {
        let stats = self.inner.stats();
        serde_json::to_string(&stats).unwrap_or_else(|_| "{}".to_string())
    }

    /// Clear all symbols.
    fn clear(&mut self) {
        self.inner.clear();
    }

    /// Search unified and return JSON.
    #[pyo3(signature = (pattern, limit))]
    fn search_unified_json(&self, pattern: &str, limit: usize) -> String {
        let results = self.inner.search_unified(pattern, limit);
        let json_results: Vec<serde_json::Value> = results
            .iter()
            .map(|s| {
                serde_json::json!({
                    "name": s.name,
                    "kind": s.kind,
                    "location": s.location,
                    "source": if s.is_external() { "external" } else { "project" },
                    "crate_name": s.crate_name,
                })
            })
            .collect();
        serde_json::to_string(&json_results).unwrap_or_else(|_| "[]".to_string())
    }
}

/// Register unified symbol module with Python.
///
/// # Errors
///
/// Returns an error if any class cannot be added to the Python module.
pub fn register_unified_symbol_module(m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<PyUnifiedSymbol>()?;
    m.add_class::<PyUnifiedSymbolIndex>()?;
    m.add_class::<PyUnifiedIndexStats>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_unified_symbol_creation() {
        let mut index = UnifiedSymbolIndex::new();
        index.add_project_symbol("my_func", "fn", "src/lib.rs:42", "mycrate");
        index.add_external_symbol("spawn", "fn", "task_join_set.rs:1", "tokio");

        let results = index.search_unified("spawn", 10);
        assert_eq!(results.len(), 1);
        assert!(results[0].is_external());
        assert_eq!(results[0].crate_name, "tokio");
    }

    #[test]
    fn test_external_usage() {
        let mut index = UnifiedSymbolIndex::new();
        index.record_external_usage("tokio", "spawn", "src/main.rs:10");
        index.record_external_usage("tokio", "spawn", "src/worker.rs:5");

        let usage = index.find_external_usage("tokio");
        assert_eq!(usage.len(), 2);
    }

    #[test]
    fn test_stats() {
        let mut index = UnifiedSymbolIndex::new();
        index.add_project_symbol("func1", "fn", "src/lib.rs:1", "mycrate");
        index.add_project_symbol("func2", "fn", "src/lib.rs:2", "mycrate");
        index.add_external_symbol("spawn", "fn", "task.rs:1", "tokio");

        let stats = index.stats();
        assert_eq!(stats.total_symbols, 3);
        assert_eq!(stats.project_symbols, 2);
        assert_eq!(stats.external_symbols, 1);
    }
}
