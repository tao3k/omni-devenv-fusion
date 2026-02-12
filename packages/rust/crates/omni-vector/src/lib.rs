//! omni-vector - High-Performance Embedded Vector Database using LanceDB

use std::path::PathBuf;
use std::sync::Arc;

use anyhow::Result;
use dashmap::DashMap;
use lance::dataset::Dataset;
use tokio::sync::Mutex;

// ============================================================================
// Re-exports from omni-lance
// ============================================================================

pub use omni_lance::{
    CONTENT_COLUMN, DEFAULT_DIMENSION, ID_COLUMN, METADATA_COLUMN, THREAD_ID_COLUMN, VECTOR_COLUMN,
    VectorRecordBatchReader, extract_optional_string, extract_string,
};

// ============================================================================
// Re-exports from omni-scanner (Skills and Knowledge types)
// ============================================================================

pub use omni_scanner::{
    SkillMetadata as OmniSkillMetadata, SkillScanner, ToolRecord as OmniToolRecord, ToolsScanner,
};

// ============================================================================
// Module Declarations
// ============================================================================

pub use checkpoint::{CheckpointRecord, CheckpointStore};
pub use error::VectorStoreError;
pub use keyword::{
    HybridSearchResult, KEYWORD_WEIGHT, KeywordIndex, KeywordSearchBackend, RRF_K, SEMANTIC_WEIGHT,
    apply_rrf, apply_weighted_rrf,
};
pub use ops::{
    FragmentInfo, MergeInsertStats, TableColumnAlteration, TableColumnType, TableInfo,
    TableNewColumn, TableVersionInfo,
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
pub mod skill;

// ============================================================================
// Vector Store Core
// ============================================================================

/// High-performance embedded vector database using `LanceDB`.
#[derive(Clone)]
pub struct VectorStore {
    base_path: PathBuf,
    datasets: Arc<Mutex<DashMap<String, Dataset>>>,
    dimension: usize,
    /// Optional keyword index used for hybrid dense+keyword retrieval.
    pub keyword_index: Option<Arc<KeywordIndex>>,
    /// Active keyword backend strategy.
    pub keyword_backend: KeywordSearchBackend,
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
