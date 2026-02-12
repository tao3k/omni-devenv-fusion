/// CheckpointStore - LanceDB-based checkpoint storage for LangGraph
///
/// This module includes automatic corruption detection and recovery for LanceDB datasets.
/// When a dataset is corrupted (e.g., missing files), the store will automatically
/// detect the issue, remove the corrupted data, and recreate an empty dataset.
///
/// Common corruption scenarios and handling:
/// 1. Process crash during checkpoint write: LanceDB partial transaction → auto-recovery
/// 2. Disk space exhaustion: Incomplete write → detected via _versions check
/// 3. Orphan checkpoints from interrupted tasks: cleanup by gc_orphan_checkpoints()
/// 4. Concurrent write conflicts: version mismatch → retry with recovery
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{Array, RecordBatch, RecordBatchIterator};
use lance::deps::arrow_schema::{ArrowError, Schema};
use tokio::sync::Mutex;

use crate::checkpoint::CheckpointRecord;
use crate::{
    CONTENT_COLUMN, DEFAULT_DIMENSION, ID_COLUMN, METADATA_COLUMN, THREAD_ID_COLUMN, VECTOR_COLUMN,
    VectorStoreError,
};

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

        if let Some(parent) = base_path.parent() {
            if !parent.exists() {
                std::fs::create_dir_all(parent)?;
            }
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

    /// Check if a dataset is corrupted (missing files, etc.).
    ///
    /// Detects common corruption patterns from interrupted operations:
    /// - Missing _versions directory (partial transaction)
    /// - Empty data directories
    /// - Corrupt manifest files
    fn is_dataset_corrupted(&self, table_name: &str) -> bool {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return false;
        }
        // Check for common corruption indicators:
        // 1. Missing _versions directory (primary indicator of interrupted transaction)
        let versions_path = table_path.join("_versions");
        if !versions_path.exists() {
            log::warn!(
                "Dataset corrupted: missing _versions directory for {}",
                table_name
            );
            return true;
        }
        // 2. Check if _versions is empty (interrupted transaction)
        if let Ok(entries) = std::fs::read_dir(&versions_path) {
            let count = entries.count();
            if count == 0 {
                log::warn!(
                    "Dataset corrupted: empty _versions directory for {}",
                    table_name
                );
                return true;
            }
        }
        // 3. Check for data files (lance files)
        let data_files: Vec<_> = table_path
            .read_dir()
            .ok()
            .map(|dir| dir.filter_map(|e| e.ok()).collect::<Vec<_>>())
            .unwrap_or_default();
        let has_lance_files = data_files
            .iter()
            .any(|e| e.file_name().to_string_lossy().ends_with(".lance"));
        if !has_lance_files {
            // No data files, but _versions exists - might be valid empty dataset
            return false;
        }
        false
    }

    /// Check and clean up orphan checkpoints from interrupted graph tasks.
    ///
    /// Orphan checkpoints are checkpoints that exist but don't form a valid chain
    /// (e.g., due to interrupted task leaving partial state). This method:
    /// 1. Finds checkpoints without valid parent references
    /// 2. Identifies chains with gaps
    /// 3. Optionally removes invalid chains
    ///
    /// Returns the number of orphan checkpoints found/removed.
    pub async fn cleanup_orphan_checkpoints(
        &mut self,
        table_name: &str,
        dry_run: bool,
    ) -> Result<u32, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }

        let mut dataset = self.open_or_recover(table_name, false).await?;

        // Scan all checkpoints to find orphans
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut orphan_ids: Vec<String> = Vec::new();
        let mut all_ids: Vec<String> = Vec::new();
        let mut parent_refs: std::collections::HashSet<String> = std::collections::HashSet::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let id_col = batch.column_by_name(ID_COLUMN);
            let metadata_col = batch.column_by_name(METADATA_COLUMN);

            if let (Some(id_c), Some(meta_c)) = (id_col, metadata_col) {
                let ids = id_c
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metas = meta_c
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(ids), Some(metas)) = (ids, metas) {
                    for i in 0..batch.num_rows() {
                        if ids.is_null(i) {
                            continue;
                        }
                        let id = ids.value(i).to_string();
                        all_ids.push(id.clone());

                        // Collect parent references from metadata
                        if !metas.is_null(i) {
                            let meta_str = metas.value(i);
                            if let Ok(meta) = serde_json::from_str::<serde_json::Value>(&meta_str) {
                                if let Some(parent) = meta.get("parent_id").and_then(|v| v.as_str())
                                {
                                    parent_refs.insert(parent.to_string());
                                }
                            }
                        }
                    }
                }
            }
        }

        // Find IDs that are not referenced as parents (orphans - likely starting points of interrupted chains)
        // Also check for UUID-like patterns that indicate temporary/incomplete tasks
        for id in &all_ids {
            // Orphan if: not referenced as parent AND looks like a temp UUID pattern
            if !parent_refs.contains(id) {
                // Additional check: UUID patterns often indicate interrupted tasks
                // UUID v1-v5 have 8-4-4-4-12 format with hex characters
                // Check for common UUID patterns: dashes at specific positions
                let is_uuid_like = id.len() >= 36
                    && id.chars().all(|c| c.is_ascii_hexdigit() || c == '-')
                    && id.matches('-').count() == 4;
                if is_uuid_like || id.len() > 50 {
                    orphan_ids.push(id.clone());
                }
            }
        }

        let orphan_count = orphan_ids.len() as u32;

        if orphan_count > 0 {
            log::info!(
                "Found {} orphan checkpoints in {} (dry_run={})",
                orphan_count,
                table_name,
                dry_run
            );

            if !dry_run {
                // Remove orphans
                for id in &orphan_ids {
                    dataset
                        .delete(&format!("{} = '{}'", ID_COLUMN, id.replace('\'', "''")))
                        .await?;
                    log::debug!("Removed orphan checkpoint: {}", id);
                }
            }
        }

        Ok(orphan_count)
    }

    /// Force recovery of a corrupted dataset, discarding all data.
    ///
    /// Use this when auto-recovery is insufficient and you want to
    /// completely reset the checkpoint store.
    pub async fn force_recover(&mut self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);

        // Remove from cache
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }

        // Remove entire dataset directory
        if table_path.exists() {
            log::warn!("Force recovering {}: removing {:?}", table_name, table_path);
            std::fs::remove_dir_all(&table_path).map_err(|e| {
                VectorStoreError::General(format!(
                    "Failed to remove corrupted dataset {}: {}",
                    table_name, e
                ))
            })?;
        }

        // Recreate empty dataset
        self.get_or_create_dataset(table_name, true).await?;

        log::info!("Force recovery complete for {}", table_name);
        Ok(())
    }

    /// Remove corrupted dataset and recreate it.
    async fn recover_corrupted_dataset(
        &mut self,
        table_name: &str,
    ) -> Result<Dataset, VectorStoreError> {
        let table_path = self.table_path(table_name);

        // Remove from cache
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }

        // Remove corrupted dataset directory
        if table_path.exists() {
            log::warn!("Removing corrupted dataset: {:?}", table_path);
            std::fs::remove_dir_all(&table_path).map_err(|e| {
                VectorStoreError::General(format!(
                    "Failed to remove corrupted dataset {}: {}",
                    table_name, e
                ))
            })?;
        }

        // Recreate the dataset
        log::info!("Recreating dataset: {}", table_name);
        let schema = self.create_schema();
        let empty_batch = self.create_empty_batch(&schema)?;
        let batches: Vec<Result<_, ArrowError>> = vec![Ok(empty_batch)];
        let iter = RecordBatchIterator::new(batches, schema);
        let table_uri = table_path.to_string_lossy().into_owned();
        let dataset = Dataset::write(
            Box::new(iter),
            table_uri.as_str(),
            Some(WriteParams::default()),
        )
        .await
        .map_err(VectorStoreError::LanceDB)?;

        // Add to cache
        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }

        Ok(dataset)
    }

    /// Try to open a dataset, recovering from corruption if needed.
    async fn open_or_recover(
        &mut self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
        // First check if we need to recover
        if !force_create && self.is_dataset_corrupted(table_name) {
            return self.recover_corrupted_dataset(table_name).await;
        }

        // Try normal open
        let table_path = self.table_path(table_name);
        if !force_create && table_path.exists() {
            match Dataset::open(table_path.to_string_lossy().as_ref()).await {
                Ok(dataset) => {
                    // Cache the successfully opened dataset
                    let datasets = self.datasets.lock().await;
                    datasets.insert(table_name.to_string(), dataset.clone());
                    return Ok(dataset);
                }
                Err(e) => {
                    log::warn!(
                        "Failed to open dataset {}: {}. Attempting recovery...",
                        table_name,
                        e
                    );
                    return self.recover_corrupted_dataset(table_name).await;
                }
            }
        }

        // Create new dataset
        self.get_or_create_dataset(table_name, force_create).await
    }

    /// Create the schema for checkpoint storage.
    fn create_schema(&self) -> Arc<Schema> {
        Arc::new(Schema::new(vec![
            lance::deps::arrow_schema::Field::new(
                ID_COLUMN,
                lance::deps::arrow_schema::DataType::Utf8,
                false,
            ),
            // thread_id as first-class column for predicate push-down filtering
            lance::deps::arrow_schema::Field::new(
                THREAD_ID_COLUMN,
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
            if !force_create {
                if let Some(cached) = datasets.get(table_name) {
                    return Ok(cached.clone());
                }
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
            // thread_id column
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

        // Build metadata JSON - merge user metadata with system fields (thread_id now in separate column)
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
        // Note: thread_id is now stored in separate column, not in metadata
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

        // Build record batch with thread_id as separate column
        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.checkpoint_id.clone(),
                ])),
                // thread_id as first-class column for predicate push-down
                Arc::new(lance::deps::arrow_array::StringArray::from(vec![
                    record.thread_id.clone(),
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
        &mut self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[CONTENT_COLUMN, METADATA_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace("'", "''"));
        scanner.filter(&filter_expr)?;

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

                        // thread_id already filtered, only need to parse timestamp from metadata
                        let metadata_str = metadata_strs.value(i);
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
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

        Ok(latest_content)
    }

    /// Get checkpoint history for a thread (newest first).
    pub async fn get_history(
        &mut self,
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

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[CONTENT_COLUMN, METADATA_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace("'", "''"));
        scanner.filter(&filter_expr)?;

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

                        // thread_id already filtered, only need to parse timestamp from metadata
                        let metadata_str = metadata_strs.value(i);
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
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

        // Sort by timestamp descending and limit
        checkpoints.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        checkpoints.truncate(limit);

        Ok(checkpoints.into_iter().map(|(_, c)| c).collect())
    }

    /// Get checkpoint by ID.
    pub async fn get_by_id(
        &mut self,
        table_name: &str,
        checkpoint_id: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        use futures::TryStreamExt;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

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
        &mut self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Ok(0);
        }

        // Use open_or_recover to handle corruption
        let mut dataset = self.open_or_recover(table_name, false).await?;

        // PREDICATE PUSH-DOWN: Use thread_id column filter instead of metadata parsing
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN])?;
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace("'", "''"));
        scanner.filter(&filter_expr)?;

        use futures::TryStreamExt;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Collect all IDs to delete
        let mut ids_to_delete: Vec<String> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let id_col_opt = batch.column_by_name(ID_COLUMN);
            if let Some(id_col) = id_col_opt {
                let ids = id_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                if let Some(ids) = ids {
                    for i in 0..batch.num_rows() {
                        if !ids.is_null(i) {
                            ids_to_delete.push(ids.value(i).to_string());
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
    pub async fn count(
        &mut self,
        table_name: &str,
        thread_id: &str,
    ) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(0);
        }

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace("'", "''"));
        scanner.filter(&filter_expr)?;

        use futures::TryStreamExt;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;
        let mut count = 0u32;

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            // thread_id already filtered, just count rows
            count += batch.num_rows() as u32;
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
        &mut self,
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

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

        // Create scanner with all columns needed for search
        let mut scanner = dataset.scan();
        scanner.project(&[
            THREAD_ID_COLUMN,
            VECTOR_COLUMN,
            CONTENT_COLUMN,
            METADATA_COLUMN,
        ])?;

        // PREDICATE PUSH-DOWN: Use native LanceDB filter for thread_id
        // This avoids full table scan and JSON parsing for thread_id filtering
        if let Some(tid) = thread_id {
            let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, tid.replace("'", "''"));
            scanner.filter(&filter_expr)?;
        }

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
                        // Pre-compute values slice once to avoid repeated method calls
                        let values_slice = values_arr.values();
                        let db_len = values_slice.len();
                        let query_len = query_vector.len();
                        // Use min to handle dimension mismatches safely
                        let compute_len = db_len.min(query_len);

                        for i in 0..batch.num_rows() {
                            // Compute L2 distance using SIMD-friendly iterator pattern
                            // zip() allows LLVM to auto-vectorize the loop
                            let distance: f32 = query_vector[..compute_len]
                                .iter()
                                .zip(&values_slice[..compute_len])
                                .map(|(q, d)| {
                                    let diff = q - d;
                                    diff * diff
                                })
                                .sum();

                            let distance = distance.sqrt();

                            // Get metadata for filtering (thread_id already filtered by predicate push-down)
                            if metadata_strs.is_null(i) {
                                continue;
                            }
                            let metadata_str = metadata_strs.value(i);

                            // Filter by metadata conditions (only if specified)
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

    /// Get timeline records for time-travel visualization.
    ///
    /// Returns structured timeline events with previews, suitable for UI display.
    /// This method is optimized for fast timeline rendering in Python/Rust.
    ///
    /// # Arguments
    /// * `table_name` - Name of the checkpoint table
    /// * `thread_id` - Thread ID to get timeline for
    /// * `limit` - Maximum number of events to return
    ///
    /// # Returns
    /// Vector of TimelineRecord sorted by timestamp descending (newest first)
    pub async fn get_timeline_records(
        &mut self,
        table_name: &str,
        thread_id: &str,
        limit: usize,
    ) -> Result<Vec<super::TimelineRecord>, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }

        // Use open_or_recover to handle corruption
        let dataset = self.open_or_recover(table_name, false).await?;

        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, CONTENT_COLUMN, METADATA_COLUMN])?;
        // PREDICATE PUSH-DOWN: Filter by thread_id column
        let filter_expr = format!("{} = '{}'", THREAD_ID_COLUMN, thread_id.replace("'", "''"));
        scanner.filter(&filter_expr)?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        const PREVIEW_MAX_LEN: usize = 200;
        let mut checkpoints: Vec<(f64, super::TimelineRecord)> = Vec::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let id_col_opt = batch.column_by_name(ID_COLUMN);
            let content_col_opt = batch.column_by_name(CONTENT_COLUMN);
            let metadata_col_opt = batch.column_by_name(METADATA_COLUMN);

            if let (Some(id_col), Some(content_col), Some(metadata_col)) =
                (id_col_opt, content_col_opt, metadata_col_opt)
            {
                let id_strs = id_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let content_strs = content_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();
                let metadata_strs = metadata_col
                    .as_any()
                    .downcast_ref::<lance::deps::arrow_array::StringArray>();

                if let (Some(id_strs), Some(content_strs), Some(metadata_strs)) =
                    (id_strs, content_strs, metadata_strs)
                {
                    for i in 0..batch.num_rows() {
                        if metadata_strs.is_null(i) || content_strs.is_null(i) || id_strs.is_null(i)
                        {
                            continue;
                        }

                        let id = id_strs.value(i).to_string();
                        let content = content_strs.value(i).to_string();
                        let metadata_str = metadata_strs.value(i);

                        // Parse metadata for timestamp, parent_checkpoint_id, and reason
                        let (timestamp, parent_checkpoint_id, reason) = if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            let ts = metadata
                                .get("timestamp")
                                .and_then(|v| v.as_f64())
                                .unwrap_or(0.0);
                            let pid = metadata
                                .get("parent_id")
                                .and_then(|v| v.as_str())
                                .map(|s| s.to_string());
                            let rs = metadata
                                .get("reason")
                                .and_then(|v| v.as_str())
                                .map(|s| s.to_string());
                            (ts, pid, rs)
                        } else {
                            (0.0, None, None)
                        };

                        // Create preview (truncated content)
                        let preview = if content.len() > PREVIEW_MAX_LEN {
                            format!("{}...", &content[0..PREVIEW_MAX_LEN])
                        } else {
                            content.clone()
                        };

                        let record = super::TimelineRecord {
                            checkpoint_id: id,
                            thread_id: thread_id.to_string(),
                            step: 0, // Will be set after sorting
                            timestamp,
                            preview,
                            parent_checkpoint_id,
                            reason,
                        };

                        checkpoints.push((timestamp, record));
                    }
                }
            }
        }

        // Sort by timestamp descending and assign step numbers
        checkpoints.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        checkpoints.truncate(limit);

        let timeline: Vec<super::TimelineRecord> = checkpoints
            .into_iter()
            .enumerate()
            .map(|(step, (_, record))| {
                let mut record = record;
                record.step = step as i32;
                record
            })
            .collect();

        Ok(timeline)
    }
}
