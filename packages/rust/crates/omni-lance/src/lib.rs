//! `LanceDB` `RecordBatch` utilities.
//!
//! Provides Arrow record batch helpers for `LanceDB` vector storage.
//!
//! **Embedding Configuration**:
//! - Default dimension: 1024 (configured via settings.yaml)
//! - LLM-based embedding: MiniMax-M2.1 generates 16 core values -> expanded to 1024
//! - Storage: `FixedSizeListArray<f32>` with configured dimension

use std::sync::Arc;

use lance::deps::arrow_array::{
    Array, FixedSizeListArray, Float32Array, RecordBatch, RecordBatchReader, StringArray,
};
use lance::deps::arrow_schema::{ArrowError, DataType, Field, Schema};

/// Vector column name
pub const VECTOR_COLUMN: &str = "vector";
/// ID column name
pub const ID_COLUMN: &str = "id";
/// Content column name
pub const CONTENT_COLUMN: &str = "content";
/// Metadata column name
pub const METADATA_COLUMN: &str = "metadata";
/// Thread ID column name (for checkpoint filtering)
pub const THREAD_ID_COLUMN: &str = "thread_id";
/// Skill name column (for scalar index / filtering)
pub const SKILL_NAME_COLUMN: &str = "skill_name";
/// Category column (for scalar index / filtering)
pub const CATEGORY_COLUMN: &str = "category";
/// Tool name (e.g. skill.command) – Arrow-native, avoids JSON parse in read path
pub const TOOL_NAME_COLUMN: &str = "tool_name";
/// File path – Arrow-native
pub const FILE_PATH_COLUMN: &str = "file_path";
/// Routing keywords, space-joined – Arrow-native
pub const ROUTING_KEYWORDS_COLUMN: &str = "routing_keywords";
/// Intents, " | "-joined – Arrow-native
pub const INTENTS_COLUMN: &str = "intents";

/// Default embedding dimension (LLM-generated semantic vector)
pub const DEFAULT_DIMENSION: usize = 1024;

/// A record batch reader for vector store data.
pub struct VectorRecordBatchReader {
    schema: Arc<Schema>,
    batches: Vec<RecordBatch>,
    current_batch: usize,
}

impl VectorRecordBatchReader {
    /// Create a new reader from a vector store batch.
    #[must_use]
    pub fn new(schema: Arc<Schema>, batches: Vec<RecordBatch>) -> Self {
        Self {
            schema,
            batches,
            current_batch: 0,
        }
    }

    /// Create a reader from individual vectors.
    ///
    /// # Errors
    ///
    /// Returns an error when:
    /// - `dimension` cannot be represented as `i32`.
    /// - Arrow array or `RecordBatch` construction fails.
    pub fn from_vectors(
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
        dimension: usize,
    ) -> Result<Self, ArrowError> {
        let dimension_i32 = dimension_to_i32(dimension)?;
        let id_array = StringArray::from(ids);
        let content_array = StringArray::from(contents);
        let metadata_array = StringArray::from(metadatas);

        // Flatten vectors
        let flat_values: Vec<f32> = vectors.into_iter().flatten().collect();
        let vector_array = FixedSizeListArray::try_new(
            Arc::new(Field::new("item", DataType::Float32, true)),
            dimension_i32,
            Arc::new(Float32Array::from(flat_values)),
            None,
        )?;

        let schema = Arc::new(Schema::new(vec![
            Field::new(ID_COLUMN, DataType::Utf8, false),
            Field::new(
                VECTOR_COLUMN,
                DataType::FixedSizeList(
                    Arc::new(Field::new("item", DataType::Float32, true)),
                    dimension_i32,
                ),
                false,
            ),
            Field::new(CONTENT_COLUMN, DataType::Utf8, false),
            Field::new(METADATA_COLUMN, DataType::Utf8, true),
        ]));

        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(id_array),
                Arc::new(vector_array),
                Arc::new(content_array),
                Arc::new(metadata_array),
            ],
        )?;

        Ok(Self {
            schema,
            batches: vec![batch],
            current_batch: 0,
        })
    }

    /// Get the default schema for vector storage.
    ///
    /// # Errors
    ///
    /// Returns an error when `dimension` cannot be represented as `i32`.
    pub fn default_schema(dimension: usize) -> Result<Arc<Schema>, ArrowError> {
        let dimension_i32 = dimension_to_i32(dimension)?;
        Ok(Arc::new(Schema::new(vec![
            Field::new(ID_COLUMN, DataType::Utf8, false),
            Field::new(
                VECTOR_COLUMN,
                DataType::FixedSizeList(
                    Arc::new(Field::new("item", DataType::Float32, true)),
                    dimension_i32,
                ),
                false,
            ),
            Field::new(CONTENT_COLUMN, DataType::Utf8, false),
            Field::new(METADATA_COLUMN, DataType::Utf8, true),
        ])))
    }
}

impl Iterator for VectorRecordBatchReader {
    type Item = Result<RecordBatch, lance::deps::arrow_schema::ArrowError>;

    fn next(&mut self) -> Option<Self::Item> {
        if self.current_batch >= self.batches.len() {
            return None;
        }
        let batch = self.batches[self.current_batch].clone();
        self.current_batch += 1;
        Some(Ok(batch))
    }
}

impl RecordBatchReader for VectorRecordBatchReader {
    fn schema(&self) -> Arc<Schema> {
        self.schema.clone()
    }
}

/// Extract string values from a `StringArray` at a specific index.
#[must_use]
pub fn extract_string(array: &StringArray, index: usize) -> String {
    if array.is_null(index) {
        String::new()
    } else {
        array.value(index).to_string()
    }
}

/// Extract optional string from metadata column.
#[must_use]
pub fn extract_optional_string(array: Option<&StringArray>, index: usize) -> Option<String> {
    array.and_then(|arr| {
        if arr.is_null(index) {
            None
        } else {
            Some(arr.value(index).to_string())
        }
    })
}

fn dimension_to_i32(dimension: usize) -> Result<i32, ArrowError> {
    i32::try_from(dimension).map_err(|_| {
        ArrowError::InvalidArgumentError(format!(
            "embedding dimension {dimension} exceeds i32::MAX"
        ))
    })
}
