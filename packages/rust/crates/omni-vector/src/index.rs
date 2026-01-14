//! Index operations for the vector store.
//!
//! Provides vector index creation for ANN search optimization.

use lance::dataset::Dataset;
use lance::index::vector::VectorIndexParams;
use lance_index::traits::DatasetIndexExt;
use lance_index::IndexType;
use lance_linalg::distance::DistanceType;

use crate::{VECTOR_COLUMN, VectorStoreError};

impl crate::VectorStore {
    /// Create a vector index for a table.
    ///
    /// Creates an IVF-FLAT index for efficient ANN search on large datasets.
    /// For datasets with < 10k vectors, flat search is usually sufficient.
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

        // Create IVF-FLAT index with L2 distance
        let params = VectorIndexParams::ivf_flat(128, DistanceType::L2);

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

        log::info!("Created vector index for table '{table_name}'");

        Ok(())
    }
}
