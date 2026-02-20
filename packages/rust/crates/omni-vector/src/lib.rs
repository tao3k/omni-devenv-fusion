//! omni-vector - High-Performance Embedded Vector Database using `LanceDB`
#![allow(clippy::doc_markdown)]

use std::path::PathBuf;
use std::sync::Arc;
use std::sync::atomic::AtomicU64;

use anyhow::Result;
use dashmap::DashMap;
use lance::dataset::Dataset;
use tokio::sync::Mutex;

use ops::DatasetCache;
use ops::DatasetCacheConfig;

// ============================================================================
// Re-exports from omni-lance
// ============================================================================

pub use omni_lance::{
    CATEGORY_COLUMN, CONTENT_COLUMN, DEFAULT_DIMENSION, FILE_PATH_COLUMN, ID_COLUMN,
    INTENTS_COLUMN, METADATA_COLUMN, ROUTING_KEYWORDS_COLUMN, SKILL_NAME_COLUMN, THREAD_ID_COLUMN,
    TOOL_NAME_COLUMN, VECTOR_COLUMN, VectorRecordBatchReader, extract_optional_string,
    extract_string,
};

// ============================================================================
// Re-exports from omni-scanner (Skills and Knowledge types)
// ============================================================================

pub use omni_scanner::skills::{
    ResourceRecord, ResourceScanner, SkillMetadata as OmniSkillMetadata, SkillScanner,
    ToolAnnotations, ToolRecord as OmniToolRecord, ToolRecord, ToolsScanner,
};

// ============================================================================
// Module Declarations
// ============================================================================

pub use checkpoint::{CheckpointRecord, CheckpointStore};
pub use error::VectorStoreError;
pub use keyword::{
    HybridSearchResult, KEYWORD_WEIGHT, KeywordIndex, KeywordSearchBackend, RRF_K, SEMANTIC_WEIGHT,
    apply_rrf, apply_weighted_rrf, distance_to_score, rrf_term, rrf_term_batch,
};
pub use ops::{
    AgenticSearchConfig, CompactionStats, FragmentInfo, IndexBuildProgress, IndexStats,
    IndexStatus, IndexThresholds, MergeInsertStats, MigrateResult, MigrationItem,
    OMNI_SCHEMA_VERSION, QueryIntent, Recommendation, TableColumnAlteration, TableColumnType,
    TableHealthReport, TableInfo, TableNewColumn, TableVersionInfo, schema_version_from_schema,
};
pub use search::SearchOptions;
pub use skill::{ToolSearchOptions, ToolSearchResult};

// ============================================================================
// Module Declarations
// ============================================================================

pub mod batch;
pub mod checkpoint;
pub mod error;
pub mod index;
pub mod keyword;
pub mod ops;
pub mod search;
pub mod search_cache;
pub mod skill;

// ============================================================================
// Vector Store Core
// ============================================================================

/// Per-table query metrics (in-process; not persisted). Used by [crate::ops::observability::get_query_metrics].
pub type QueryMetricsCell = Arc<(AtomicU64, AtomicU64)>; // (query_count, last_query_ms; 0 means None)

/// Callback for index build progress (Started / Progress / Done). Set optionally for polling or UI.
pub type IndexProgressCallback = Arc<dyn Fn(crate::ops::IndexBuildProgress) + Send + Sync>;

/// High-performance embedded vector database using `LanceDB`.
#[derive(Clone)]
pub struct VectorStore {
    base_path: PathBuf,
    datasets: Arc<Mutex<DatasetCache>>,
    dimension: usize,
    /// Optional keyword index used for hybrid dense+keyword retrieval.
    pub keyword_index: Option<Arc<KeywordIndex>>,
    /// Active keyword backend strategy.
    pub keyword_backend: KeywordSearchBackend,
    /// Optional index cache size in bytes. When set, datasets are opened via DatasetBuilder.
    pub index_cache_size_bytes: Option<usize>,
    /// In-process per-table query metrics (query_count, last_query_ms). Wired when agentic_search runs.
    pub(crate) query_metrics: Arc<DashMap<String, QueryMetricsCell>>,
    /// Optional callback for index build progress (Started/Done; Progress when Lance exposes API).
    pub(crate) index_progress_callback: Option<IndexProgressCallback>,
    /// When base_path is ":memory:", a unique id so each store uses its own temp subdir (avoids DatasetAlreadyExists).
    pub(crate) memory_mode_id: Option<u64>,
}

// ----------------------------------------------------------------------------
// Vector Store Implementations (Included via include!)
// ----------------------------------------------------------------------------

include!("ops/core.rs");
include!("ops/writer_impl.rs");
include!("ops/admin_impl.rs");
include!("skill/ops_impl.rs");
include!("search/search_impl.rs");

impl VectorStore {
    /// Check if a metadata value matches the filter conditions.
    #[must_use]
    pub fn matches_filter(metadata: &serde_json::Value, conditions: &serde_json::Value) -> bool {
        match conditions {
            serde_json::Value::Object(obj) => {
                for (key, value) in obj {
                    let meta_value = if key.contains('.') {
                        let parts: Vec<&str> = key.split('.').collect();
                        let mut current = metadata.clone();
                        for part in parts {
                            if let serde_json::Value::Object(map) = current {
                                current = map.get(part).cloned().unwrap_or(serde_json::Value::Null);
                            } else {
                                return false;
                            }
                        }
                        Some(current)
                    } else {
                        metadata.get(key).cloned()
                    };

                    if let Some(meta_val) = meta_value {
                        match (&meta_val, value) {
                            (serde_json::Value::String(mv), serde_json::Value::String(v)) => {
                                if mv != v {
                                    return false;
                                }
                            }
                            (serde_json::Value::Number(mv), serde_json::Value::Number(v)) => {
                                if mv != v {
                                    return false;
                                }
                            }
                            (serde_json::Value::Bool(mv), serde_json::Value::Bool(v)) => {
                                if mv != v {
                                    return false;
                                }
                            }
                            _ => {
                                let meta_str = meta_val.to_string().trim_matches('"').to_string();
                                let value_str = value.to_string().trim_matches('"').to_string();
                                if meta_str != value_str {
                                    return false;
                                }
                            }
                        }
                    } else {
                        return false;
                    }
                }
                true
            }
            _ => true,
        }
    }
}
