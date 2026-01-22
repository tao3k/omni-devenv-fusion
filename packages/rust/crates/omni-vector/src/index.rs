//! Index operations for the vector store.
//!
//! Provides vector index creation for ANN search optimization.
//! Uses adaptive IVF-FLAT index with optimal partition count based on dataset size.

use lance::dataset::Dataset;
use lance::index::vector::VectorIndexParams;
use lance_index::IndexType;
use lance_index::traits::DatasetIndexExt;
use lance_linalg::distance::DistanceType;

use crate::{VECTOR_COLUMN, VectorStoreError};

/// Minimum vectors before index is useful
const MIN_VECTORS_FOR_INDEX: usize = 100;
/// Vectors per partition (heuristic)
const VECTORS_PER_PARTITION: usize = 256;
/// Max partitions to avoid over-sharding
const MAX_PARTITIONS: usize = 512;

impl crate::VectorStore {
    /// Create a vector index for a table.
    ///
    /// Creates an adaptive IVF-FLAT index with optimal partition count.
    /// Partition count = min(max(vectors / 256, 32), 512)
    ///
    /// For small datasets (< 1k vectors), flat search is typically faster.
    ///
    /// # Arguments
    ///
    /// * `table_name` - Name of the table/collection
    ///
    /// # Errors
    ///
    /// Returns [`VectorStoreError::TableNotFound`] if the table doesn't exist.
    pub async fn create_index(&self, table_name: &str) -> Result<(), VectorStoreError> {
        let table_path = self.table_path(table_name);

        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let mut dataset = Dataset::open(table_path.to_string_lossy().as_ref())
            .await
            .map_err(VectorStoreError::LanceDB)?;

        // Get row count for adaptive partition sizing
        let num_rows = dataset
            .count_rows(None)
            .await
            .map_err(VectorStoreError::LanceDB)? as usize;

        // Skip indexing for very small datasets
        if num_rows < MIN_VECTORS_FOR_INDEX {
            log::info!(
                "Table '{table_name}' has {num_rows} vectors (min: {}), skipping index creation",
                MIN_VECTORS_FOR_INDEX
            );
            return Ok(());
        }

        // Calculate adaptive partition count
        let num_partitions = (num_rows / VECTORS_PER_PARTITION).clamp(32, MAX_PARTITIONS);

        // Create IVF-FLAT index with L2 distance
        let params = VectorIndexParams::ivf_flat(num_partitions, DistanceType::L2);

        dataset
            .create_index(
                &[VECTOR_COLUMN],
                IndexType::Vector,
                None,
                &params,
                true, // replace existing index
            )
            .await
            .map_err(VectorStoreError::LanceDB)?;

        log::info!(
            "Created IVF-FLAT index for table '{table_name}' ({num_rows} vectors, {num_partitions} partitions)",
            num_rows = num_rows,
            num_partitions = num_partitions
        );

        Ok(())
    }
}
