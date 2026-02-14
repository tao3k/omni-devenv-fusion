//! PyO3 bindings for sync engine (incremental file sync).

use pyo3::prelude::*;
use serde_json::to_string;
use std::collections::HashMap;

use crate::sync::{SyncEngine, SyncManifest, SyncResult};

/// Sync result Python wrapper.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PySyncResult {
    /// Wrapped sync result payload from Rust core.
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

/// Sync engine Python wrapper.
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
