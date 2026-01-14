//! omni-vector - High-Performance Embedded Vector Database using LanceDB
//!
//! # Features
//!
//! - **Embedded**: No server required, runs directly on local filesystem
//! - **Arrow-Native**: Uses Apache Arrow for zero-copy data handling
//! - **High Performance**: Written in Rust with `LanceDB` for blazing fast ANN search
//! - **Async-First**: Built on tokio for concurrent operations
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-vector/src/
//! ├── lib.rs         # Main module and VectorStore
//! ├── error.rs       # VectorStoreError enum
//! ├── reader.rs      # Record batch utilities
//! ├── search.rs      # Search operations
//! └── index.rs       # Index creation operations
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_vector::VectorStore;
//!
//! let store = VectorStore::new(".cache/omni-vector").await?;
//!
//! // Add documents with embeddings
//! store.add_documents(
//!     "skills",
//!     vec!["skill-1".to_string()],
//!     vec![vec![0.1; 1536]],
//!     vec!["Content".to_string()],
//!     vec![r#"{"keywords": "test"}"#.to_string()],
//! ).await?;
//!
//! // Search
//! let results = store.search("skills", vec![0.1; 1536], 5).await?;
//! ```

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;

use lance::dataset::{Dataset, WriteParams};
use lance::deps::arrow_array::{RecordBatch, RecordBatchIterator};
use lance::deps::arrow_schema::ArrowError;

use tokio::sync::Mutex;

// ============================================================================
// Constants
// ============================================================================

/// Default embedding dimension (`OpenAI` Ada-002)
pub const DEFAULT_DIMENSION: usize = 1536;

/// Vector column name
pub const VECTOR_COLUMN: &str = "vector";
/// ID column name
pub const ID_COLUMN: &str = "id";
/// Content column name
pub const CONTENT_COLUMN: &str = "content";
/// Metadata column name
pub const METADATA_COLUMN: &str = "metadata";

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
pub use reader::{extract_optional_string, extract_string, VectorRecordBatchReader};

mod error;
mod index;
mod reader;
mod search;
