//! VectorStore CRUD operations - Document storage and management
//!
//! This module provides the core CRUD (Create, Read, Update, Delete)
//! operations for the VectorStore.

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{RecordBatch, RecordBatchIterator};
use lance::deps::arrow_schema::ArrowError;

use tokio::sync::Mutex;

use crate::{
    CONTENT_COLUMN, DEFAULT_DIMENSION, ID_COLUMN, METADATA_COLUMN, VECTOR_COLUMN, VectorStoreError,
};

impl crate::VectorStore {
    /// Create a new vector store at the given path.
    ///
    /// # Arguments
    ///
    /// * `path` - Base directory for the vector database
    /// * `dimension` - Embedding vector dimension (default: 1536 for `OpenAI` Ada-002)
    ///
    /// # Returns
    ///
    /// A new `VectorStore` instance
    ///
    /// # Errors
    ///
    /// Returns an error if the directory cannot be created.
    pub async fn new(path: &str, dimension: Option<usize>) -> Result<Self, VectorStoreError> {
        // Special case for in-memory mode - don't create any directories
        if path == ":memory:" {
            return Ok(Self {
                base_path: PathBuf::from(":memory:"),
                datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
                dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
            });
        }

        let base_path = PathBuf::from(path);

        // Ensure parent directory exists
        if let Some(parent) = base_path.parent() {
            if !parent.exists() {
                std::fs::create_dir_all(parent)?;
            }
        }

        // Create base directory if it doesn't exist
        if !base_path.exists() {
            std::fs::create_dir_all(&base_path)?;
        }

        Ok(Self {
            base_path,
            datasets: Arc::new(Mutex::new(dashmap::DashMap::new())),
            dimension: dimension.unwrap_or(DEFAULT_DIMENSION),
        })
    }

    /// Get the table path for a given table name.
    pub fn table_path(&self, table_name: &str) -> PathBuf {
        // For in-memory mode, return a special marker instead of file path
        if self.base_path.as_os_str() == ":memory:" {
            PathBuf::from(format!(":memory:_{}", table_name))
        } else {
            self.base_path.join(format!("{table_name}.lance"))
        }
    }

