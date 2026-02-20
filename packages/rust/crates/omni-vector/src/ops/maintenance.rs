//! Maintenance operations: auto-indexing and compaction.
//!
//! Phase 2 of the `LanceDB` 2.0 roadmap: automatic index creation when thresholds
//! are met, and table compaction to reduce fragmentation.

use std::sync::Arc;
use std::time::Instant;

use chrono::Duration as ChronoDuration;
use lance::dataset::optimize::{CompactionOptions, compact_files};
use lance_index::traits::DatasetIndexExt;

use crate::error::VectorStoreError;
use crate::ops::types::{CompactionStats, IndexStats, IndexThresholds};
use crate::{CATEGORY_COLUMN, SKILL_NAME_COLUMN, VectorStore};

#[allow(clippy::missing_errors_doc, clippy::doc_markdown)]
impl VectorStore {
    /// Returns true if the table has any vector index (e.g. IVF_FLAT, IVF_PQ).
    pub async fn has_vector_index(&self, table_name: &str) -> Result<bool, VectorStoreError> {
        let indices = self.describe_indices(table_name).await?;
        let is_vector_type = |t: &str| {
            t.contains("Vector")
                || t.contains("IVF")
                || t.contains("FLAT")
                || t.eq_ignore_ascii_case("flat")
        };
        Ok(indices.iter().any(|d| {
            let n = d.name();
            n == "vector" || n == "vector_idx" || is_vector_type(d.index_type())
        }))
    }

    /// Returns true if the table has an FTS (inverted) index on content.
    pub async fn has_fts_index(&self, table_name: &str) -> Result<bool, VectorStoreError> {
        let indices = self.describe_indices(table_name).await?;
        Ok(indices
            .iter()
            .any(|d| d.index_type() == "Inverted" || d.name() == "content_fts"))
    }

    /// Returns true if the table has any scalar index (BTree or Bitmap) on skill_name or category.
    pub async fn has_scalar_index(&self, table_name: &str) -> Result<bool, VectorStoreError> {
        let indices = self.describe_indices(table_name).await?;
        Ok(indices.iter().any(|d| {
            let t = d.index_type();
            (t == "BTree" || t == "Bitmap")
                && (d.name().contains("skill_name") || d.name().contains("category"))
        }))
    }

    /// List index descriptions for the table (empty if table missing or no indices).
    pub(crate) async fn describe_indices(
        &self,
        table_name: &str,
    ) -> Result<Vec<Arc<dyn lance_index::IndexDescription>>, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Ok(Vec::new());
        }
        let dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;
        dataset
            .describe_indices(None)
            .await
            .map_err(VectorStoreError::LanceDB)
    }

    /// Create indexes if the table meets thresholds (vector, FTS, scalar on skill_name/category).
    /// Uses [IndexThresholds] for row thresholds. Best-effort: logs and continues on per-index errors.
    pub async fn auto_index_if_needed(
        &self,
        table_name: &str,
    ) -> Result<Option<IndexStats>, VectorStoreError> {
        self.auto_index_if_needed_with_thresholds(table_name, &IndexThresholds::default())
            .await
    }

    /// Like [Self::auto_index_if_needed] with custom thresholds.
    #[allow(clippy::collapsible_if)]
    pub async fn auto_index_if_needed_with_thresholds(
        &self,
        table_name: &str,
        thresholds: &IndexThresholds,
    ) -> Result<Option<IndexStats>, VectorStoreError> {
        let count = self.count(table_name).await? as usize;
        if count < thresholds.auto_index_at {
            return Ok(None);
        }

        let mut last_stats: Option<IndexStats> = None;

        if !self.has_vector_index(table_name).await? && count >= thresholds.auto_index_at {
            if let Err(e) = self.create_index(table_name).await {
                log::warn!("auto_index: create vector index failed: {e}");
            }
        }

        if !self.has_fts_index(table_name).await? && count >= thresholds.auto_index_at {
            if let Err(e) = self.create_fts_index(table_name).await {
                log::warn!("auto_index: create FTS index failed: {e}");
            }
        }

        if !self.has_scalar_index(table_name).await?
            && count >= thresholds.auto_index_at.saturating_add(100)
        {
            if let Ok(s) = self.create_btree_index(table_name, SKILL_NAME_COLUMN).await {
                last_stats = Some(s);
            } else {
                log::warn!("auto_index: create btree index on {SKILL_NAME_COLUMN} failed");
            }
            if let Ok(s) = self.create_bitmap_index(table_name, CATEGORY_COLUMN).await {
                last_stats = Some(s);
            } else {
                log::warn!("auto_index: create bitmap index on {CATEGORY_COLUMN} failed");
            }
        }

        Ok(last_stats)
    }

    /// Run cleanup of old versions and optional file compaction; returns stats.
    pub async fn compact(&self, table_name: &str) -> Result<CompactionStats, VectorStoreError> {
        let table_path = self.table_path(table_name);
        if !table_path.exists() {
            return Err(VectorStoreError::TableNotFound(table_name.to_string()));
        }

        let start = Instant::now();
        let mut dataset = self
            .open_dataset_at_uri(table_path.to_string_lossy().as_ref())
            .await?;

        let fragments_before = dataset.get_fragments().len();

        let bytes_freed = dataset
            .cleanup_old_versions(ChronoDuration::days(7), None, None)
            .await
            .map_err(VectorStoreError::LanceDB)
            .map(|s| s.bytes_removed)?;

        let opts = CompactionOptions {
            target_rows_per_fragment: 256 * 1024,
            max_rows_per_group: 1024,
            ..Default::default()
        };
        let metrics = compact_files(&mut dataset, opts, None)
            .await
            .map_err(VectorStoreError::LanceDB)?;

        let fragments_after = dataset.get_fragments().len();
        let duration_ms = u64::try_from(start.elapsed().as_millis()).unwrap_or(u64::MAX);

        Ok(CompactionStats {
            fragments_before,
            fragments_after,
            fragments_removed: metrics.fragments_removed,
            bytes_freed,
            duration_ms,
        })
    }
}
