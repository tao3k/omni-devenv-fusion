//! Tool Operations - Tool indexing and listing helpers

#![allow(dead_code)]

use omni_vector::VectorStore;

/// Index skill tools helper
pub async fn index_skill_tools_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    base_path: &str,
    table_name: &str,
) -> pyo3::PyResult<usize> {
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
}

/// List all tools helper
pub async fn list_all_tools_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
) -> pyo3::PyResult<String> {
    let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    store
        .list_all_tools(table_name)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Get all file hashes helper
pub async fn get_all_file_hashes_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
) -> pyo3::PyResult<String> {
    let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    store
        .get_all_file_hashes(table_name)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}
