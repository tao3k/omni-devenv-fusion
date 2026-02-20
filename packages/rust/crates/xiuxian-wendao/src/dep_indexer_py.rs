//! PyO3 bindings for dependency indexer.
#![allow(clippy::doc_markdown)]

use pyo3::prelude::*;
use std::path::PathBuf;

use crate::dependency_indexer::{
    ConfigExternalDependency, DependencyBuildConfig, DependencyIndexResult, DependencyIndexer,
    DependencyStats, ExternalSymbol, SymbolIndex, SymbolKind,
};

/// Python wrapper for ExternalSymbol
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyExternalSymbol {
    inner: ExternalSymbol,
}

#[pymethods]
impl PyExternalSymbol {
    #[new]
    fn new(name: &str, kind: &str, file: &str, line: usize, crate_name: &str) -> Self {
        let kind = match kind {
            "struct" => SymbolKind::Struct,
            "enum" => SymbolKind::Enum,
            "trait" => SymbolKind::Trait,
            "fn" => SymbolKind::Function,
            "method" => SymbolKind::Method,
            "field" => SymbolKind::Field,
            "impl" => SymbolKind::Impl,
            "mod" => SymbolKind::Mod,
            "const" => SymbolKind::Const,
            "static" => SymbolKind::Static,
            "type" => SymbolKind::TypeAlias,
            _ => SymbolKind::Unknown,
        };
        Self {
            inner: ExternalSymbol {
                name: name.to_string(),
                kind,
                file: PathBuf::from(file),
                line,
                crate_name: crate_name.to_string(),
            },
        }
    }

    #[getter]
    fn name(&self) -> String {
        self.inner.name.clone()
    }

    #[getter]
    fn kind(&self) -> String {
        match self.inner.kind {
            SymbolKind::Struct => "struct",
            SymbolKind::Enum => "enum",
            SymbolKind::Trait => "trait",
            SymbolKind::Function => "fn",
            SymbolKind::Method => "method",
            SymbolKind::Field => "field",
            SymbolKind::Impl => "impl",
            SymbolKind::Mod => "mod",
            SymbolKind::Const => "const",
            SymbolKind::Static => "static",
            SymbolKind::TypeAlias => "type",
            SymbolKind::Unknown => "unknown",
        }
        .to_string()
    }

    #[getter]
    fn file(&self) -> String {
        self.inner.file.to_string_lossy().to_string()
    }

    #[getter]
    fn line(&self) -> usize {
        self.inner.line
    }

