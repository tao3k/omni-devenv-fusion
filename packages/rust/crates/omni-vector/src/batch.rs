//! RecordBatch utilities for LanceDB operations
//!
//! This module provides helper functions for creating and manipulating
//! Arrow RecordBatch objects for vector storage.

use std::sync::Arc;

use lance::deps::arrow_array::{Array, FixedSizeListArray, Float32Array, RecordBatch, StringArray};
use lance::deps::arrow_schema::{Field, Schema};

use crate::{DEFAULT_DIMENSION, VectorStoreError};

/// Build a RecordBatch from document components.
///
/// # Arguments
///
/// * `schema` - The Arrow schema for the batch
/// * `ids` - Document IDs
/// * `vectors` - Flattened vector data (dimension * count elements)
/// * `dimension` - Vector dimension
/// * `contents` - Text content
/// * `metadatas` - JSON metadata strings
///
/// # Errors
///
/// Returns an error if batch construction fails.
pub fn build_record_batch(
    schema: &Arc<Schema>,
    ids: Vec<String>,
    vectors: Vec<f32>,
    dimension: usize,
    contents: Vec<String>,
    metadatas: Vec<String>,
) -> Result<RecordBatch, VectorStoreError> {
    // Build Arrow arrays
    let id_array = StringArray::from(ids);
    let content_array = StringArray::from(contents);
    let metadata_array = StringArray::from(metadatas);

    // Build FixedSizeListArray from flattened vectors
    let vector_array = FixedSizeListArray::try_new(
        Arc::new(Field::new(
            "item",
            lance::deps::arrow_schema::DataType::Float32,
            true,
        )),
        i32::try_from(dimension).unwrap_or(DEFAULT_DIMENSION as i32),
        Arc::new(Float32Array::from(vectors)),
        None,
    )
    .map_err(VectorStoreError::Arrow)?;

    RecordBatch::try_new(
        schema.clone(),
        vec![
            Arc::new(id_array),
            Arc::new(vector_array),
            Arc::new(content_array),
            Arc::new(metadata_array),
        ],
    )
    .map_err(VectorStoreError::Arrow)
}

/// Create an empty RecordBatch with the given schema.
///
/// This is used for initializing new LanceDB tables.
pub fn create_empty_batch(
    schema: &Arc<Schema>,
    dimension: usize,
) -> Result<RecordBatch, VectorStoreError> {
    let arrays: Vec<Arc<dyn Array>> = vec![
        Arc::new(StringArray::from(Vec::<String>::new())) as _,
        Arc::new(FixedSizeListArray::new_null(
            Arc::new(Field::new(
                "item",
                lance::deps::arrow_schema::DataType::Float32,
                true,
            )),
            i32::try_from(dimension).unwrap_or(DEFAULT_DIMENSION as i32),
            0,
        )) as _,
        Arc::new(StringArray::from(Vec::<String>::new())) as _,
        Arc::new(StringArray::from(Vec::<String>::new())) as _,
    ];

    RecordBatch::try_new(schema.clone(), arrays).map_err(VectorStoreError::Arrow)
}
