//! omni-knowledge - High-performance knowledge management library.
//!
//! This crate provides:
//! - KnowledgeEntry type definition
//! - KnowledgeCategory enumeration
//! - LanceDB storage operations
//! - Sync engine for incremental updates
//! - PyO3 bindings for Python
//!
//! # Examples
//!
//! ```rust
//! use omni_knowledge::{KnowledgeEntry, KnowledgeCategory};
//!
//! let entry = KnowledgeEntry::new(
//!     "test-001".to_string(),
//!     "Error Handling Pattern".to_string(),
//!     "Best practices for error handling...".to_string(),
//!     KnowledgeCategory::Pattern,
//! ).with_tags(vec!["error".to_string(), "exception".to_string()]);
//! ```

use pyo3::prelude::*;
use serde_json::{json, to_string};
use std::collections::HashMap;

mod storage;
mod sync;
mod types;

pub use storage::KnowledgeStorage;
pub use sync::{DiscoveryOptions, FileChange, SyncEngine, SyncManifest, SyncResult};
pub use types::{KnowledgeCategory, KnowledgeEntry, KnowledgeSearchQuery, KnowledgeStats};

/// Python module definition
#[pymodule]
fn _omni_knowledge(_py: Python, m: &Bound<PyModule>) -> PyResult<()> {
    // Register types
    m.add_class::<PyKnowledgeCategory>()?;
    m.add_class::<PyKnowledgeEntry>()?;
    m.add_class::<PyKnowledgeStorage>()?;
    m.add_class::<PySyncEngine>()?;
    m.add_class::<PySyncResult>()?;

    // Register functions
    m.add_function(wrap_pyfunction!(create_knowledge_entry, _py)?)?;
    m.add_function(wrap_pyfunction!(compute_hash, _py)?)?;

    Ok(())
}

/// Knowledge category Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeCategory {
    inner: KnowledgeCategory,
}

#[pymethods]
impl PyKnowledgeCategory {
    #[classattr]
    const PATTERN: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Pattern,
    };

    #[classattr]
    const SOLUTION: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Solution,
    };

    #[classattr]
    const ERROR: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Error,
    };

    #[classattr]
    const TECHNIQUE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Technique,
    };

    #[classattr]
    const NOTE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Note,
    };

    #[classattr]
    const REFERENCE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Reference,
    };

    #[classattr]
    const ARCHITECTURE: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Architecture,
    };

    #[classattr]
    const WORKFLOW: PyKnowledgeCategory = PyKnowledgeCategory {
        inner: KnowledgeCategory::Workflow,
    };

    #[new]
    fn new(category: &str) -> PyResult<Self> {
        match category {
            "patterns" | "pattern" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Pattern,
            }),
            "solutions" | "solution" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Solution,
            }),
            "errors" | "error" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Error,
            }),
            "techniques" | "technique" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Technique,
            }),
            "notes" | "note" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Note,
            }),
            "references" | "reference" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Reference,
            }),
            "architecture" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Architecture,
            }),
            "workflows" | "workflow" => Ok(PyKnowledgeCategory {
                inner: KnowledgeCategory::Workflow,
            }),
            _ => Err(pyo3::exceptions::PyValueError::new_err(format!(
                "Unknown category: {}",
                category
            ))),
        }
    }

    #[getter]
    fn value(&self) -> String {
        match self.inner {
            KnowledgeCategory::Pattern => "patterns".to_string(),
            KnowledgeCategory::Solution => "solutions".to_string(),
            KnowledgeCategory::Error => "errors".to_string(),
            KnowledgeCategory::Technique => "techniques".to_string(),
            KnowledgeCategory::Note => "notes".to_string(),
            KnowledgeCategory::Reference => "references".to_string(),
            KnowledgeCategory::Architecture => "architecture".to_string(),
            KnowledgeCategory::Workflow => "workflows".to_string(),
        }
    }

    fn __str__(&self) -> String {
        self.value()
    }
}

/// Knowledge entry Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyKnowledgeEntry {
    inner: KnowledgeEntry,
}

#[pymethods]
impl PyKnowledgeEntry {
    #[new]
    #[pyo3(signature = (id, title, content, category))]
    fn new(id: &str, title: &str, content: &str, category: PyKnowledgeCategory) -> Self {
        Self {
            inner: KnowledgeEntry::new(
                id.to_string(),
                title.to_string(),
                content.to_string(),
                category.inner,
            ),
        }
    }

    #[getter]
    fn id(&self) -> String {
        self.inner.id.clone()
    }

    #[getter]
    fn title(&self) -> String {
        self.inner.title.clone()
    }

    #[getter]
    fn content(&self) -> String {
        self.inner.content.clone()
    }

    #[getter]
    fn category(&self) -> PyKnowledgeCategory {
        PyKnowledgeCategory {
            inner: self.inner.category.clone(),
        }
    }

    #[getter]
    fn tags(&self) -> Vec<String> {
        self.inner.tags.clone()
    }

    #[getter]
    fn source(&self) -> Option<String> {
        self.inner.source.clone()
    }

    #[getter]
    fn version(&self) -> i32 {
        self.inner.version
    }

