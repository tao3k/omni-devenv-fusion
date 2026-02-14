use crate::{
    CONTENT_COLUMN, FILE_PATH_COLUMN, ID_COLUMN, INTENTS_COLUMN, ROUTING_KEYWORDS_COLUMN,
    TOOL_NAME_COLUMN,
};

/// Tunable scanner options for vector search.
#[derive(Debug, Clone)]
pub struct SearchOptions {
    /// Optional SQL-like Lance filter (e.g. `skill_name = 'git'`).
    /// When scalar indices exist on the filtered columns, Lance can reduce rows before/during ANN.
    pub where_filter: Option<String>,
    /// Scanner batch size.
    pub batch_size: Option<usize>,
    /// Number of fragments to prefetch.
    pub fragment_readahead: Option<usize>,
    /// Number of batches to prefetch.
    pub batch_readahead: Option<usize>,
    /// Optional scan-level limit (defaults to ANN fetch count).
    pub scan_limit: Option<usize>,
    /// Projected columns for scan I/O optimization (default includes Arrow-native columns to avoid JSON parse).
    pub projected_columns: Vec<&'static str>,
    /// Columns to include in IPC output (None = all). Reduces transfer when caller needs only id, content, _distance, etc.
    pub ipc_projection: Option<Vec<String>>,
}

impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            where_filter: None,
            batch_size: Some(1024),
            fragment_readahead: Some(4),
            batch_readahead: Some(16),
            scan_limit: None,
            projected_columns: vec![
                ID_COLUMN,
                CONTENT_COLUMN,
                TOOL_NAME_COLUMN,
                FILE_PATH_COLUMN,
                ROUTING_KEYWORDS_COLUMN,
                INTENTS_COLUMN,
            ],
            ipc_projection: None,
        }
    }
}
