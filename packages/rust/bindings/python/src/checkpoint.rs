//! Checkpoint Store - Python Bindings for LanceDB State Persistence
//!
//! Provides checkpoint persistence for LangGraph workflows.

use omni_vector::CheckpointStore;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};
use tokio::sync::Mutex as AsyncMutex;

/// Global connection pool: path -> Arc<Mutex<CheckpointStore>>
/// Ensures same path reuses the same store instance (connection复用)
static STORE_CACHE: OnceLock<Mutex<HashMap<String, Arc<AsyncMutex<CheckpointStore>>>>> =
    OnceLock::new();

/// Get or create the global runtime for Python bindings
fn get_runtime() -> &'static tokio::runtime::Runtime {
    static RUNTIME: OnceLock<tokio::runtime::Runtime> = OnceLock::new();
    RUNTIME.get_or_init(|| {
        tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .expect("Failed to create Tokio runtime for Python bindings")
    })
}

/// Timeline event for time-travel visualization.
/// V2.1: Aligned with TUI Visual Debugger requirements.
#[pyclass]
#[derive(Clone, Debug)]
pub struct PyTimelineEvent {
    /// Unique checkpoint identifier.
    #[pyo3(get)]
    pub checkpoint_id: String,
    /// Workflow thread identifier.
    #[pyo3(get)]
    pub thread_id: String,
    /// Monotonic workflow step number.
    #[pyo3(get)]
    pub step: i32,
    /// Event timestamp in Unix milliseconds.
    #[pyo3(get)]
    pub timestamp: f64,
    /// Human-friendly checkpoint preview text.
    #[pyo3(get)]
    pub preview: String,
    /// Parent checkpoint identifier when this is a branch.
    #[pyo3(get)]
    pub parent_checkpoint_id: Option<String>,
    /// Optional checkpoint reason tag.
    #[pyo3(get)]
    pub reason: Option<String>,
}

#[pymethods]
impl PyTimelineEvent {
    /// Format timestamp as ISO string for display
    fn iso_timestamp(&self) -> String {
        let secs = self.timestamp as i64;
        let nanos = ((self.timestamp - secs as f64) * 1_000_000_000.0) as i32;
        chrono::DateTime::from_timestamp(secs, nanos as u32)
            .map(|dt| dt.to_rfc3339())
            .unwrap_or_else(|| format!("{}", self.timestamp))
    }

    /// Get relative time string (e.g., "2 minutes ago")
    fn relative_time(&self) -> String {
        let now = chrono::Utc::now().timestamp_millis() as f64;
        let diff_ms = now - self.timestamp;
        let secs = diff_ms / 1000.0;

        if secs < 60.0 {
            format!("{:.0}s ago", secs)
        } else if secs < 3600.0 {
            format!("{:.0}m ago", secs / 60.0)
        } else if secs < 86400.0 {
            format!("{:.0}h ago", secs / 3600.0)
        } else {
            format!("{:.1}d ago", secs / 86400.0)
        }
    }

    /// Serialize to JSON for TUI socket communication
    fn to_json(&self) -> String {
        serde_json::json!({
            "checkpoint_id": self.checkpoint_id,
            "thread_id": self.thread_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "preview": self.preview,
            "parent_checkpoint_id": self.parent_checkpoint_id,
            "reason": self.reason
        })
        .to_string()
    }

    /// Convert to Python Dict for debugging
    fn to_dict(&self, py: Python) -> PyResult<Py<PyAny>> {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("checkpoint_id", &self.checkpoint_id)?;
        dict.set_item("thread_id", &self.thread_id)?;
        dict.set_item("step", self.step)?;
        dict.set_item("timestamp", self.timestamp)?;
        dict.set_item("preview", &self.preview)?;
        dict.set_item("parent_checkpoint_id", &self.parent_checkpoint_id)?;
        dict.set_item("reason", &self.reason)?;
        Ok(dict.into())
    }
}