    /// Create the schema for vector storage.
    pub fn create_schema(&self) -> Arc<lance::deps::arrow_schema::Schema> {
        Arc::new(lance::deps::arrow_schema::Schema::new(vec![
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
                false,
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

    /// Get or create a dataset for a table.
    async fn get_or_create_dataset(
        &self,
        table_name: &str,
        force_create: bool,
    ) -> Result<Dataset, VectorStoreError> {
        let table_path = self.table_path(table_name);
        let table_uri = table_path.to_string_lossy().into_owned();

        // Check cache first
        {
            let datasets = self.datasets.lock().await;
            if !force_create {
                if let Some(cached) = datasets.get(table_name) {
                    return Ok(cached.clone());
                }
            }
        }

        // Open or create dataset
        let is_memory_mode = self.base_path.as_os_str() == ":memory:";
        let dataset = if !is_memory_mode && table_path.exists() && !force_create {
            Dataset::open(table_uri.as_str()).await?
        } else {
            // Create new dataset with schema using Dataset::write
            let schema = self.create_schema();
            let empty_batch = self.create_empty_batch(&schema)?;
            let batches: Vec<Result<_, ArrowError>> = vec![Ok(empty_batch)];
            let iter = RecordBatchIterator::new(batches, schema);

            // For in-memory mode, use a temporary file that gets cleaned up
            // (LanceDB doesn't have true in-memory mode for persistence)
            let write_uri = if is_memory_mode {
                // Use a temp file for in-memory operations
                use std::env;
                let temp_dir = env::temp_dir();
                let temp_path = temp_dir.join(format!("omni_lance_{}", table_name));
                temp_path.to_string_lossy().into_owned()
            } else {
                table_uri
            };

            Dataset::write(
                Box::new(iter),
                write_uri.as_str(),
                Some(WriteParams::default()),
            )
            .await
            .map_err(VectorStoreError::LanceDB)?
        };

        // Cache the dataset
        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }

        Ok(dataset)
    }

    /// Create an empty record batch for initialization.
    pub fn create_empty_batch(
        &self,
        schema: &Arc<lance::deps::arrow_schema::Schema>,
    ) -> Result<RecordBatch, VectorStoreError> {
        // Use instance dimension, not default
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

    /// Add documents to the vector store.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `ids` - Unique identifiers for each document
    /// * `vectors` - Embedding vectors (must all have the same dimension)
    /// * `contents` - Text content for each document
    /// * `metadatas` - JSON metadata for each document
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::EmptyDataset`] if ids is empty,
    /// or [`VectorStoreError::InvalidDimension`] if vectors have inconsistent dimensions.
    pub async fn add_documents(
        &self,
        table_name: &str,
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        if ids.is_empty() {
            return Ok(());
        }

        // Validate dimensions
        let dimension = vectors.first().ok_or(VectorStoreError::EmptyDataset)?.len();

        if dimension == 0 {
            return Err(VectorStoreError::InvalidEmbeddingDimension);
        }

        for vec in &vectors {
            if vec.len() != dimension {
                return Err(VectorStoreError::InvalidDimension {
                    expected: dimension,
                    actual: vec.len(),
                });
            }
        }

        // Build Arrow arrays
        let id_array = lance::deps::arrow_array::StringArray::from(ids);
        let content_array = lance::deps::arrow_array::StringArray::from(contents);
        let metadata_array = lance::deps::arrow_array::StringArray::from(metadatas);

        // Flatten vectors for FixedSizeListArray
        let flat_values: Vec<f32> = vectors.into_iter().flatten().collect();
        let vector_array = lance::deps::arrow_array::FixedSizeListArray::try_new(
            Arc::new(lance::deps::arrow_schema::Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(dimension).unwrap_or(1536),
            Arc::new(lance::deps::arrow_array::Float32Array::from(flat_values)),
            None, // no nulls
        )
        .map_err(VectorStoreError::Arrow)?;

        // Create record batch
        let schema = self.create_schema();
        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(id_array),
                Arc::new(vector_array),
                Arc::new(content_array),
                Arc::new(metadata_array),
            ],
        )
        .map_err(VectorStoreError::Arrow)?;

        // Get or create dataset
        let mut dataset = self.get_or_create_dataset(table_name, false).await?;

        // Append to dataset using LanceDB 1.0 API
        let batches: Vec<Result<_, ArrowError>> = vec![Ok(batch)];
        let iter = RecordBatchIterator::new(batches, schema);
        dataset
            .append(Box::new(iter), None)
            .await
            .map_err(VectorStoreError::LanceDB)?;

        log::info!("Added documents to table '{table_name}'");

        Ok(())
    }

    /// Delete documents by ID.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `ids` - IDs of documents to delete
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn delete(&self, table_name: &str, ids: Vec<String>) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Delete by ID using LanceDB 1.0 API
        for id in ids {
            dataset
                .delete(&format!("{ID_COLUMN} = '{id}'"))
                .await
                .map_err(VectorStoreError::LanceDB)?;
        }

        Ok(())
    }

    /// Delete documents by file path.
    ///
    /// Note: file_path is stored in the metadata JSON column as a string.
    /// We use LIKE pattern matching to find records where metadata contains
    /// the file path in the expected JSON format: `"file_path":"<path>"`
    ///
    /// Delete documents by their file_path in metadata.
    ///
    /// This function scans the table and matches `file_path` from metadata JSON,
    /// then deletes by ID. This approach is chosen over SQL LIKE because:
    ///
    /// - **SQL LIKE has underscore escaping issues**: `_` in paths like
    ///   `temp_skill/scripts/hello.py` would be interpreted as single-character
    ///   wildcard, causing incorrect matches.
    ///   - Incorrect: `WHERE file_path LIKE '%temp\_skill%'` (underscore escaped)
    ///   - Incorrect: `WHERE file_path LIKE '%temp_skill%'` (underscore as wildcard)
    /// - **JSON field access is unreliable**: `metadata:file_path` queries may not
    ///   work consistently across LanceDB versions.
    /// - **Scanning is reliable**: We read all IDs and file_paths, then match in
    ///   Rust where the semantics are well-defined.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `file_paths` - Exact file paths to delete (must match metadata["file_path"])
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    ///
    /// # Example
    ///
    /// ```ignore
    /// store.delete_by_file_path(
    ///     "skills",
    ///     vec!["temp_skill/scripts/hello.py".to_string()]
    /// ).await?;
    /// ```
    pub async fn delete_by_file_path(
        &self,
        table_name: &str,
        file_paths: Vec<String>,
    ) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        if file_paths.is_empty() {
            return Ok(());
        }

        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Create a HashSet for O(1) lookup - handles paths with underscores correctly
        let file_paths_set: std::collections::HashSet<String> =
            file_paths.iter().cloned().collect();

        // Scan the table and find IDs matching the file paths
        // We scan instead of using SQL LIKE because:
        // 1. LIKE's underscore (_) is a single-character wildcard
        // 2. Escaping underscore (\_) doesn't work reliably
        // 3. JSON path queries are version-dependent
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut ids_to_delete: Vec<String> = Vec::new();

        use futures::TryStreamExt;
        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            use lance::deps::arrow_array::{Array, StringArray};

            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_col = batch.column_by_name(ID_COLUMN);

            if let (Some(meta_col), Some(id_c)) = (metadata_col, id_col) {
                if let Some(metas) = meta_col.as_any().downcast_ref::<StringArray>() {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }

                        let metadata_str = metas.value(i);
                        let id = id_c
                            .as_any()
                            .downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();

                        // Parse metadata JSON and check file_path
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if let Some(file_path) =
                                metadata.get("file_path").and_then(|v| v.as_str())
                            {
                                if file_paths_set.contains(file_path) {
                                    ids_to_delete.push(id);
                                }
                            }
                        }
                    }
                }
            }
        }

