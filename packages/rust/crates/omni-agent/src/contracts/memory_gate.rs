use serde::{Deserialize, Serialize};

/// 3-in-1 gate verdict for short-term memory lifecycle.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryGateVerdict {
    Retain,
    Obsolete,
    Promote,
}

/// Evidence-based gate decision emitted after turn reflection.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MemoryGateDecision {
    /// Final verdict.
    pub verdict: MemoryGateVerdict,
    /// Confidence for this verdict.
    pub confidence: f32,
    /// ReAct evidence references.
    pub react_evidence_refs: Vec<String>,
    /// Graph evidence references.
    pub graph_evidence_refs: Vec<String>,
    /// Omega factors and notes.
    pub omega_factors: Vec<String>,
    /// Audit reason.
    pub reason: String,
    /// Next action command (`retain`, `obsolete`, `promote`).
    pub next_action: String,
}
