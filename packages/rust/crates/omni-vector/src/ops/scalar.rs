//! Scalar index operations: `BTree`, `Bitmap`, and optimal type selection.
//!
//! Provides structured APIs and statistics for `LanceDB` 2.0 scalar indices
//! used to accelerate exact match and low-cardinality filters (e.g. `skill_name`, `category`).

use std::collections::HashSet;
use std::time::Instant;

use futures::TryStreamExt;
use lance_index::IndexType;
use lance_index::scalar::{BuiltinIndexType, ScalarIndexParams};
use lance_index::traits::DatasetIndexExt;

use crate::VectorStore;
use crate::error::VectorStoreError;

use super::types::{IndexBuildProgress, IndexStats};

/// Cardinality threshold below which Bitmap index is preferred (low-cardinality columns).
const BITMAP_CARDINALITY_THRESHOLD: usize = 100;
/// Cardinality above which we still use `BTree` but log that partitioning may help.
const HIGH_CARDINALITY_THRESHOLD: usize = 10_000;
/// Sample size for cardinality estimation (distinct count over first N rows).
const CARDINALITY_SAMPLE_LIMIT: i64 = 2000;

#[allow(clippy::missing_errors_doc, clippy::doc_markdown)]
impl VectorStore {
    /// Create a BTree index on a column for exact match and range queries.
    ///
    /// Accelerates: `column = value`, `BETWEEN`, `IN`, `IS NULL`.
    pub async fn create_btree_index(
        &self,
        table_name: &str,
        column: &str,
    ) -> Result<IndexStats, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let params = ScalarIndexParams::for_builtin(BuiltinIndexType::BTree);
        let index_name = format!("scalar_{column}_btree");

        if let Some(ref cb) = self.index_progress_callback {
            cb(IndexBuildProgress::Started {
                table_name: table_name.to_string(),
                index_type: "btree".to_string(),
            });
        }

        let start = Instant::now();
        dataset
            .create_index(&[column], IndexType::BTree, Some(index_name), &params, true)
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let duration_ms = u64::try_from(start.elapsed().as_millis()).unwrap_or(u64::MAX);
        if let Some(ref cb) = self.index_progress_callback {
            cb(IndexBuildProgress::Done { duration_ms });
        }

        Ok(IndexStats {
            column: column.to_string(),
            index_type: "btree".to_string(),
            duration_ms,
        })
    }

    /// Create a Bitmap index on a column for low-cardinality filters.
    ///
    /// Best for: category, status, enum-like columns (few unique values).
    pub async fn create_bitmap_index(
        &self,
        table_name: &str,
        column: &str,
    ) -> Result<IndexStats, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let params = ScalarIndexParams::for_builtin(BuiltinIndexType::Bitmap);
        let index_name = format!("scalar_{column}_bitmap");

        if let Some(ref cb) = self.index_progress_callback {
            cb(IndexBuildProgress::Started {
                table_name: table_name.to_string(),
                index_type: "bitmap".to_string(),
            });
        }

        let start = Instant::now();
        dataset
            .create_index(
                &[column],
                IndexType::Bitmap,
                Some(index_name),
                &params,
                true,
            )
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let duration_ms = u64::try_from(start.elapsed().as_millis()).unwrap_or(u64::MAX);
        if let Some(ref cb) = self.index_progress_callback {
            cb(IndexBuildProgress::Done { duration_ms });
        }

        Ok(IndexStats {
            column: column.to_string(),
            index_type: "bitmap".to_string(),
            duration_ms,
        })
    }

    /// Estimate the number of distinct values in a column (sample-based).
    ///
    /// Used by `create_optimal_scalar_index` to choose BTree vs Bitmap.
    pub async fn estimate_cardinality(
        &self,
        table_name: &str,
        column: &str,
    ) -> Result<usize, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let mut scanner = dataset.scan();
        scanner.project(&[column])?;
        scanner.limit(Some(CARDINALITY_SAMPLE_LIMIT), None)?;
        let mut stream = scanner.try_into_stream().await?;

        let mut distinct = HashSet::new();
        while let Some(batch) = stream.try_next().await? {
            let col = batch
                .column_by_name(column)
                .ok_or_else(|| VectorStoreError::General(format!("Column '{column}' not found")))?;
            let n = col.len();
            for i in 0..n {
                let s = crate::ops::get_utf8_at(col.as_ref(), i);
                if !s.is_empty() {
                    distinct.insert(s);
                }
            }
        }
        Ok(distinct.len())
    }

    /// Create the best scalar index type for a column based on estimated cardinality.
    ///
    /// - Low cardinality (&lt; 100): Bitmap.
    /// - Otherwise: BTree.
    pub async fn create_optimal_scalar_index(
        &self,
        table_name: &str,
        column: &str,
    ) -> Result<IndexStats, VectorStoreError> {
        let cardinality = self.estimate_cardinality(table_name, column).await?;

        let stats = if cardinality < BITMAP_CARDINALITY_THRESHOLD {
            self.create_bitmap_index(table_name, column).await?
        } else {
            if cardinality >= HIGH_CARDINALITY_THRESHOLD {
                log::warn!(
                    "High cardinality column '{column}' (est. {cardinality}) may benefit from partitioning"
                );
            }
            self.create_btree_index(table_name, column).await?
        };

        Ok(stats)
    }
}
