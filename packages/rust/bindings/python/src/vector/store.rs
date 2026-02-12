//! Store Lifecycle - Constructor and lifecycle methods for PyVectorStore.
//!
//! Contains: new, count, drop_table, schema evolution, table info

use omni_vector::{TableColumnAlteration, TableNewColumn, VectorStore};
use pyo3::prelude::*;
use serde::Deserialize;

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
        let mut store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .drop_table(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_get_table_info(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
) -> PyResult<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let info = store
            .get_table_info(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&info)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_list_versions(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
) -> PyResult<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let versions = store
            .list_versions(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&versions)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_get_fragment_stats(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
) -> PyResult<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .get_fragment_stats(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

#[derive(Debug, Deserialize)]
struct AddColumnsPayload {
    columns: Vec<TableNewColumn>,
}

pub(crate) fn store_add_columns(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
    payload_json: String,
) -> PyResult<()> {
    let payload: AddColumnsPayload = serde_json::from_str(&payload_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .add_columns(&table_name, payload.columns)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

#[derive(Debug, Deserialize)]
struct AlterColumnsPayload {
    alterations: Vec<TableColumnAlteration>,
}

pub(crate) fn store_alter_columns(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
    payload_json: String,
) -> PyResult<()> {
    let payload: AlterColumnsPayload = serde_json::from_str(&payload_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .alter_columns(&table_name, payload.alterations)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_drop_columns(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: String,
    columns: Vec<String>,
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
            .drop_columns(&table_name, columns)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}
