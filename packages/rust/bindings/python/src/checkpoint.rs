//! Checkpoint Store - Python Bindings for LanceDB State Persistence
//!
//! Provides checkpoint persistence for LangGraph workflows.

use omni_vector::CheckpointStore;
use pyo3::prelude::*;
use std::sync::Arc;
use tokio::sync::Mutex;

/// Python wrapper for CheckpointStore (LanceDB-based state persistence)
#[pyclass]
pub struct PyCheckpointStore {
    // Cached store instance - reused across calls (path/dimension stored in Rust store)
    store: Arc<Mutex<CheckpointStore>>,
}

#[pymethods]
impl PyCheckpointStore {
    #[new]
    fn new(path: String, dimension: Option<usize>) -> PyResult<Self> {
        let dimension = dimension.unwrap_or(1536);

        // Create the store once and cache it
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let store = rt.block_on(async {
            CheckpointStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        Ok(PyCheckpointStore {
            store: Arc::new(Mutex::new(store)),
        })
    }

    /// Save a checkpoint
    #[pyo3(signature = (table_name, checkpoint_id, thread_id, content, timestamp, parent_id, embedding, metadata))]
    fn save_checkpoint(
        &self,
        table_name: String,
        checkpoint_id: String,
        thread_id: String,
        content: String,
        timestamp: f64,
        parent_id: Option<String>,
        embedding: Option<Vec<f32>>,
        metadata: Option<String>,
    ) -> PyResult<()> {
        let record = omni_vector::CheckpointRecord {
            checkpoint_id,
            thread_id,
            parent_id,
            timestamp,
            content,
            embedding,
            metadata, // Pass metadata from Python
        };

        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let guard = store.lock().await;
            guard
                .save_checkpoint(&table_name, &record)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Get the latest checkpoint for a thread
    fn get_latest(&self, table_name: String, thread_id: String) -> PyResult<Option<String>> {
        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let guard = store.lock().await;
            guard
                .get_latest(&table_name, &thread_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Get checkpoint by ID
    fn get_by_id(&self, table_name: String, checkpoint_id: String) -> PyResult<Option<String>> {
        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let guard = store.lock().await;
            guard
                .get_by_id(&table_name, &checkpoint_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Get checkpoint history for a thread (newest first)
    fn get_history(
        &self,
        table_name: String,
        thread_id: String,
        limit: usize,
    ) -> PyResult<Vec<String>> {
        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let guard = store.lock().await;
            guard
                .get_history(&table_name, &thread_id, limit)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Delete all checkpoints for a thread
    fn delete_thread(&self, table_name: String, thread_id: String) -> PyResult<u32> {
        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let guard = store.lock().await;
            guard
                .delete_thread(&table_name, &thread_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Count checkpoints for a thread
    fn count(&self, table_name: String, thread_id: String) -> PyResult<u32> {
        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        rt.block_on(async {
            let guard = store.lock().await;
            guard
                .count(&table_name, &thread_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Search for similar checkpoints using vector similarity
    ///
    /// Returns a list of JSON strings: each contains content, metadata, and distance
    fn search(
        &self,
        table_name: String,
        query_vector: Vec<f32>,
        limit: usize,
        thread_id: Option<String>,
        filter_metadata: Option<String>,
    ) -> PyResult<Vec<String>> {
        let store = self.store.clone();
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

        let filter = filter_metadata
            .as_ref()
            .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok());

        rt.block_on(async {
            let guard = store.lock().await;
            let results = guard
                .search(
                    &table_name,
                    &query_vector,
                    limit,
                    thread_id.as_deref(),
                    filter,
                )
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            // Convert results to JSON strings
            let json_results: Vec<String> = results
                .into_iter()
                .map(|(content, metadata, distance)| {
                    serde_json::json!({
                        "content": content,
                        "metadata": metadata,
                        "distance": distance
                    })
                    .to_string()
                })
                .collect();

            Ok(json_results)
        })
    }
}

/// Create a new checkpoint store
#[pyfunction]
pub fn create_checkpoint_store(
    path: String,
    dimension: Option<usize>,
) -> PyResult<PyCheckpointStore> {
    PyCheckpointStore::new(path, dimension)
}
