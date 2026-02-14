//! Document Operations - Add, delete documents helper functions
//!
//! Contains: add_documents, merge_insert_documents, add_single, delete, delete_by_file_path

use omni_vector::VectorStore;
use pyo3::prelude::*;

pub(crate) fn add_documents_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    ids: Vec<String>,
    vectors: Vec<Vec<f32>>,
    contents: Vec<String>,
    metadatas: Vec<String>,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .add_documents(table_name, ids, vectors, contents, metadatas)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn add_documents_partitioned_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    partition_by: &str,
    ids: Vec<String>,
    vectors: Vec<Vec<f32>>,
    contents: Vec<String>,
    metadatas: Vec<String>,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .add_documents_partitioned(table_name, partition_by, ids, vectors, contents, metadatas)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn replace_documents_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    ids: Vec<String>,
    vectors: Vec<Vec<f32>>,
    contents: Vec<String>,
    metadatas: Vec<String>,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let mut store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .replace_documents(table_name, ids, vectors, contents, metadatas)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn merge_insert_documents_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    ids: Vec<String>,
    vectors: Vec<Vec<f32>>,
    contents: Vec<String>,
    metadatas: Vec<String>,
    match_on: String,
) -> PyResult<String> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .merge_insert_documents(table_name, ids, vectors, contents, metadatas, &match_on)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn add_single_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    content: String,
    vector: Vec<f32>,
    metadata: String,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
    let id = uuid::Uuid::new_v4().to_string();

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .add_documents(
                table_name,
                vec![id],
                vec![vector],
                vec![content],
                vec![metadata],
            )
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn delete_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    ids: Vec<String>,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .delete(table_name, ids)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn delete_by_file_path_async(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: &str,
    file_paths: Vec<String>,
) -> PyResult<()> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            super::store::cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .delete_by_file_path(table_name, file_paths)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}
