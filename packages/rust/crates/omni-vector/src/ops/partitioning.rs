//! Partitioning suggestions for large tables.
//!
//! Phase 4 of the LanceDB 2.0 roadmap: suggest a column to partition by
//! (e.g. skill_name) when the table is large enough to benefit.

use crate::error::VectorStoreError;
use crate::{CATEGORY_COLUMN, SKILL_NAME_COLUMN, VectorStore};

/// Row count above which we suggest partitioning (advisory).
const PARTITION_SUGGEST_ROW_THRESHOLD: usize = 10_000;

impl VectorStore {
    /// Suggests a column to partition the table by, if the table is large and has
    /// a partition-friendly column (e.g. skill_name, category). Returns `None` if
    /// the table does not exist, is too small, or has no such column.
    ///
    /// # Errors
    ///
    /// Returns an error when opening or counting the table fails.
    pub async fn suggest_partition_column(
        &self,
        table_name: &str,
    ) -> Result<Option<String>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(None);
        }
        let row_count = self.count(table_name).await? as usize;
        if row_count < PARTITION_SUGGEST_ROW_THRESHOLD {
            return Ok(None);
        }
        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        let schema = dataset.schema();
        if schema.field(SKILL_NAME_COLUMN).is_some() {
            return Ok(Some(SKILL_NAME_COLUMN.to_string()));
        }
        if schema.field(CATEGORY_COLUMN).is_some() {
            return Ok(Some(CATEGORY_COLUMN.to_string()));
        }
        Ok(None)
    }
}