    #[getter]
    fn crate_name(&self) -> String {
        self.inner.crate_name.clone()
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "name": self.inner.name,
            "kind": self.kind(),
            "file": self.file(),
            "line": self.inner.line,
            "crate_name": self.inner.crate_name,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Convert ExternalSymbol to Python-compatible dict
fn symbol_to_dict(sym: &ExternalSymbol) -> serde_json::Value {
    serde_json::json!({
        "name": sym.name,
        "kind": format!("{:?}", sym.kind).to_lowercase(),
        "file": sym.file.to_string_lossy(),
        "line": sym.line,
        "crate_name": sym.crate_name,
    })
}

/// Python wrapper for SymbolIndex
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySymbolIndex {
    inner: SymbolIndex,
}

#[pymethods]
impl PySymbolIndex {
    #[new]
    #[pyo3(signature = ())]
    fn new() -> Self {
        Self {
            inner: SymbolIndex::new(),
        }
    }

    fn search(&self, pattern: &str, limit: usize) -> Vec<PyExternalSymbol> {
        self.inner
            .search(pattern, limit)
            .into_iter()
            .map(|s| PyExternalSymbol { inner: s })
            .collect()
    }

    fn search_crate(&self, crate_name: &str, pattern: &str, limit: usize) -> Vec<PyExternalSymbol> {
        self.inner
            .search_crate(crate_name, pattern, limit)
            .into_iter()
            .map(|s| PyExternalSymbol { inner: s })
            .collect()
    }

    fn get_crates(&self) -> Vec<String> {
        self.inner
            .get_crates()
            .iter()
            .map(std::string::ToString::to_string)
            .collect()
    }

    fn symbol_count(&self) -> usize {
        self.inner.symbol_count()
    }

    fn crate_count(&self) -> usize {
        self.inner.crate_count()
    }

    fn clear(&mut self) {
        self.inner.clear();
    }

    fn serialize(&self) -> String {
        self.inner.serialize()
    }

    fn deserialize(&mut self, data: &str) -> bool {
        self.inner.deserialize(data)
    }

    /// Get results as JSON string
    fn search_json(&self, pattern: &str, limit: usize) -> String {
        let results = self.inner.search(pattern, limit);
        let json_results: Vec<serde_json::Value> = results.iter().map(symbol_to_dict).collect();
        serde_json::to_string(&json_results).unwrap_or_else(|_| "[]".to_string())
    }

    /// Search within crate and return JSON
    fn search_crate_json(&self, crate_name: &str, pattern: &str, limit: usize) -> String {
        let results = self.inner.search_crate(crate_name, pattern, limit);
        let json_results: Vec<serde_json::Value> = results.iter().map(symbol_to_dict).collect();
        serde_json::to_string(&json_results).unwrap_or_else(|_| "[]".to_string())
    }
}

/// Python wrapper for DependencyIndexResult
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyDependencyIndexResult {
    inner: DependencyIndexResult,
}

#[pymethods]
impl PyDependencyIndexResult {
    #[new]
    fn new(
        files_processed: usize,
        total_symbols: usize,
        errors: usize,
        crates_indexed: usize,
        error_details: Vec<String>,
    ) -> Self {
        Self {
            inner: DependencyIndexResult {
                files_processed,
                total_symbols,
                errors,
                crates_indexed,
                error_details,
            },
        }
    }

    #[getter]
    fn files_processed(&self) -> usize {
        self.inner.files_processed
    }

    #[getter]
    fn total_symbols(&self) -> usize {
        self.inner.total_symbols
    }

    #[getter]
    fn errors(&self) -> usize {
        self.inner.errors
    }

    #[getter]
    fn crates_indexed(&self) -> usize {
        self.inner.crates_indexed
    }

    #[getter]
    fn error_details(&self) -> Vec<String> {
        self.inner.error_details.clone()
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "files_processed": self.inner.files_processed,
            "total_symbols": self.inner.total_symbols,
            "errors": self.inner.errors,
            "crates_indexed": self.inner.crates_indexed,
            "error_details": self.inner.error_details,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for DependencyStats
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyDependencyStats {
    inner: DependencyStats,
}

#[pymethods]
impl PyDependencyStats {
    #[new]
    fn new(total_crates: usize, total_symbols: usize) -> Self {
        Self {
            inner: DependencyStats {
                total_crates,
                total_symbols,
            },
        }
    }

    #[getter]
    fn total_crates(&self) -> usize {
        self.inner.total_crates
    }

    #[getter]
    fn total_symbols(&self) -> usize {
        self.inner.total_symbols
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "total_crates": self.inner.total_crates,
            "total_symbols": self.inner.total_symbols,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for DependencyIndexer
#[pyclass]
#[derive(Debug)]
pub struct PyDependencyIndexer {
    inner: DependencyIndexer,
}

#[pymethods]
impl PyDependencyIndexer {
    #[new]
    #[pyo3(signature = (project_root, config_path))]
    fn new(project_root: &str, config_path: Option<&str>) -> Self {
        Self {
            inner: DependencyIndexer::new(project_root, config_path),
        }
    }

    /// Build the dependency index (synchronous).
    #[pyo3(signature = (clean=false, verbose=false))]
    fn build(&mut self, clean: bool, verbose: bool) -> String {
        let _ = clean; // reserved for future cache-clearing behavior
        // CLI argument can force verbose; env var remains a fallback for global logging config.
        let env_verbose = std::env::var("OMNI_LOG_LEVEL").is_ok_and(|v| v == "DEBUG");
        let result = self.inner.build(verbose || env_verbose);
        serde_json::to_string(&result).unwrap_or_else(|_| "{}".to_string())
    }

    /// Search for symbols matching a pattern.
    /// Returns list of symbols as JSON string.
    fn search(&self, pattern: &str, limit: usize) -> String {
        let results = self.inner.search(pattern, limit);
        let json_results: Vec<serde_json::Value> = results.iter().map(symbol_to_dict).collect();
        serde_json::to_string(&json_results).unwrap_or_else(|_| "[]".to_string())
    }

    /// Search within a specific crate.
    fn search_crate(&self, crate_name: &str, pattern: &str, limit: usize) -> String {
        let results = self.inner.search_crate(crate_name, pattern, limit);
        let json_results: Vec<serde_json::Value> = results.iter().map(symbol_to_dict).collect();
        serde_json::to_string(&json_results).unwrap_or_else(|_| "[]".to_string())
    }

    /// Get list of indexed crates/packages.
    fn get_indexed(&self) -> Vec<String> {
        self.inner.get_indexed().iter().map(String::clone).collect()
    }

    /// Get statistics as JSON string.
    fn stats(&self) -> String {
        let stats = self.inner.stats();
        serde_json::to_string(&stats).unwrap_or_else(|_| "{}".to_string())
    }

    /// Load index from cache.
    fn load_index(&mut self) -> bool {
        self.inner.load_index().is_ok()
    }

    /// Get the symbol index for direct manipulation (returns a new PySymbolIndex with cloned data).
    fn get_symbol_index(&self) -> PySymbolIndex {
        PySymbolIndex {
            inner: self.inner.symbol_index.clone(),
        }
    }
}

/// Python wrapper for ConfigExternalDependency
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyExternalDependency {
    inner: ConfigExternalDependency,
}

#[pymethods]
impl PyExternalDependency {
    #[new]
    fn new(pkg_type: &str, registry: Option<&str>, manifests: Vec<String>) -> Self {
        Self {
            inner: ConfigExternalDependency {
                pkg_type: pkg_type.to_string(),
                registry: registry.map(str::to_string),
                manifests,
            },
        }
    }

    #[getter]
    fn pkg_type(&self) -> String {
        self.inner.pkg_type.clone()
    }

    #[getter]
    fn registry(&self) -> Option<String> {
        self.inner.registry.clone()
    }

    #[getter]
    fn manifests(&self) -> Vec<String> {
        self.inner.manifests.clone()
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "pkg_type": self.inner.pkg_type,
            "registry": self.inner.registry,
            "manifests": self.inner.manifests,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Python wrapper for DependencyBuildConfig
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyDependencyConfig {
    inner: DependencyBuildConfig,
}

#[pymethods]
impl PyDependencyConfig {
    #[new]
    #[pyo3(signature = (path))]
    fn new(path: &str) -> Self {
        Self {
            inner: DependencyBuildConfig::load(path),
        }
    }

    #[getter]
    fn manifests(&self) -> Vec<PyExternalDependency> {
        self.inner
            .manifests
            .iter()
            .map(|e| PyExternalDependency { inner: e.clone() })
            .collect()
    }

    /// Load config from a YAML file path.
    #[staticmethod]
    #[pyo3(signature = (path))]
    fn load(path: &str) -> Self {
        Self::new(path)
    }

    fn to_dict(&self) -> String {
        let manifests: Vec<serde_json::Value> = self
            .inner
            .manifests
            .iter()
            .map(|e| {
                serde_json::json!({
                    "pkg_type": e.pkg_type,
                    "manifests": e.manifests,
                })
            })
            .collect();
        let value = serde_json::json!({
            "manifests": manifests,
        });
        serde_json::to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Register dependency indexer module with Python
///
/// # Errors
///
/// Returns `PyErr` when class registration fails.
pub fn register_dependency_indexer_module(m: &Bound<PyModule>) -> PyResult<()> {
    m.add_class::<PyExternalSymbol>()?;
    m.add_class::<PyExternalDependency>()?;
    m.add_class::<PySymbolIndex>()?;
    m.add_class::<PyDependencyConfig>()?;
    m.add_class::<PyDependencyIndexResult>()?;
    m.add_class::<PyDependencyStats>()?;
    m.add_class::<PyDependencyIndexer>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use crate::dependency_indexer::{ConfigExternalDependency, SymbolIndex};
    use std::path::PathBuf;

    fn workspace_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(4)
            .unwrap_or_else(|| panic!("failed to resolve workspace root from CARGO_MANIFEST_DIR"))
            .to_path_buf()
    }

    #[test]
    fn test_external_dependency_new() {
        let dep = ConfigExternalDependency {
            pkg_type: "rust".to_string(),
            registry: Some("cargo".to_string()),
            manifests: vec!["**/Cargo.toml".to_string()],
        };
        // Access inner directly in Rust tests
        assert_eq!(dep.pkg_type, "rust");
        assert_eq!(dep.registry, Some("cargo".to_string()));
        assert_eq!(dep.manifests, vec!["**/Cargo.toml"]);
    }

    #[test]
    fn test_external_dependency_no_registry() {
        let dep = ConfigExternalDependency {
            pkg_type: "python".to_string(),
            registry: None,
            manifests: vec!["**/pyproject.toml".to_string()],
        };

        assert_eq!(dep.pkg_type, "python");
        assert_eq!(dep.registry, None);
    }

    #[test]
    fn test_symbol_index_search() {
        let mut index = SymbolIndex::new();
        index.add_symbols(
            "test_crate",
            &[
                crate::dependency_indexer::ExternalSymbol {
                    name: "TestStruct".to_string(),
                    kind: crate::dependency_indexer::SymbolKind::Struct,
                    file: std::path::PathBuf::from("src/lib.rs"),
                    line: 10,
                    crate_name: "test_crate".to_string(),
                },
                crate::dependency_indexer::ExternalSymbol {
                    name: "test_function".to_string(),
                    kind: crate::dependency_indexer::SymbolKind::Function,
                    file: std::path::PathBuf::from("src/lib.rs"),
                    line: 20,
                    crate_name: "test_crate".to_string(),
                },
            ],
        );

        // Search for "TestStruct"
        let results = index.search("TestStruct", 10);
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].name, "TestStruct");
        assert_eq!(
            results[0].kind,
            crate::dependency_indexer::SymbolKind::Struct
        );
    }

    #[test]
    fn test_dependency_config_load() {
        use crate::dependency_indexer::DependencyBuildConfig as ConfigType;

        // Test loading config from actual references.yaml
        let config_path = workspace_root().join("packages/conf/references.yaml");
        let config = ConfigType::load(config_path.to_string_lossy().as_ref());

        // Should have at least rust and python dependencies
        assert!(!config.manifests.is_empty());

        // Find rust dependency
        let rust_dep = config.manifests.iter().find(|d| d.pkg_type == "rust");
        assert!(rust_dep.is_some());
        assert_eq!(rust_dep.unwrap().registry, Some("cargo".to_string()));

        // Find python dependency
        let py_dep = config.manifests.iter().find(|d| d.pkg_type == "python");
        assert!(py_dep.is_some());
        assert_eq!(py_dep.unwrap().registry, Some("pip".to_string()));
    }
}
