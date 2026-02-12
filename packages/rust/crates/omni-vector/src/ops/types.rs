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
