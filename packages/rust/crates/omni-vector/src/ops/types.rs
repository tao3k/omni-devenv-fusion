use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Lightweight table metadata for admin and observability APIs.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableInfo {
    /// Current latest version id.
    pub version_id: u64,
    /// RFC3339 timestamp for the current commit.
    pub commit_timestamp: String,
    /// Total logical rows in the table.
    pub num_rows: u64,
    /// Debug view of current schema.
    pub schema: String,
    /// Number of fragments in the current version.
    pub fragment_count: usize,
}

/// Serializable view of historical table version metadata.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableVersionInfo {
    /// Version id in manifest history.
    pub version_id: u64,
    /// RFC3339 timestamp for that version.
    pub timestamp: String,
    /// Key/value metadata stored in the manifest.
    pub metadata: BTreeMap<String, String>,
}

/// Fragment-level stats useful for query planning and maintenance.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FragmentInfo {
    /// Fragment identifier.
    pub id: usize,
    /// Live row count after deletions.
    pub num_rows: usize,
    /// Physical row count before deletions, when available.
    pub physical_rows: Option<usize>,
    /// Number of data files owned by the fragment.
    pub num_data_files: usize,
}

/// Summary of a merge-insert (upsert) execution.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct MergeInsertStats {
    /// Number of newly inserted rows.
    pub inserted: u64,
    /// Number of updated rows.
    pub updated: u64,
    /// Number of deleted rows.
    pub deleted: u64,
    /// Number of retry attempts performed.
    pub attempts: u32,
    /// Bytes written to storage.
    pub bytes_written: u64,
    /// Number of files written.
    pub files_written: u64,
}

/// Supported logical column types for schema evolution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TableColumnType {
    /// UTF-8 string type.
    Utf8,
    /// 64-bit signed integer type.
    Int64,
    /// 64-bit floating-point type.
    Float64,
    /// Boolean type.
    Boolean,
}

/// New column definition for schema evolution.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableNewColumn {
    /// New column name.
    pub name: String,
    /// Logical column type.
    pub data_type: TableColumnType,
    /// Whether the column is nullable.
    pub nullable: bool,
}

/// Progress events for index build. Used when an optional callback is set on the store;
/// when Lance 2.x exposes a progress API, `Progress(percent)` can be emitted during build.
#[derive(Debug, Clone)]
pub enum IndexBuildProgress {
    /// Index build started.
    Started {
        /// Table being indexed.
        table_name: String,
        /// Index type (e.g. `btree`, `ivf_hnsw`).
        index_type: String,
    },
    /// Build progress (0–100). Emitted when Lance provides progress; not yet wired.
    Progress {
        /// Progress percentage 0–100.
        percent: u8,
    },
    /// Index build finished.
    Done {
        /// Build duration in milliseconds.
        duration_ms: u64,
    },
}

/// Statistics returned after creating an index (scalar or vector).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexStats {
    /// Column(s) indexed (e.g. `"skill_name"`, `"category"`).
    pub column: String,
    /// Index kind: `"btree"`, `"bitmap"`, `"inverted"`, `"vector"`.
    pub index_type: String,
    /// Build duration in milliseconds.
    pub duration_ms: u64,
}

/// Thresholds for automatic index creation and maintenance (Phase 2).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexThresholds {
    /// Create indexes when table reaches this many rows.
    pub auto_index_at: usize,
    /// Minimum rows between re-indexing.
    pub reindex_interval: usize,
    /// Maximum acceptable fragmentation (fragments / rows).
    pub max_fragmentation_ratio: f64,
}

impl Default for IndexThresholds {
    fn default() -> Self {
        Self {
            auto_index_at: 100,
            reindex_interval: 500,
            max_fragmentation_ratio: 0.01,
        }
    }
}

/// Summary of one index for health reports.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IndexStatus {
    /// Index name (e.g. `"vector"`, `"content_fts"`).
    pub name: String,
    /// Index kind (e.g. `"IVF_FLAT"`, `"Inverted"`, `"BTree"`).
    pub index_type: String,
}

/// Suggested action from [crate::VectorStore::analyze_table_health].
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Recommendation {
    /// Run compaction to reduce fragmentation.
    RunCompaction,
    /// Create missing vector/FTS/scalar indices.
    CreateIndices,
    /// Rebuild existing indices.
    RebuildIndices,
    /// Partition the table by the given column.
    Partition {
        /// Column name to partition by.
        column: String,
    },
    /// No action needed.
    None,
}

/// Per-table query metrics. In-process: updated by [crate::VectorStore::record_query] when
/// [crate::VectorStore::agentic_search] runs; can later be wired to Lance tracing when available.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct QueryMetrics {
    /// Number of agentic_search calls for this table (in-process; resets with store instance).
    pub query_count: u64,
    /// Last query latency in milliseconds.
    pub last_query_ms: Option<u64>,
}

/// Table health report from [crate::VectorStore::analyze_table_health].
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableHealthReport {
    /// Total row count.
    pub row_count: u32,
    /// Number of fragments.
    pub fragment_count: usize,
    /// Fragment count / row count (high values suggest compaction).
    pub fragmentation_ratio: f64,
    /// List of existing indices.
    pub indices_status: Vec<IndexStatus>,
    /// Suggested actions.
    pub recommendations: Vec<Recommendation>,
}

/// Index cache statistics (Lance Dataset in-memory index cache).
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct IndexCacheStats {
    /// Number of entries currently in the index cache.
    pub entry_count: usize,
    /// Cache hit ratio (0.0–1.0).
    pub hit_rate: f32,
}

/// Statistics returned after compaction (cleanup + file compaction).
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct CompactionStats {
    /// Fragment count before compaction.
    pub fragments_before: usize,
    /// Fragment count after compaction.
    pub fragments_after: usize,
    /// Fragments merged/removed by compaction.
    pub fragments_removed: usize,
    /// Bytes freed by cleanup (old versions and unreferenced files).
    pub bytes_freed: u64,
    /// Total duration in milliseconds.
    pub duration_ms: u64,
}

/// Column evolution operation for schema changes.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TableColumnAlteration {
    /// Rename a column path.
    Rename {
        /// Existing column path.
        path: String,
        /// New leaf name for the column.
        new_name: String,
    },
    /// Change nullability for a column path.
    SetNullable {
        /// Existing column path.
        path: String,
        /// Target nullability.
        nullable: bool,
    },
}