/// Python wrapper for CheckpointStore (LanceDB-based state persistence)
#[pyclass]
pub struct PyCheckpointStore {
    // Cached store instance - reused across calls (path/dimension stored in Rust store)
    store: Arc<AsyncMutex<CheckpointStore>>,
}

#[pymethods]
impl PyCheckpointStore {
    #[new]
    fn new(path: String, dimension: Option<usize>) -> PyResult<Self> {
        let dimension = dimension.unwrap_or(1536);

        // Get or create the global cache
        let cache_mutex = STORE_CACHE.get_or_init(|| Mutex::new(HashMap::new()));
        let mut cache = cache_mutex.lock().map_err(|e| {
            pyo3::exceptions::PyRuntimeError::new_err(format!("Poisoned cache lock: {}", e))
        })?;

        // Check if store already exists for this path
        if let Some(store) = cache.get(&path) {
            return Ok(PyCheckpointStore {
                store: store.clone(),
            });
        }

        // Create new store
        let rt = get_runtime();
        let store = rt.block_on(async {
            CheckpointStore::new(&path, Some(dimension))
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })?;

        let arc_store = Arc::new(AsyncMutex::new(store));
        cache.insert(path.clone(), arc_store.clone());

        Ok(PyCheckpointStore { store: arc_store })
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
        let rt = get_runtime();

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
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
            guard
                .get_latest(&table_name, &thread_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Get checkpoint by ID
    fn get_by_id(&self, table_name: String, checkpoint_id: String) -> PyResult<Option<String>> {
        let store = self.store.clone();
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
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
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
            guard
                .get_history(&table_name, &thread_id, limit)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Delete all checkpoints for a thread
    fn delete_thread(&self, table_name: String, thread_id: String) -> PyResult<u32> {
        let store = self.store.clone();
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
            guard
                .delete_thread(&table_name, &thread_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
        })
    }

    /// Count checkpoints for a thread
    fn count(&self, table_name: String, thread_id: String) -> PyResult<u32> {
        let store = self.store.clone();
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
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
        let rt = get_runtime();

        let filter = filter_metadata
            .as_ref()
            .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok());

        rt.block_on(async {
            let mut guard = store.lock().await;
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

    /// Get timeline for time-travel visualization.
    ///
    /// Returns a list of PyTimelineEvent objects with previews and metadata.
    /// This method is optimized for fast timeline rendering - all parsing
    /// and preview generation happens in Rust.
    ///
    /// # Arguments
    /// * `table_name` - Name of the checkpoint table
    /// * `thread_id` - Thread ID to get timeline for
    /// * `limit` - Maximum number of events to return (default 20)
    ///
    /// # Returns
    /// List of PyTimelineEvent objects sorted by timestamp descending
    fn get_timeline(
        &self,
        table_name: String,
        thread_id: String,
        limit: Option<usize>,
    ) -> PyResult<Vec<PyTimelineEvent>> {
        let limit = limit.unwrap_or(20);
        let store = self.store.clone();
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
            let records = guard
                .get_timeline_records(&table_name, &thread_id, limit)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))?;

            // Convert to PyTimelineEvent objects
            let events: Vec<PyTimelineEvent> = records
                .into_iter()
                .map(|record| PyTimelineEvent {
                    checkpoint_id: record.checkpoint_id,
                    thread_id: record.thread_id,
                    step: record.step,
                    timestamp: record.timestamp,
                    preview: record.preview,
                    parent_checkpoint_id: record.parent_checkpoint_id,
                    reason: record.reason,
                })
                .collect();

            Ok(events)
        })
    }

    /// Get checkpoint content by ID.
    fn get_checkpoint_content(
        &self,
        table_name: String,
        checkpoint_id: String,
    ) -> PyResult<Option<String>> {
        let store = self.store.clone();
        let rt = get_runtime();

        rt.block_on(async {
            let mut guard = store.lock().await;
            guard
                .get_by_id(&table_name, &checkpoint_id)
                .await
                .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
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
