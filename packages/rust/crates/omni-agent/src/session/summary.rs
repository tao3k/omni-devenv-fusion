//! Session summary segment used for rolling window compaction.

use serde::{Deserialize, Serialize};

/// Compacted summary for a drained segment of old turns.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SessionSummarySegment {
    /// Human-readable compact summary text.
    pub summary: String,
    /// Number of turns represented by this summary segment.
    pub turn_count: usize,
    /// Total tool calls observed in the drained segment.
    pub tool_calls: u32,
    /// Unix timestamp in milliseconds when this segment was created.
    pub created_at_ms: u64,
}

impl SessionSummarySegment {
    /// Build a summary segment from compacted text and basic metadata.
    pub fn new(summary: String, turn_count: usize, tool_calls: u32, created_at_ms: u64) -> Self {
        Self {
            summary,
            turn_count,
            tool_calls,
            created_at_ms,
        }
    }
}
