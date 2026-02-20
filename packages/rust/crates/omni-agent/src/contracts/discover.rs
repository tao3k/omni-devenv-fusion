use serde::{Deserialize, Serialize};

/// Confidence class attached to discover ranking output.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DiscoverConfidence {
    High,
    Medium,
    Low,
}

/// Canonical discover ranking row for tool selection.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DiscoverMatch {
    /// Canonical tool identifier (`skill.command`).
    pub tool: String,
    /// Exact usage template for tool invocation.
    pub usage: String,
    /// Raw ranking score.
    pub score: f32,
    /// Calibrated final score for decision thresholding.
    pub final_score: f32,
    /// Calibrated confidence label.
    pub confidence: DiscoverConfidence,
    /// Summary of why this tool was ranked.
    pub ranking_reason: String,
    /// Stable digest of input schema used to generate usage.
    pub input_schema_digest: String,
    /// Optional path to supporting documentation.
    pub documentation_path: Option<String>,
}
