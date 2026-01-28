//! Document Operations - Add, delete documents helper functions

#![allow(dead_code)]

use omni_vector::VectorStore;

/// Add documents helper (called from PyVectorStore methods)
pub async fn add_documents_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    ids: Vec<String>,
    vectors: Vec<Vec<f32>>,
    contents: Vec<String>,
    metadatas: Vec<String>,
) -> pyo3::PyResult<()> {
    let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    store
        .add_documents(table_name, ids, vectors, contents, metadatas)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Delete documents helper
pub async fn delete_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    ids: Vec<String>,
) -> pyo3::PyResult<()> {
    let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    store
        .delete(table_name, ids)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}

/// Delete by file path helper
pub async fn delete_by_file_path_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    table_name: &str,
    file_paths: Vec<String>,
) -> pyo3::PyResult<()> {
    let store = VectorStore::new_with_keyword_index(path, Some(dimension), enable_kw)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    store
        .delete_by_file_path(table_name, file_paths)
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
}
