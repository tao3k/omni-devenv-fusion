//! Checkpoint Store - State Checkpoint Persistence with Semantic Search
//!
//! This module provides checkpoint storage for LangGraph workflows using LanceDB.

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{Array, RecordBatch, RecordBatchIterator};
use lance::deps::arrow_schema::{ArrowError, Schema};
use serde::{Deserialize, Serialize};
use tokio::sync::Mutex;

use crate::{
    CONTENT_COLUMN, DEFAULT_DIMENSION, ID_COLUMN, METADATA_COLUMN, VECTOR_COLUMN, VectorStoreError,
};

// ============================================================================
// Data Types
// ============================================================================

/// Checkpoint record for persistence.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointRecord {
    /// Unique checkpoint identifier
    pub checkpoint_id: String,
    /// Thread/session identifier
    pub thread_id: String,
    /// Parent checkpoint ID (for history chain)
    pub parent_id: Option<String>,
    /// Timestamp of checkpoint creation
    pub timestamp: f64,
    /// Serialized state JSON
    pub content: String,
    /// State embedding for semantic search (optional)
    pub embedding: Option<Vec<f32>>,
    /// Additional metadata (JSON serialized)
    pub metadata: Option<String>,
}

// ============================================================================
// Checkpoint Store Implementation
// ============================================================================

/// LanceDB-based checkpoint storage for LangGraph.
#[derive(Clone)]
pub struct CheckpointStore {
    base_path: PathBuf,
    datasets: Arc<Mutex<dashmap::DashMap<String, Dataset>>>,
    dimension: usize,
}

