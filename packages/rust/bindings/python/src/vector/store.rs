//! Store Lifecycle - Constructor and lifecycle methods for PyVectorStore.
//!
//! Contains: new, count, drop_table, schema evolution, table info

use omni_vector::{
    MigrateResult, MigrationItem, TableColumnAlteration, TableNewColumn, VectorStore,
    ops::DatasetCacheConfig,
};
use pyo3::prelude::*;
use serde::Deserialize;

pub(crate) fn cache_config_from_max(
    max_cached_tables: Option<usize>,
) -> Option<DatasetCacheConfig> {
    max_cached_tables.map(|n| DatasetCacheConfig {
        max_cached_tables: Some(n),
    })
}

/// Create a new PyVectorStore with async runtime initialization.
#[pyfunction]
#[pyo3(signature = (path, dimension = 1536, enable_keyword_index = false, index_cache_size_bytes = None, max_cached_tables = None))]
pub fn create_vector_store(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
) -> PyResult<super::PyVectorStore> {
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

    rt.block_on(async {
        VectorStore::new_with_keyword_index(
            &path,
            Some(dimension),
            enable_keyword_index,
            index_cache_size_bytes,
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })?;

    Ok(super::PyVectorStore {
        path,
        dimension,
        enable_keyword_index,
        index_cache_size_bytes,
        max_cached_tables,
    })
}

pub(crate) fn store_new(
    path: String,
    dimension: usize,
    enable_keyword_index: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
) -> PyResult<super::PyVectorStore> {
    create_vector_store(
        path,
        dimension,
        enable_keyword_index,
        index_cache_size_bytes,
        max_cached_tables,
    )
}

pub(crate) fn store_count(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
) -> PyResult<u32> {
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
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
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
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
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
        let store = VectorStore::new_with_keyword_index(
            path,
            Some(dimension),
            enable_kw,
            index_cache_size_bytes,
            cache_config_from_max(max_cached_tables),
        )
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
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
    columns: Vec<String>,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .drop_columns(&table_name, columns)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_analyze_table_health(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let report = store
            .analyze_table_health(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&report)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

/// Return table health report as Arrow IPC stream bytes for Python pyarrow.
pub(crate) fn store_analyze_table_health_ipc(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
) -> PyResult<Vec<u8>> {
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let report = store
            .analyze_table_health(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        super::ipc::table_health_report_to_ipc(&report)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))
    })
}

pub(crate) fn store_compact(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .compact(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_check_migrations(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let items: Vec<MigrationItem> = store
            .check_migrations(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&items)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_migrate(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
) -> PyResult<String> {
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let result: MigrateResult = store
            .migrate(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&result)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_get_index_cache_stats(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .get_index_cache_stats(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_get_query_metrics(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let metrics = store
            .get_query_metrics(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&metrics)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

// ---------------------------------------------------------------------------
// Index and maintenance operations (Phase 1–2 LanceDB 2.x)
// ---------------------------------------------------------------------------

pub(crate) fn store_create_btree_index(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
    column: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .create_btree_index(&table_name, &column)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_create_bitmap_index(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
    column: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .create_bitmap_index(&table_name, &column)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_create_hnsw_index(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .create_hnsw_index(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_create_optimal_vector_index(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let stats = store
            .create_optimal_vector_index(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        serde_json::to_string(&stats)
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_suggest_partition_column(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
) -> PyResult<Option<String>> {
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store
            .suggest_partition_column(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    })
}

pub(crate) fn store_auto_index_if_needed(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
) -> PyResult<Option<String>> {
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        let out = store
            .auto_index_if_needed(&table_name)
            .await
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        Ok(out.map(|s| serde_json::to_string(&s).unwrap_or_else(|_| "{}".to_string())))
    })
}

/// Start building the vector index in a background task. Returns immediately.
pub(crate) fn store_create_index_background(
    path: &str,
    dimension: usize,
    enable_kw: bool,
    index_cache_size_bytes: Option<usize>,
    max_cached_tables: Option<usize>,
    table_name: String,
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
            cache_config_from_max(max_cached_tables),
        )
        .await
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;
        store.create_index_background(&table_name);
        Ok(())
    })
}
