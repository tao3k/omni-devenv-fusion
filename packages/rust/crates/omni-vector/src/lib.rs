//! omni-vector - High-Performance Embedded Vector Database using LanceDB
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-vector/src/
//! ├── lib.rs              # Main module and VectorStore struct
//! ├── error.rs            # VectorStoreError enum
//! ├── store.rs            # CRUD operations (add/delete/count)
//! ├── search.rs           # Search operations
//! ├── index.rs            # Index creation operations
//! ├── filter/             # Filter expression utilities (JSON to WHERE clause)
//! ├── skill.rs            # Skill tool indexing (uses skills-scanner crate)
//! ├── batch.rs            # RecordBatch utilities
//! ```
//!
//! Uses [omni-lance][omni_lance] for RecordBatch utilities.
//!
//! [omni_lance]: ../omni_lance/index.html

use std::path::PathBuf;
use std::sync::Arc;

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

// Re-export ToolSearchResult from skill module for Python bindings
pub use skill::ToolSearchResult;

// ============================================================================
// Re-exports from checkpoint module
// ============================================================================

pub use checkpoint::{CheckpointRecord, CheckpointStore};

// ============================================================================
// Vector Store Implementation
// ============================================================================

/// High-performance embedded vector database using `LanceDB`.
///
/// This struct provides a clean interface to `LanceDB` for storing and
/// searching vector embeddings with metadata.
///
/// # Example
///
/// ```ignore
/// use omni_vector::VectorStore;
///
/// #[tokio::main]
/// async fn main() -> Result<(), Box<dyn std::error::Error>> {
///     let store = VectorStore::new("./vector_db", Some(1536)).await?;
///     Ok(())
/// }
/// ```
#[derive(Clone)]
pub struct VectorStore {
    base_path: PathBuf,
    /// Shared dataset cache to avoid reopening tables
    datasets: Arc<Mutex<dashmap::DashMap<String, lance::dataset::Dataset>>>,
    /// Default embedding dimension
    dimension: usize,
}

// ============================================================================
// Module Declarations
// ============================================================================

pub use error::VectorStoreError;
pub mod batch;
pub mod checkpoint;
pub mod error;
pub mod filter;
pub mod index;
pub mod search;
pub mod skill;
pub mod store;

// Re-export filter utilities
pub use filter::json_to_lance_where;
