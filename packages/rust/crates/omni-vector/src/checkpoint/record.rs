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

/// Timeline event record for time-travel visualization.
/// Contains all information needed to display a checkpoint in a timeline view.
/// V2.1: Aligned with TUI Visual Debugger requirements.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineRecord {
    /// Unique checkpoint identifier
    pub checkpoint_id: String,
    /// Parent checkpoint ID for branch visualization
    pub parent_checkpoint_id: Option<String>,
    /// Thread/session identifier
    pub thread_id: String,
    /// Step number in the execution history
    pub step: i32,
    /// Timestamp of checkpoint creation
    pub timestamp: f64,
    /// Preview of the content (truncated if too long)
    pub preview: String,
    /// Reason for this checkpoint (e.g., "AutoFix", "Manual Fork")
    pub reason: Option<String>,
}
