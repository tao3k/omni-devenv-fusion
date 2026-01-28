//! Vector search operations using LanceDB.
//!
//! Provides nearest neighbor search using LanceDB 1.0's scanner API.

use futures::TryStreamExt;
use lance::dataset::Dataset;
use lance::deps::arrow_array::{Array, Float32Array, StringArray};

use crate::{CONTENT_COLUMN, ID_COLUMN, METADATA_COLUMN, VECTOR_COLUMN};
use omni_types::VectorSearchResult;

/// Multiplier for fetch count to account for filtering loss
const FETCH_MULTIPLIER: usize = 2;

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
    ) -> Result<Vec<VectorSearchResult>, crate::VectorStoreError> {
        self.search_with_keywords(table_name, query, Vec::new(), limit, None)
            .await
    }

    /// Search with metadata filtering.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    /// * `query` - Query vector
    /// * `limit` - Maximum number of results
    /// * `where_filter` - Optional metadata filter as JSON string
    ///
    /// # Returns
    ///
    /// Vector of search results filtered by metadata
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn search_filtered(
        &self,
        table_name: &str,
        query: Vec<f32>,
        limit: usize,
        where_filter: Option<String>,
    ) -> Result<Vec<VectorSearchResult>, crate::VectorStoreError> {
        self.search_with_keywords(table_name, query, Vec::new(), limit, where_filter)
            .await
    }

    /// Internal search implementation with optional keyword boosting and metadata filtering.
    async fn search_with_keywords(
        &self,
        table_name: &str,
        query: Vec<f32>,
        _keywords: Vec<String>,
        limit: usize,
        where_filter: Option<String>,
    ) -> Result<Vec<VectorSearchResult>, crate::VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(crate::VectorStoreError::TableNotFound(
                table_name.to_string(),
            ));
        }

        // Open dataset
        let dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(crate::VectorStoreError::LanceDB)?;

        // Build query vector array
        let query_arr = Float32Array::from(query);

        // Create scanner and execute nearest neighbor search
        let mut scanner = dataset.scan();
        let fetch_count = limit.saturating_mul(FETCH_MULTIPLIER).max(limit + 10);
        scanner
            .nearest(VECTOR_COLUMN, &query_arr, fetch_count)
            .map_err(crate::VectorStoreError::LanceDB)?;

        // Get results as stream
        let mut stream = scanner
            .try_into_stream()
            .await
            .map_err(crate::VectorStoreError::LanceDB)?;

        // Parse where_filter if provided
        let filter_conditions = where_filter
            .as_ref()
            .map(|f| serde_json::from_str::<serde_json::Value>(f).ok())
            .flatten();

        let mut results = Vec::new();

        // Process record batches
        while let Some(batch) = stream
            .try_next()
            .await
            .map_err(crate::VectorStoreError::LanceDB)?
        {
            // Extract columns
            let id_col = batch.column_by_name(ID_COLUMN).ok_or_else(|| {
                crate::VectorStoreError::TableNotFound("id column not found".to_string())
            })?;
            let content_col = batch.column_by_name(CONTENT_COLUMN).ok_or_else(|| {
                crate::VectorStoreError::TableNotFound("content column not found".to_string())
            })?;
            let distance_col = batch.column_by_name("_distance").ok_or_else(|| {
                crate::VectorStoreError::TableNotFound("_distance column not found".to_string())
            })?;
            let metadata_col = batch.column_by_name(METADATA_COLUMN);

            let ids = id_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    crate::VectorStoreError::TableNotFound(
                        "id column is not StringArray".to_string(),
                    )
                })?;
            let contents = content_col
                .as_any()
                .downcast_ref::<StringArray>()
                .ok_or_else(|| {
                    crate::VectorStoreError::TableNotFound(
                        "content column is not StringArray".to_string(),
                    )
                })?;
            let distances = distance_col
                .as_any()
                .downcast_ref::<Float32Array>()
                .ok_or_else(|| {
                    crate::VectorStoreError::TableNotFound(
                        "distance column is not Float32Array".to_string(),
                    )
                })?;

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

                // Apply where_filter if specified
                if let Some(ref conditions) = filter_conditions {
                    if !crate::VectorStore::matches_filter(&metadata, conditions) {
                        continue; // Skip this result
                    }
                }

                results.push(VectorSearchResult {
                    id: ids.value(i).to_string(),
                    content: contents.value(i).to_string(),
                    metadata,
                    distance: f64::from(distances.value(i)),
                });
            }
        }

        // Sort by distance (smaller is better for cosine)
        results.sort_by(|a, b| {
            a.distance
                .partial_cmp(&b.distance)
                .unwrap_or(std::cmp::Ordering::Equal)
        });

        // Limit results after sorting
        results.truncate(limit);

        Ok(results)
    }
}

#[cfg(test)]
mod tests {

    #[tokio::test]
    async fn test_search_basic() {
        let temp_dir = tempfile::TempDir::new().unwrap();
        let store = crate::VectorStore::new(temp_dir.path().to_str().unwrap(), None)
            .await
            .unwrap();

        // Add test document (use 1024 dimension to match DEFAULT_DIMENSION)
        store
            .add_documents(
                "test",
                vec!["doc1".to_string()],
                vec![vec![0.1; 1024]],
                vec!["test content".to_string()],
                vec![r#"{"category": "test"}"#.to_string()],
            )
            .await
            .unwrap();

        // Search should return results
        let results = store.search("test", vec![0.1; 1024], 5).await.unwrap();

        assert!(!results.is_empty());
        assert_eq!(results[0].id, "doc1");
    }

    #[tokio::test]
    async fn test_search_empty_table() {
        let temp_dir = tempfile::TempDir::new().unwrap();
        let store = crate::VectorStore::new(temp_dir.path().to_str().unwrap(), None)
            .await
            .unwrap();

        let result = store.search("nonexistent", vec![0.1; 1024], 5).await;

        assert!(result.is_err());
        if let Err(e) = result {
            let err_msg = format!("{:?}", e);
            assert!(
                err_msg.contains("TableNotFound"),
                "Expected TableNotFound error, got: {}",
                err_msg
            );
        }
    }
}
