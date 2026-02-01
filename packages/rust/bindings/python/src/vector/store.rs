//! Store Lifecycle - Constructor and lifecycle methods for PyVectorStore.
//!
//! Contains: new, count, drop_table

use omni_vector::VectorStore;
use pyo3::prelude::*;

/// Create a new PyVectorStore with async runtime initialization.
#[pyfunction]
#[pyo3(signature = (path, dimension = 1536, enable_keyword_index = false))]
pub fn create_vector_store(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
) -> PyResult<super::PyVectorStore> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        VectorStore::new_with_keyword_index(&path, Some(dimension), enable_keyword_index)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })?;

    Ok(super::PyVectorStore {
        path,
        dimension,
        enable_keyword_index,
    })
}

pub(crate) fn store_new(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
) -> PyResult<super::PyVectorStore> {
    create_vector_store(path, dimension, enable_keyword_index)
}

pub(crate) fn store_count(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
) -> PyResult<u32> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .count(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_drop_table(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .drop_table(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}
