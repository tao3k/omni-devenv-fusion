use crate::{CONTENT_COLUMN, ID_COLUMN, METADATA_COLUMN};

/// Tunable scanner options for vector search.
#[derive(Debug, Clone)]
pub struct SearchOptions {
    /// Optional SQL-like Lance filter expression or JSON metadata filter.
    pub where_filter: Option<String>,
    /// Scanner batch size.
    pub batch_size: Option<usize>,
    /// Number of fragments to prefetch.
    pub fragment_readahead: Option<usize>,
    /// Number of batches to prefetch.
    pub batch_readahead: Option<usize>,
    /// Optional scan-level limit (defaults to ANN fetch count).
    pub scan_limit: Option<usize>,
    /// Projected columns for scan I/O optimization.
    pub projected_columns: Vec<&'static str>,
}

impl Default for SearchOptions {
    fn default() -> Self {
        Self {
            where_filter: None,
            batch_size: Some(1024),
            fragment_readahead: Some(4),
            batch_readahead: Some(16),
            scan_limit: None,
            projected_columns: vec![ID_COLUMN, CONTENT_COLUMN, METADATA_COLUMN],
        }
    }
}
