//! Tool Operations - Tool indexing and listing helpers
//!
//! Contains: index_skill_tools, list_all_tools

#![allow(dead_code)]

use omni_vector::VectorStore;
use pyo3::prelude::*;

pub(crate) fn index_skill_tools_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    base_path: &str,
    table_name: &str,
) -> PyResult<usize> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .index_skill_tools(base_path, table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let count = store
            .count(table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(count as usize)
    })
}

pub(crate) fn list_all_tools_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
) -> PyResult<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .list_all_tools(table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}
