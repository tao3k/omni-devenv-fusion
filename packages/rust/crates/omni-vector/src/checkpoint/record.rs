//! CheckpointRecord - Data types for checkpoint persistence

use serde::{Deserialize, Serialize};

/// Checkpoint record for persistence.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CheckpointRecord {
    /// Unique checkpoint identifier
    pub checkpoint_id: String,
    /// Thread/session identifier
    pub thread_id: String,
    /// Parent checkpoint ID (for history chain)
    pub parent_id: Option<String>,
    /// Timestamp of checkpoint creation
    pub timestamp: f64,
    /// Serialized state JSON
    pub content: String,
    /// State embedding for semantic search (optional)
    pub embedding: Option<Vec<f32>>,
    /// Additional metadata (JSON serialized)
    pub metadata: Option<String>,
}
