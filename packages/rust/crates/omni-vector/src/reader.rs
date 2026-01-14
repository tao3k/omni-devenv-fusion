//! Utilities for working with Arrow record batches.

use std::sync::Arc;

use lance::deps::arrow_array::{
    Array, FixedSizeListArray, Float32Array, RecordBatch, RecordBatchReader, StringArray,
};
use lance::deps::arrow_schema::{DataType, Field, Schema};

use crate::{CONTENT_COLUMN, ID_COLUMN, METADATA_COLUMN, VECTOR_COLUMN};

/// A record batch reader for vector store data.
pub struct VectorRecordBatchReader {
    schema: Arc<Schema>,
    batches: Vec<RecordBatch>,
    current_batch: usize,
}

impl VectorRecordBatchReader {
    /// Create a new reader from a vector store batch.
    pub fn new(schema: Arc<Schema>, batches: Vec<RecordBatch>) -> Self {
        Self {
            schema,
            batches,
            current_batch: 0,
        }
    }

    /// Create a reader from individual vectors.
    pub fn from_vectors(
        ids: Vec<String>,
        vectors: Vec<Vec<f32>>,
        contents: Vec<String>,
        metadatas: Vec<String>,
        dimension: usize,
    ) -> Result<Self, lance::deps::arrow_schema::ArrowError> {
        let id_array = StringArray::from(ids);
        let content_array = StringArray::from(contents);
        let metadata_array = StringArray::from(metadatas);

        // Flatten vectors
        let flat_values: Vec<f32> = vectors.into_iter().flatten().collect();
        let vector_array = FixedSizeListArray::try_new(
            Arc::new(Field::new("item", DataType::Float32, true)),
            dimension as i32,
            Arc::new(Float32Array::from(flat_values)),
            None,
        )?;

        let schema = Arc::new(Schema::new(vec![
            Field::new(ID_COLUMN, DataType::Utf8, false),
            Field::new(
                VECTOR_COLUMN,
                DataType::FixedSizeList(
                    Arc::new(Field::new("item", DataType::Float32, true)),
                    dimension as i32,
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

/// Extract string values from a StringArray at a specific index.
pub fn extract_string(array: &StringArray, index: usize) -> String {
    if array.is_null(index) {
        String::new()
    } else {
        array.value(index).to_string()
    }
}

/// Extract optional string from metadata column.
pub fn extract_optional_string(array: Option<&StringArray>, index: usize) -> Option<String> {
    array.and_then(|arr| {
        if arr.is_null(index) {
            None
        } else {
            Some(arr.value(index).to_string())
        }
    })
}
