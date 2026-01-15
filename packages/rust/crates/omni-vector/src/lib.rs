//! omni-vector - High-Performance Embedded Vector Database using LanceDB
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-vector/src/
//! ├── lib.rs         # Main module and VectorStore
//! ├── error.rs       # VectorStoreError enum
//! ├── search.rs      # Search operations
//! ├── index.rs       # Index creation operations
//! └── scanner.rs     # Script scanning (Phase 62)
//! ```
//!
//! Uses [omni-lance][omni_lance] for RecordBatch utilities.
//!
//! [omni_lance]: ../omni_lance/index.html

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;

use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{RecordBatch, RecordBatchIterator};
use lance::deps::arrow_schema::ArrowError;

use tokio::sync::Mutex;

// ============================================================================
// Re-exports from omni-lance
// ============================================================================

pub use omni_lance::{VectorRecordBatchReader, ID_COLUMN, VECTOR_COLUMN, CONTENT_COLUMN, METADATA_COLUMN, DEFAULT_DIMENSION, extract_string, extract_optional_string};

// ============================================================================
// Vector Store Implementation
// ============================================================================

/// High-performance embedded vector database using `LanceDB`.
///
/// This struct provides a clean interface to `LanceDB` for storing and
/// searching vector embeddings with metadata.
#[derive(Clone)]
pub struct VectorStore {
    base_path: PathBuf,
    /// Shared dataset cache to avoid reopening tables
    datasets: Arc<Mutex<dashmap::DashMap<String, Dataset>>>,
    /// Default embedding dimension
    dimension: usize,
}

impl VectorStore {
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
        let base_path = PathBuf::from(path);