impl CheckpointStore {
    /// Create a new checkpoint store at the given path.
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
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
        })
    }

    /// Get the table path for a checkpoint table.
    fn table_path(&self, table_name: &str) -> PathBuf {
        self.base_path.join(format!("{table_name}.lance"))
    }

    /// Create the schema for checkpoint storage.
    fn create_schema(&self) -> Arc<Schema> {
        Arc::new(Schema::new(vec![
            lance::deps::arrow_schema::Field::new(
                ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                VECTOR_COLUMN,
                lance::deps::arrow_schema::DataType::FixedSizeList(
                    Arc::new(lance::deps::arrow_schema::Field::new(
                        "item",
                        lance::deps::arrow_schema::DataType::Float32,
                        true,
                    )),
                    i32::try_from(self.dimension).unwrap_or(1536),
                ),
                true,
            ),
            lance::deps::arrow_schema::Field::new(
                CONTENT_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            lance::deps::arrow_schema::Field::new(
                METADATA_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                true,
            ),
        ]))
    }

    /// Get or create a dataset for checkpoint storage.
    async fn get_or_create_dataset(
        &self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
        let table_path = self.table_path(table_name);
        let table_uri = table_path.to_string_lossy().into_owned();

        {
            let datasets = self.datasets.lock().await;
            if !force_create && let Some(cached) = datasets.get(table_name) {
                return Ok(cached.clone());
            }
        }

        let dataset = if table_path.exists() && !force_create {
            Dataset::open(table_uri.as_str()).await?
        } else {
            let schema = self.create_schema();
            let empty_batch = self.create_empty_batch(&schema)?;
            let batches: Vec<Result<_, ArrowError>> = vec![Ok(empty_batch)];
            let iter = RecordBatchIterator::new(batches, schema);
            Dataset::write(
                Box::new(iter),
                table_uri.as_str(),
                Some(WriteParams::default()),
            )
            .await
            .map_err(VectorStoreError::LanceDB)?
        };

        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }

        Ok(dataset)
    }

    /// Create an empty record batch for initialization.
    fn create_empty_batch(&self, schema: &Arc<Schema>) -> Result<RecordBatch, VectorStoreError> {
        let dimension = self.dimension;
        let arrays: Vec<Arc<dyn lance::deps::arrow_array::Array>> = vec![
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            Arc::new(lance::deps::arrow_array::FixedSizeListArray::new_null(
                Arc::new(lance::deps::arrow_schema::Field::new(
                    "item",
                    lance::deps::arrow_schema::DataType::Float32,
                    true,
                )),
                i32::try_from(dimension).unwrap_or(1536),
                0,
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(
                Vec::<String>::new(),
            )) as _,
        ];

        RecordBatch::try_new(schema.clone(), arrays).map_err(VectorStoreError::Arrow)
    }

    /// Save a checkpoint.
    pub async fn save_checkpoint(
        &self,
        table_name: &str,
        record: &CheckpointRecord,
    ) -> Result<(), VectorStoreError> {
        let schema = self.create_schema();

        // Build metadata JSON - merge user metadata with system fields
        let mut metadata_map = serde_json::Map::new();
        if let Some(ref user_meta) = record.metadata {
            if let Ok(user_obj) = serde_json::from_str::<serde_json::Value>(user_meta) {
                if let Some(obj) = user_obj.as_object() {
                    for (k, v) in obj.iter() {
                        metadata_map.insert(k.clone(), v.clone());
                    }
                }
            }
        }
        // Always override system fields
        metadata_map.insert(
            "thread_id".to_string(),
            serde_json::Value::String(record.thread_id.clone()),
        );
        if let Some(parent) = &record.parent_id {
            metadata_map.insert(
                "parent_id".to_string(),
                serde_json::Value::String(parent.clone()),
            );
        }
        metadata_map.insert(
            "timestamp".to_string(),
            serde_json::Value::Number(
                serde_json::Number::from_f64(record.timestamp)
                    .unwrap_or(serde_json::Number::from(0)),
            ),
        );
        let metadata = serde_json::Value::Object(metadata_map).to_string();

        // Build vector array (use zeros if no embedding)
        let embedding = record
            .embedding
            .clone()
            .unwrap_or_else(|| vec![0.0; self.dimension]);
        let flat_values: Vec<f32> = embedding;
        let vector_array = lance::deps::arrow_array::FixedSizeListArray::try_new(
            Arc::new(lance::deps::arrow_schema::Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(self.dimension).unwrap_or(1536),
            Arc::new(lance::deps::arrow_array::Float32Array::from(flat_values)),
            None,
        )
        .map_err(VectorStoreError::Arrow)?;

        // Build record batch
        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.checkpoint_id.clone(),
                ])),
                Arc::new(vector_array),
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.content.clone(),
                ])),
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![metadata])),
            ],
        )
        .map_err(VectorStoreError::Arrow)?;

        // Append to dataset
        let mut dataset = self.get_or_create_dataset(table_name, false).await?;
        let batches: Vec<Result<_, ArrowError>> = vec![Ok(batch)];
        let iter = RecordBatchIterator::new(batches, schema);
        dataset
            .append(Box::new(iter), None)
            .await
            .map_err(VectorStoreError::LanceDB)?;

        log::debug!(
            "Saved checkpoint '{}' for thread '{}'",
            record.checkpoint_id,
            record.thread_id
        );

        Ok(())
    }

    /// Get the latest checkpoint for a thread.
    pub async fn get_latest(
        &self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut scanner = dataset.scan();
        scanner.project(&[CONTENT_COLUMN, METADATA_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut latest_content: Option<String> = None;
        let mut latest_timestamp: f64 = -1.0;

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);

            if let (Some(content_col), Some(metadata_col)) = (content_col_opt, metadata_col_opt) {
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metadata_strs = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(content_strs), Some(metadata_strs)) = (content_strs, metadata_strs) {
                    for i in 0..batch.num_rows() {
                        if metadata_strs.is_null(i) {
                            continue;
                        }

                        let metadata_str = metadata_strs.value(i);
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if metadata.get("thread_id").and_then(|v| v.as_str()) == Some(thread_id)
                            {
                                let timestamp = metadata
                                    .get("timestamp")
                                    .and_then(|v| v.as_f64())
                                    .unwrap_or(0.0);
                                if timestamp > latest_timestamp {
                                    latest_timestamp = timestamp;
                                    if !content_strs.is_null(i) {
                                        latest_content = Some(content_strs.value(i).to_string());
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        Ok(latest_content)
    }

    /// Get checkpoint history for a thread (newest first).
    pub async fn get_history(
        &self,
        table_name: &str,
        thread_id: &str,
        limit: usize,
    ) -> Result<Vec<String>, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut scanner = dataset.scan();
        scanner.project(&[CONTENT_COLUMN, METADATA_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut checkpoints: Vec<(f64, String)> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);

            if let (Some(content_col), Some(metadata_col)) = (content_col_opt, metadata_col_opt) {
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metadata_strs = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(content_strs), Some(metadata_strs)) = (content_strs, metadata_strs) {
                    for i in 0..batch.num_rows() {
                        if metadata_strs.is_null(i) || content_strs.is_null(i) {
                            continue;
                        }

                        let metadata_str = metadata_strs.value(i);
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if metadata.get("thread_id").and_then(|v| v.as_str()) == Some(thread_id)
                            {
                                let timestamp = metadata
                                    .get("timestamp")
                                    .and_then(|v| v.as_f64())
                                    .unwrap_or(0.0);
                                let content = content_strs.value(i).to_string();
                                checkpoints.push((timestamp, content));
                            }
                        }
                    }
                }
            }
        }

        // Sort by timestamp descending and limit
        checkpoints.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        checkpoints.truncate(limit);

        Ok(checkpoints.into_iter().map(|(_, c)| c).collect())
    }

    /// Get checkpoint by ID.
    pub async fn get_by_id(
        &self,
        table_name: &str,
        checkpoint_id: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        use futures::TryStreamExt;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut scanner = dataset.scan();
        let filter_str = format!("{} = '{}'", ID_COLUMN, checkpoint_id.replace('\'', "''"));
        scanner.filter(filter_str.as_str())?;
        scanner.project(&[CONTENT_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        if let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let content_col = batch.column_by_name(CONTENT_COLUMN);
            if let Some(col) = content_col {
                if let Some(arr) = col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>()
                {
                    if batch.num_rows() > 0 && !arr.is_null(0) {
                        return Ok(Some(arr.value(0).to_string()));
                    }
                }
            }
        }

        Ok(None)
    }

    /// Delete all checkpoints for a thread.
    pub async fn delete_thread(
        &self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Ok(0);
        }

        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // First, get all matching checkpoint IDs (filter in memory since LanceDB json_extract expects binary)
        let mut ids_to_delete: Vec<String> = Vec::new();
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;

        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let id_col_opt = batch.column_by_name(ID_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);

            if let (Some(id_col), Some(metadata_col)) = (id_col_opt, metadata_col_opt) {
                let ids = id_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metas = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(ids), Some(metas)) = (ids, metas) {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }
                        let metadata_str = metas.value(i);
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if metadata.get("thread_id").and_then(|v| v.as_str()) == Some(thread_id)
                            {
                                if !ids.is_null(i) {
                                    ids_to_delete.push(ids.value(i).to_string());
                                }
                            }
                        }
                    }
                }
            }
        }

        // Delete by ID
        let mut deleted_count = 0;
        for id in &ids_to_delete {
            dataset
                .delete(&format!("{} = '{}'", ID_COLUMN, id.replace('\'', "''")))
                .await?;
            deleted_count += 1;
        }

        Ok(deleted_count as u32)
    }

    /// Count checkpoints for a thread.
    pub async fn count(&self, table_name: &str, thread_id: &str) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;

        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut count = 0u32;

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            if let Some(meta_col) = metadata_col {
                if let Some(metas) = meta_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>()
                {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }
                        let metadata_str = metas.value(i);
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if metadata.get("thread_id").and_then(|v| v.as_str()) == Some(thread_id)
                            {
                                count += 1;
                            }
                        }
                    }
                }
            }
        }

        Ok(count)
    }

    /// Search for similar checkpoints using vector similarity.
    ///
    /// Performs ANN (Approximate Nearest Neighbor) search on the embedding column.
    /// Optionally filters by thread_id and/or metadata conditions.
    ///
    /// # Arguments
    /// * `table_name` - Name of the checkpoint table
    /// * `query_vector` - Query embedding vector to search against
    /// * `limit` - Maximum number of results to return
    /// * `thread_id` - Optional thread ID to filter results (None = all threads)
    /// * `filter_metadata` - Optional metadata key-value pairs to filter by
    ///
    /// # Returns
    /// Vector of tuples: (content_json, metadata_json, distance_score)
    pub async fn search(
        &self,
        table_name: &str,
        query_vector: &[f32],
        limit: usize,
        thread_id: Option<&str>,
        filter_metadata: Option<serde_json::Value>,
    ) -> Result<Vec<(String, String, f32)>, VectorStoreError> {
        use futures::TryStreamExt;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        // Open dataset
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Build filter string from metadata conditions
        let _filter_parts: Vec<String> = Vec::new();
        if let Some(meta_filter) = &filter_metadata {
            if let Some(obj) = meta_filter.as_object() {
                for (key, value) in obj {
                    match value {
                        serde_json::Value::Bool(b) => {
                            // Filter will be applied in post-processing
                            log::debug!("Filtering by {} = {}", key, b);
                        }
                        serde_json::Value::String(s) => {
                            log::debug!("Filtering by {} = '{}'", key, s);
                        }
                        serde_json::Value::Number(n) => {
                            log::debug!("Filtering by {} = {}", key, n);
                        }
                        _ => {}
                    }
                }
            }
        }

        // Create scanner with all columns
        let mut scanner = dataset.scan();
        scanner.project(&[VECTOR_COLUMN, CONTENT_COLUMN, METADATA_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Collect all results with distances
        let mut results: Vec<(String, String, f32)> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let vector_col_opt = batch.column_by_name(VECTOR_COLUMN);
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);

            if let (Some(vector_col), Some(content_col), Some(metadata_col)) =
                (vector_col_opt, content_col_opt, metadata_col_opt)
            {
                let vector_arr = vector_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::FixedSizeListArray>();
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metadata_strs = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(vector_arr), Some(content_strs), Some(metadata_strs)) =
                    (vector_arr, content_strs, metadata_strs)
                {
                    let values_arr = vector_arr
                        .values()
                        .as_any()
                        .downcast_ref::<lance::deps::arrow_array::Float32Array>();

                    if let Some(values_arr) = values_arr {
                        for i in 0..batch.num_rows() {
                            // Compute L2 distance
                            let mut distance = 0.0f32;
                            let query_len = query_vector.len();
                            let values_len = values_arr.len();
                            for j in 0..query_len {
                                let db_val = if j < values_len {
                                    values_arr.value(j)
                                } else {
                                    0.0
                                };
                                let diff = db_val - query_vector[j];
                                distance += diff * diff;
                            }
                            let distance = distance.sqrt();

                            // Get metadata for filtering
                            if metadata_strs.is_null(i) {
                                continue;
                            }
                            let metadata_str = metadata_strs.value(i);

                            // Filter by thread_id if specified
                            if let Some(tid) = thread_id {
                                if let Ok(metadata) =
                                    serde_json::from_str::<serde_json::Value>(&metadata_str)
                                {
                                    if metadata.get("thread_id").and_then(|v| v.as_str())
                                        != Some(tid)
                                    {
                                        continue;
                                    }
                                } else {
                                    continue;
                                }
                            }

                            // Filter by metadata conditions
                            if let Some(meta_filter) = &filter_metadata {
                                if let Ok(metadata) =
                                    serde_json::from_str::<serde_json::Value>(&metadata_str)
                                {
                                    let mut matches = true;
                                    if let Some(obj) = meta_filter.as_object() {
                                        for (key, expected) in obj {
                                            if let Some(actual) = metadata.get(key) {
                                                if actual != expected {
                                                    matches = false;
                                                    break;
                                                }
                                            } else {
                                                matches = false;
                                                break;
                                            }
                                        }
                                    }
                                    if !matches {
                                        continue;
                                    }
                                } else {
                                    continue;
                                }
                            }

                            // Get content
                            if content_strs.is_null(i) {
                                continue;
                            }
                            let content = content_strs.value(i).to_string();

                            results.push((content, metadata_str.to_string(), distance));
                        }
                    }
                }
            }
        }

        // Sort by distance (lower is better for L2) and limit
        results.sort_by(|a, b| a.2.partial_cmp(&b.2).unwrap_or(std::cmp::Ordering::Equal));
        results.truncate(limit);

        Ok(results)
    }
}
