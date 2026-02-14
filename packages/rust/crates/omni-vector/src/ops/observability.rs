//! Observability: table health analysis and recommendations.
//!
//! Phase 5 of the LanceDB 2.0 roadmap. Query metrics are in-process (not from Lance tracing yet).

use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use crate::VectorStore;
use crate::error::VectorStoreError;
use crate::ops::types::{
    IndexCacheStats, IndexStatus, QueryMetrics, Recommendation, TableHealthReport,
};

/// Fragmentation ratio above which we recommend compaction.
const FRAGMENTATION_RATIO_THRESHOLD: f64 = 0.01;
/// Row count above which we recommend having indices.
const ROW_COUNT_INDEX_THRESHOLD: usize = 1000;

impl VectorStore {
    /// Analyze table health and return a report with recommendations.
    pub async fn analyze_table_health(
        &self,
        table_name: &str,
    ) -> Result<TableHealthReport, VectorStoreError> {
        let row_count = self.count(table_name).await?;
        let fragments = self.get_fragment_stats(table_name).await?;
        let fragment_count = fragments.len();
        let total_rows = row_count as f64;
        let fragmentation_ratio = if total_rows > 0.0 {
            fragment_count as f64 / total_rows
        } else {
            0.0
        };

        let indices = self.describe_indices(table_name).await?;
        let indices_status: Vec<IndexStatus> = indices
            .iter()
            .map(|d| IndexStatus {
                name: d.name().to_string(),
                index_type: d.index_type().to_string(),
            })
            .collect();

        let has_vector = self.has_vector_index(table_name).await?;
        let has_fts = self.has_fts_index(table_name).await?;
        let has_scalar = self.has_scalar_index(table_name).await?;
        let needs_indices = row_count as usize >= ROW_COUNT_INDEX_THRESHOLD
            && (!has_vector || !has_fts || !has_scalar);

        let mut recommendations = Vec::new();
        if fragmentation_ratio > FRAGMENTATION_RATIO_THRESHOLD {
            recommendations.push(Recommendation::RunCompaction);
        }
        if needs_indices {
            recommendations.push(Recommendation::CreateIndices);
        }
        if recommendations.is_empty() {
            recommendations.push(Recommendation::None);
        }

        Ok(TableHealthReport {
            row_count,
            fragment_count,
            fragmentation_ratio,
            indices_status,
            recommendations,
        })
    }

    /// Record a query for the table (in-process metrics). Called from agentic_search.
    pub fn record_query(&self, table_name: &str, elapsed_ms: u64) {
        let cell = self
            .query_metrics
            .entry(table_name.to_string())
            .or_insert_with(|| Arc::new((AtomicU64::new(0), AtomicU64::new(0))));
        cell.0.fetch_add(1, Ordering::Relaxed);
        cell.1.store(elapsed_ms, Ordering::Relaxed);
    }

    /// Return per-table query metrics. In-process counts and last latency from agentic_search;
    /// when Lance provides per-query tracing, this can be wired to that instead.
    pub async fn get_query_metrics(
        &self,
        table_name: &str,
    ) -> Result<QueryMetrics, VectorStoreError> {
        if let Some(cell) = self.query_metrics.get(table_name) {
            let count = cell.0.load(Ordering::Relaxed);
            let last_ms = cell.1.load(Ordering::Relaxed);
            Ok(QueryMetrics {
                query_count: count,
                last_query_ms: if last_ms == 0 { None } else { Some(last_ms) },
            })
        } else {
            Ok(QueryMetrics::default())
        }
    }

    /// Return index cache stats (entry count and hit rate) for the table's dataset.
    pub async fn get_index_cache_stats(
        &self,
        table_name: &str,
    ) -> Result<IndexCacheStats, VectorStoreError> {
        let path = self.table_path(table_name);
        let uri = path.to_string_lossy();
        let dataset = self.open_dataset_at_uri(uri.as_ref()).await?;
        let entry_count = dataset.index_cache_entry_count().await;
        let hit_rate = dataset.index_cache_hit_rate().await;
        Ok(IndexCacheStats {
            entry_count,
            hit_rate,
        })
    }
}
