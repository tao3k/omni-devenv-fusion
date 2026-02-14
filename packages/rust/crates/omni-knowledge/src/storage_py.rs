//! PyO3 bindings for KnowledgeStorage (LanceDB operations).

use pyo3::prelude::*;

use crate::knowledge_py::PyKnowledgeEntry;
use crate::storage::KnowledgeStorage;

/// Knowledge storage Python wrapper.
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
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.init())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(())
    }

    fn upsert(&self, entry: &PyKnowledgeEntry) -> PyResult<bool> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.upsert(&entry.inner))
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(true)
    }

    fn text_search(&self, query: &str, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = runtime
            .block_on(self.inner.search_text(query, limit))
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|inner| PyKnowledgeEntry { inner })
            .collect())
    }

    fn vector_search(&self, query_vector: Vec<f32>, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let results = runtime
            .block_on(self.inner.search(&query_vector, limit))
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(results
            .into_iter()
            .map(|inner| PyKnowledgeEntry { inner })
            .collect())
    }

    fn search(&self, query: &str, limit: i32) -> PyResult<Vec<PyKnowledgeEntry>> {
        self.text_search(query, limit)
    }

    fn count(&self) -> PyResult<i64> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.count())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    fn clear(&self) -> PyResult<()> {
        let runtime = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        runtime
            .block_on(self.inner.clear())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(())
    }
}
