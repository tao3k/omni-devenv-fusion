use serde::{Deserialize, Serialize};

use crate::{InjectionPolicy, PromptContextBlock, RoleMixProfile};

/// Immutable turn-level injection snapshot consumed by execution runtime.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct InjectionSnapshot {
    /// Snapshot identifier for replay/audit.
    pub snapshot_id: String,
    /// Session identifier.
    pub session_id: String,
    /// Turn sequence number in this session.
    pub turn_id: u64,
    /// Policy used to produce this snapshot.
    pub policy: InjectionPolicy,
    /// Selected role-mix profile, if any.
    pub role_mix: Option<RoleMixProfile>,
    /// Retained blocks in final snapshot.
    pub blocks: Vec<PromptContextBlock>,
    /// Aggregate chars across retained blocks.
    pub total_chars: usize,
    /// Block IDs dropped by budget policy.
    pub dropped_block_ids: Vec<String>,
    /// Block IDs truncated by budget policy.
    pub truncated_block_ids: Vec<String>,
}

impl InjectionSnapshot {
    /// Build a snapshot and compute `total_chars` from blocks.
    #[must_use]
    pub fn from_blocks(
        snapshot_id: impl Into<String>,
        session_id: impl Into<String>,
        turn_id: u64,
        policy: InjectionPolicy,
        role_mix: Option<RoleMixProfile>,
        blocks: Vec<PromptContextBlock>,
    ) -> Self {
        let total_chars = blocks.iter().map(|block| block.payload_chars).sum();
        Self {
            snapshot_id: snapshot_id.into(),
            session_id: session_id.into(),
            turn_id,
            policy,
            role_mix,
            blocks,
            total_chars,
            dropped_block_ids: Vec::new(),
            truncated_block_ids: Vec::new(),
        }
    }

    /// Validate key contract invariants for this snapshot.
    pub fn validate(&self) -> Result<(), String> {
        let computed_chars: usize = self.blocks.iter().map(|block| block.payload_chars).sum();
        if computed_chars != self.total_chars {
            return Err(format!(
                "injection snapshot total_chars mismatch: computed={computed_chars} stored={}",
                self.total_chars
            ));
        }
        if self.blocks.len() > self.policy.max_blocks {
            return Err(format!(
                "injection snapshot exceeds max_blocks: blocks={} max_blocks={}",
                self.blocks.len(),
                self.policy.max_blocks
            ));
        }
        if self.total_chars > self.policy.max_chars {
            return Err(format!(
                "injection snapshot exceeds max_chars: total_chars={} max_chars={}",
                self.total_chars, self.policy.max_chars
            ));
        }
        Ok(())
    }
}