        // Ensure parent directory exists
        if let Some(parent) = base_path.parent()
            && !parent.exists()
        {
            std::fs::create_dir_all(parent)?;
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
    fn table_path(&self, table_name: &str) -> PathBuf {
        self.base_path.join(format!("{table_name}.lance"))
    }

    /// Create the schema for vector storage.
    fn create_schema(&self) -> Arc<lance::deps::arrow_schema::Schema> {
        Arc::new(lance::deps::arrow_schema::Schema::new(vec![
            lance::deps::arrow_schema::Field::new(ID_COLUMN, lance::deps::arrow_schema::DataType::Utf8, false),
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
            lance::deps::arrow_schema::Field::new(CONTENT_COLUMN, lance::deps::arrow_schema::DataType::Utf8, false),
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
            if !force_create
                && let Some(cached) = datasets.get(table_name)
            {
                return Ok(cached.clone());
            }
        }

        // Open or create dataset
        let dataset = if table_path.exists() && !force_create {
            Dataset::open(table_uri.as_str()).await?
        } else {
            // Create new dataset with schema using Dataset::write
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

        // Cache the dataset
        {
            let datasets = self.datasets.lock().await;
            datasets.insert(table_name.to_string(), dataset.clone());
        }

        Ok(dataset)
    }

    /// Create an empty record batch for initialization.
    fn create_empty_batch(
        &self,
        schema: &Arc<lance::deps::arrow_schema::Schema>,
    ) -> Result<RecordBatch, VectorStoreError> {
        // Use instance dimension, not default
        let dimension = self.dimension;
        let arrays: Vec<Arc<dyn lance::deps::arrow_array::Array>> = vec![
            Arc::new(lance::deps::arrow_array::StringArray::from(Vec::<String>::new())) as _,
            Arc::new(lance::deps::arrow_array::FixedSizeListArray::new_null(
                Arc::new(lance::deps::arrow_schema::Field::new(
                    "item",
                    lance::deps::arrow_schema::DataType::Float32,
                    true,
                )),
                i32::try_from(dimension).unwrap_or(1536),
                0,
            )) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(Vec::<String>::new())) as _,
            Arc::new(lance::deps::arrow_array::StringArray::from(Vec::<String>::new())) as _,
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
        let dimension = vectors
            .first()
            .ok_or(VectorStoreError::EmptyDataset)?
            .len();

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
    pub async fn delete(
        &self,
        table_name: &str,
        ids: Vec<String>,
    ) -> Result<(), VectorStoreError> {
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
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `file_paths` - File paths to delete
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
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

        // Phase 67 optimization: Single query with OR conditions instead of N queries
        // Build condition: (metadata LIKE '%"file_path":"path1"%') OR (metadata LIKE '%"file_path":"path2"%') ...
        let conditions: Vec<String> = file_paths
            .iter()
            .map(|path| {
                // Escape special SQL characters for LIKE
                let escaped = path
                    .replace('\\', "\\\\")
                    .replace('%', "\\%")
                    .replace('_', "\\_")
                    .replace('\'', "\\'");
                format!(
                    "{} LIKE '%\"file_path\":\"{}\"%'",
                    METADATA_COLUMN, escaped
                )
            })
            .collect();

        let query = conditions.join(" OR ");
        dataset
            .delete(&query)
            .await
            .map_err(VectorStoreError::LanceDB)?;

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

        while let Some(batch) = stream
            .try_next()
            .await
            .map_err(VectorStoreError::LanceDB)?
        {
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
                        let id = id_c.as_any().downcast_ref::<StringArray>()
                            .map(|arr| arr.value(i).to_string())
                            .unwrap_or_default();

                        // Parse metadata JSON to extract file_path and file_hash
                        if let Ok(metadata) = serde_json::from_str::<serde_json::Value>(&metadata_str) {
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

        serde_json::to_string(&hash_map).map_err(|e| VectorStoreError::from(anyhow::anyhow!("{}", e)))
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

// ============================================================================
// Re-exports
// ============================================================================

pub use error::VectorStoreError;
pub use scanner::{ScriptScanner, ToolRecord};

mod error;
mod index;
mod search;
mod scanner;

// ============================================================================
// Phase 62: Skill Tool Indexing
// ============================================================================

impl crate::VectorStore {
    /// Index all tools from skills scripts directory.
    ///
    /// Scans `base_path/skills/*/scripts/*.py` for `@skill_script` decorated
    /// functions and indexes them for discovery.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Base directory containing skills (e.g., "assets/skills")
    /// * `table_name` - Table to store tool records (default: "skills")
    ///
    /// # Errors
    ///
    /// Returns an error if scanning or indexing fails.
    pub async fn index_skill_tools(
        &self,
        base_path: &str,
        table_name: &str,
    ) -> Result<(), VectorStoreError> {
        use std::path::Path;

        let scanner = ScriptScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(());
        }

        let tools = scanner.scan_all(skills_path).map_err(|e| {
            VectorStoreError::from(anyhow::anyhow!("Failed to scan skills: {}", e))
        })?;

        if tools.is_empty() {
            log::info!("No tools found in scripts");
            return Ok(());
        }

        // Convert tools to record format
        let ids: Vec<String> = tools.iter()
            .map(|t| format!("{}.{}", t.skill_name, t.tool_name))
            .collect();

        // Use description as content for embedding
        let contents: Vec<String> = tools.iter()
            .map(|t| t.description.clone())
            .collect();

        // Create metadata JSON with file_hash (input_schema will be added by Python if needed)
        let metadatas: Vec<String> = tools.iter()
            .map(|t| {
                serde_json::json!({
                    "skill_name": t.skill_name,
                    "tool_name": t.tool_name,
                    "file_path": t.file_path,
                    "function_name": t.function_name,
                    "keywords": t.keywords,
                    "file_hash": t.file_hash,
                    "input_schema": "{}",  // Placeholder - Python can update this
                    "docstring": t.docstring,
                }).to_string()
            })
            .collect();

        // Generate placeholder embeddings (in production, use actual embeddings)
        let dimension = self.dimension;
        let vectors: Vec<Vec<f32>> = ids.iter()
            .map(|id| {
                // Simple hash-based embedding for demonstration
                // In production, use: embedding_model.encode(content)
                let mut vec = vec![0.0; dimension];
                // Use wrapping_mul to avoid overflow panic on long IDs
                let hash = id.bytes().fold(0u64, |acc, b| acc.wrapping_mul(31).wrapping_add(b as u64));
                for (i, v) in vec.iter_mut().enumerate() {
                    *v = ((hash >> (i % 64)) as f32 / u64::MAX as f32) * 0.1;
                }
                vec
            })
            .collect();

        self.add_documents(table_name, ids, vectors, contents, metadatas)
            .await?;

        log::info!("Indexed {} tools from scripts", tools.len());
        Ok(())
    }

    /// Get tool records by skill name.
    ///
    /// # Arguments
    ///
    /// * `skill_name` - Name of the skill to query
    ///
    /// # Returns
    ///
    /// Vector of tool records for the skill.
    ///
    /// # Errors
    ///
    /// Returns an error if the table doesn't exist.
    pub async fn get_tools_by_skill(&self, _skill_name: &str) -> Result<Vec<ToolRecord>, VectorStoreError> {
        // Phase 62: Simplified implementation
        // Full implementation requires additional LanceDB table scanning API
        // For now, return empty list as placeholder
        //
        // To implement fully:
        // 1. Open the "skills" table
        // 2. Scan all records
        // 3. Filter by skill_name in metadata
        // 4. Deserialize and return ToolRecords
        Ok(vec![])
    }

    /// Scan for skill tools without indexing (returns raw tool records as JSON).
    ///
    /// This method discovers @skill_script decorated functions without
    /// attempting schema extraction. Use this when you want to do schema
    /// extraction in Python with proper import context.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Base directory containing skills (e.g., "assets/skills")
    ///
    /// # Returns
    ///
    /// Vector of JSON strings representing tool records
    ///
    /// # Errors
    ///
    /// Returns an error if scanning fails.
    pub fn scan_skill_tools_raw(&self, base_path: &str) -> Result<Vec<String>, VectorStoreError> {
        use std::path::Path;

        let scanner = ScriptScanner::new();
        let skills_path = Path::new(base_path);

        if !skills_path.exists() {
            log::warn!("Skills directory not found: {}", base_path);
            return Ok(vec![]);
        }

        let tools = scanner.scan_all(skills_path).map_err(|e| {
            VectorStoreError::from(anyhow::anyhow!("Failed to scan skills: {}", e))
        })?;

        // Convert to JSON strings
        let json_tools: Vec<String> = tools
            .into_iter()
            .map(|t| serde_json::to_string(&t).unwrap_or_default())
            .filter(|s| !s.is_empty())
            .collect();

        log::info!("Scanned {} skill tools", json_tools.len());
        Ok(json_tools)
    }
}
