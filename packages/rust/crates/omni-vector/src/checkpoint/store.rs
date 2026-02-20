/// `CheckpointStore` - LanceDB-based checkpoint storage for `LangGraph`.
///
/// This module includes automatic corruption detection and recovery for `LanceDB` datasets.
/// When a dataset is corrupted (e.g., missing files), the store will automatically
/// detect the issue, remove the corrupted data, and recreate an empty dataset.
///
/// Common corruption scenarios and handling:
/// 1. Process crash during checkpoint write: `LanceDB` partial transaction -> auto-recovery
/// 2. Disk space exhaustion: Incomplete write -> detected via `_versions` check
/// 3. Orphan checkpoints from interrupted tasks: cleanup by `cleanup_orphan_checkpoints()`
/// 4. Concurrent write conflicts: version mismatch -> retry with recovery
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use futures::TryStreamExt;
use lance::dataset::optimize::{CompactionOptions, compact_files};
use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{Array, RecordBatch, RecordBatchIterator};
use lance::deps::arrow_schema::{ArrowError, Schema};
use tokio::sync::Mutex;

use crate::checkpoint::CheckpointRecord;
use crate::{
    CONTENT_COLUMN, DEFAULT_DIMENSION, ID_COLUMN, METADATA_COLUMN, THREAD_ID_COLUMN, VECTOR_COLUMN,
    VectorStoreError,
};

mod lifecycle;
mod maintenance;
mod read_ops;
mod schema;
mod search_ops;
mod timeline_ops;
mod write_ops;

/// LanceDB-based checkpoint storage for `LangGraph`.
#[derive(Clone)]
pub struct CheckpointStore {
    base_path: PathBuf,
    datasets: Arc<Mutex<dashmap::DashMap<String, Dataset>>>,
    repaired_tables: Arc<Mutex<std::collections::HashSet<String>>>,
    dimension: usize,
}

const PREVIEW_MAX_LEN: usize = 200;
const AUTO_COMPACT_FRAGMENT_THRESHOLD: usize = 128;
const AUTO_COMPACT_CHECK_INTERVAL: usize = 32;
const AUTO_COMPACT_TARGET_ROWS_PER_FRAGMENT: usize = 16 * 1024;
const AUTO_COMPACT_MAX_ROWS_PER_GROUP: usize = 1024;
const CHECKPOINT_TIMESTAMP_COLUMN: &str = "checkpoint_timestamp";
const CHECKPOINT_PARENT_ID_COLUMN: &str = "checkpoint_parent_id";
const CHECKPOINT_STEP_COLUMN: &str = "checkpoint_step";

impl CheckpointStore {
    /// Create a new checkpoint store at the given path.
    ///
    /// # Errors
    ///
    /// Returns an error if parent directories cannot be created.
    #[allow(clippy::unused_async)]
    pub async fn new(path: &str, dimension: Option<usize>) -> Result<Self, VectorStoreError> {
        let base_path = PathBuf::from(path);

        if let Some(parent) = base_path.parent()
            && !parent.exists()
        {
            std::fs::create_dir_all(parent)?;
        }

        if !base_path.exists() {
            std::fs::create_dir_all(&base_path)?;
        }

        Ok(Self {
            base_path,
            datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
            repaired_tables: Arc::new(Mutex::new(std::collections::HashSet::new())),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
        })
    }

    /// Get the table path for a checkpoint table.
    fn table_path(&self, table_name: &str) -> PathBuf {
        self.base_path.join(format!("{table_name}.lance"))
    }
}
