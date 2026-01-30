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
// Re-exports from skills-scanner
// ============================================================================

pub use skills_scanner::{
    DocumentScanner, SkillMetadata, SkillScanner, SkillStructure, ToolRecord, ToolsScanner,
};

// ============================================================================
// Re-exports from submodules
// ============================================================================

pub use checkpoint::{CheckpointRecord, CheckpointStore};
pub use error::VectorStoreError;
pub use keyword::{
    HybridSearchResult, KEYWORD_WEIGHT, KeywordIndex, RRF_K, SEMANTIC_WEIGHT, apply_rrf,
    apply_weighted_rrf,
};
pub use skill::ToolSearchResult;

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
    keyword_index: Option<Arc<KeywordIndex>>,
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
