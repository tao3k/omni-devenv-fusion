//! Single turn in the session window.

use serde::{Deserialize, Serialize};

/// One turn (user or assistant) with optional checkpoint ref.
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
#[must_use]
pub struct TurnSlot {
    /// Role: "user" or "assistant".
    pub role: String,
    /// Message or response content.
    pub content: String,
    /// Number of tool calls in this turn.
    pub tool_count: u32,
    /// Optional memory checkpoint ID for consolidation.
    pub checkpoint_id: Option<String>,
}

impl TurnSlot {
    /// Build a turn slot from role, content, and tool count.
    pub fn new(role: &str, content: &str, tool_count: u32) -> Self {
        Self {
            role: role.to_string(),
            content: content.to_string(),
            tool_count,
            checkpoint_id: None,
        }
    }

    /// Attach a checkpoint ID to this turn.
    pub fn with_checkpoint(mut self, checkpoint_id: String) -> Self {
        self.checkpoint_id = Some(checkpoint_id);
        self
    }
}