    #[setter]
    fn set_tags(&mut self, tags: Vec<String>) {
        self.inner.tags = tags;
    }

    #[setter]
    fn set_source(&mut self, source: Option<String>) {
        self.inner.source = source;
    }

    fn add_tag(&mut self, tag: String) {
        self.inner.add_tag(tag);
    }

    fn to_dict(&self) -> PyResult<String> {
        let value = json!({
            "id": self.inner.id,
            "title": self.inner.title,
            "content": self.inner.content,
            "category": self.category().value(),
            "tags": self.inner.tags,
            "source": self.inner.source,
            "version": self.inner.version,
        });
        Ok(to_string(&value).unwrap_or_else(|_| "{}".to_string()))
    }
}

/// Knowledge storage Python wrapper
#[pyclass]
#[derive(Debug)]
pub struct PyKnowledgeStorage {
    inner: KnowledgeStorage,
}

#[pymethods]
impl PyKnowledgeStorage {
    #[new]
    #[pyo3(signature = (path, table_name))]
    fn new(path: &str, table_name: &str) -> Self {
        Self {
            inner: KnowledgeStorage::new(path, table_name),
        }
    }

    #[getter]
    fn path(&self) -> String {
        self.inner.path().to_string_lossy().to_string()
    }

    #[getter]
    fn table_name(&self) -> String {
        self.inner.table_name().to_string()
    }

    fn init(&self) -> PyResult<()> {
        // TODO: Implement async init
        Ok(())
    }

    fn upsert(&self, entry: &PyKnowledgeEntry) -> PyResult<bool> {
        // TODO: Implement async upsert
        Ok(true)
    }

    fn search(&self, query: &str, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        // TODO: Implement async search
        Ok(Vec::new())
    }

    fn count(&self) -> PyResult<i64> {
        // TODO: Implement async count
        Ok(0)
    }

    fn clear(&self) -> PyResult<()> {
        // TODO: Implement async clear
        Ok(())
    }
}

/// Create a knowledge entry from Python.
#[pyfunction]
#[pyo3(signature = (title, content, category, tags, source))]
fn create_knowledge_entry(
    title: &str,
    content: &str,
    category: PyKnowledgeCategory,
    tags: Vec<String>,
    source: Option<&str>,
) -> PyResult<PyKnowledgeEntry> {
    let entry = KnowledgeEntry::new(
        uuid::Uuid::new_v4().to_string(),
        title.to_string(),
        content.to_string(),
        category.inner,
    )
    .with_tags(tags)
    .with_source(source.map(|s| s.to_string()));

    Ok(PyKnowledgeEntry { inner: entry })
}

/// Sync result Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySyncResult {
    pub inner: SyncResult,
}

#[pymethods]
impl PySyncResult {
    #[getter]
    fn added(&self) -> Vec<String> {
        self.inner
            .added
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    #[getter]
    fn modified(&self) -> Vec<String> {
        self.inner
            .modified
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    #[getter]
    fn deleted(&self) -> Vec<String> {
        self.inner
            .deleted
            .iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    #[getter]
    fn unchanged(&self) -> usize {
        self.inner.unchanged
    }

    fn to_dict(&self) -> String {
        let value = serde_json::json!({
            "added": self.added(),
            "modified": self.modified(),
            "deleted": self.deleted(),
            "unchanged": self.unchanged(),
        });
        to_string(&value).unwrap_or_else(|_| "{}".to_string())
    }
}

/// Sync engine Python wrapper
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySyncEngine {
    inner: SyncEngine,
}

#[pymethods]
impl PySyncEngine {
    #[new]
    #[pyo3(signature = (project_root, manifest_path))]
    fn new(project_root: &str, manifest_path: &str) -> Self {
        Self {
            inner: SyncEngine::new(project_root, manifest_path),
        }
    }

    fn load_manifest(&self) -> PyResult<String> {
        let manifest = self.inner.load_manifest();
        Ok(serde_json::to_string(&manifest.0).unwrap_or_default())
    }

    fn save_manifest(&self, manifest_json: &str) -> PyResult<()> {
        let manifest: HashMap<String, String> = serde_json::from_str(manifest_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let manifest = SyncManifest(manifest);
        self.inner
            .save_manifest(&manifest)
            .map_err(|e| pyo3::exceptions::PyIOError::new_err(e.to_string()))
    }

    fn discover_files(&self) -> Vec<String> {
        self.inner
            .discover_files()
            .into_iter()
            .map(|p| p.to_string_lossy().to_string())
            .collect()
    }

    fn compute_diff(&self, manifest_json: &str) -> PyResult<PySyncResult> {
        let manifest: HashMap<String, String> = serde_json::from_str(manifest_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        let manifest = SyncManifest(manifest);

        let files = self.inner.discover_files();
        let result = self.inner.compute_diff(&manifest, &files);

        Ok(PySyncResult { inner: result })
    }
}

/// Compute hash from content using xxhash (fast).
#[pyfunction]
#[pyo3(signature = (content))]
pub fn compute_hash(content: &str) -> String {
    SyncEngine::compute_hash(content)
}