        // Delete by IDs if any found
        if !ids_to_delete.is_empty() {
            eprintln!(
                "DEBUG delete_by_file_path: deleting {} ids",
                ids_to_delete.len()
            );
            for id in &ids_to_delete {
                eprintln!("  - {}", id);
            }
            dataset
                .delete(&format!(
                    "{} IN ('{}')",
                    ID_COLUMN,
                    ids_to_delete.join("','")
                ))
                .await
                .map_err(VectorStoreError::LanceDB)?;
        }

        Ok(())
    }

    /// Get all file hashes from a table for incremental sync.
    ///
    /// Returns a JSON string of file_path -> file_hash mapping.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    ///
    /// # Returns
    ///
    /// JSON string of path-hash mapping, or empty dict if table doesn't exist.
    pub async fn get_all_file_hashes(&self, table_name: &str) -> Result<String, VectorStoreError> {
        use futures::TryStreamExt;
        use lance::deps::arrow_array::Array;

        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Ok("{}".to_string());
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Create scanner to read id and metadata columns
        // file_path and file_hash are stored in metadata JSON
        let mut scanner = dataset.scan();
        scanner.project(&[ID_COLUMN, METADATA_COLUMN])?;

        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut hash_map = std::collections::HashMap::new();

        while let Some(batch) = stream.try_next().await.map_err(VectorStoreError::LanceDB)? {
            let metadata_col = batch.column_by_name(METADATA_COLUMN);
            let id_col = batch.column_by_name(ID_COLUMN);

            if let (Some(meta_col), Some(id_c)) = (metadata_col, id_col) {
                use lance::deps::arrow_array::StringArray;

                if let Some(metas) = meta_col.as_any().downcast_ref::<StringArray>() {
                    for i in 0..batch.num_rows() {
                        if metas.is_null(i) {
                            continue;
                        }

                        let metadata_str = metas.value(i);
                        let id = id_c
                            .as_any()
                            .downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();

                        // Parse metadata JSON to extract file_path and file_hash
                        if let Ok(metadata) =
                            serde_json::from_str::<serde_json::Value>(&metadata_str)
                        {
                            if let (Some(path), Some(hash)) = (
                                metadata.get("file_path").and_then(|v| v.as_str()),
                                metadata.get("file_hash").and_then(|v| v.as_str()),
                            ) {
                                hash_map.insert(
                                    path.to_string(),
                                    serde_json::json!({
                                        "hash": hash.to_string(),
                                        "id": id
                                    }),
                                );
                            }
                        }
                    }
                }
            }
        }

        serde_json::to_string(&hash_map).map_err(|e| VectorStoreError::General(format!("{}", e)))
    }

    /// Count documents in a table.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    ///
    /// # Returns
    ///
    /// The number of documents, or 0 if the table doesn't exist.
    pub async fn count(&self, table_name: &str) -> Result<u32, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Ok(0);
        }

        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;
        Ok(u32::try_from(
            dataset
                .count_rows(None)
                .await
                .map_err(VectorStoreError::LanceDB)?,
        )
        .unwrap_or(0))
    }

    /// Drop a table completely.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    pub async fn drop_table(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);

        // Remove from cache
        {
            let datasets = self.datasets.lock().await;
            datasets.remove(table_name);
        }

        // Delete the directory
        if table_path.exists() {
            std::fs::remove_dir_all(&table_path)?;
        }

        Ok(())
    }
}
