//! Search operations for the vector store.
//!
//! Provides nearest neighbor search using LanceDB 1.0's scanner API.

use lance::dataset::Dataset;
use lance::deps::arrow_array::{Array, Float32Array, StringArray};
use futures::TryStreamExt;

use omni_types::VectorSearchResult;

use crate::{ID_COLUMN, CONTENT_COLUMN, METADATA_COLUMN, VECTOR_COLUMN, VectorStoreError};

impl crate::VectorStore {
    /// Search for similar documents.
    ///
    /// Performs nearest neighbor search using `LanceDB` 1.0's scanner API.
    /// Supports flat search (brute force) for small datasets and ANN search
    /// when an index is created.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `query` - Query vector
    /// * `limit` - Maximum number of results
    ///
    /// # Returns
    ///
    /// Vector of search results sorted by similarity (distance)
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn search(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
    ) -> Result<Vec<VectorSearchResult>, VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        // Open dataset
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Build query vector array
        let query_arr = Float32Array::from(query);

        // Create scanner and execute nearest neighbor search
        let mut scanner = dataset.scan();
        scanner
            .nearest(VECTOR_COLUMN, &query_arr, limit)
            .map_err(VectorStoreError::LanceDB)?;

        // Get results as stream
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let mut results = Vec::new();

        // Process record batches
        while let Some(batch) = stream
            .try_next()
            .await
            .map_err(VectorStoreError::LanceDB)?
        {
            // Extract columns
            let id_col = batch
                .column_by_name(ID_COLUMN)
                .ok_or_else(|| VectorStoreError::TableNotFound("id column not found".to_string()))?;
            let content_col = batch
                .column_by_name(CONTENT_COLUMN)
                .ok_or_else(|| VectorStoreError::TableNotFound("content column not found".to_string()))?;
            let distance_col = batch
                .column_by_name("_distance")
                .ok_or_else(|| VectorStoreError::TableNotFound("_distance column not found".to_string()))?;
            let metadata_col = batch.column_by_name(METADATA_COLUMN);

            let ids = id_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| VectorStoreError::TableNotFound("id column is not StringArray".to_string()))?;
            let contents = content_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| VectorStoreError::TableNotFound("content column is not StringArray".to_string()))?;
            let distances = distance_col
                .as_any()
                .downcast_ref::<Float32Array>()
                .ok_or_else(|| VectorStoreError::TableNotFound("distance column is not Float32Array".to_string()))?;

            for i in 0..batch.num_rows() {
                // Extract metadata if present
                let metadata = if let Some(meta_col) = metadata_col {
                    if let Some(meta_arr) = meta_col.as_any().downcast_ref::<StringArray>() {
                        if meta_arr.is_null(i) {
                            serde_json::Value::Null
                        } else {
                            let meta_str = meta_arr.value(i);
                            serde_json::from_str(meta_str).unwrap_or_default()
                        }
                    } else {
                        serde_json::Value::Null
                    }
                } else {
                    serde_json::Value::Null
                };

                results.push(VectorSearchResult {
                    id: ids.value(i).to_string(),
                    content: contents.value(i).to_string(),
                    metadata,
                    distance: f64::from(distances.value(i)),
                });
            }
        }

        Ok(results)
    }
}
