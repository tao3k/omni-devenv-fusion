use serde::{Deserialize, Serialize};

/// Route selected by Omega governance.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OmegaRoute {
    React,
    Graph,
}

impl OmegaRoute {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::React => "react",
            Self::Graph => "graph",
        }
    }
}

/// Risk classification emitted by Omega route policy.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OmegaRiskLevel {
    Low,
    Medium,
    High,
    Critical,
}

impl OmegaRiskLevel {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Low => "low",
            Self::Medium => "medium",
            Self::High => "high",
            Self::Critical => "critical",
        }
    }
}

/// Fallback action when selected route fails.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OmegaFallbackPolicy {
    RetryReact,
    SwitchToGraph,
    Abort,
}

impl OmegaFallbackPolicy {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::RetryReact => "retry_react",
            Self::SwitchToGraph => "switch_to_graph",
            Self::Abort => "abort",
        }
    }
}

/// Tool trust class emitted by Omega for execution governance.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum OmegaToolTrustClass {
    Evidence,
    Verification,
    Other,
}

impl OmegaToolTrustClass {
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Evidence => "evidence",
            Self::Verification => "verification",
            Self::Other => "other",
        }
    }
}

/// Decision envelope emitted by Omega.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct OmegaDecision {
    /// Selected execution route.
    pub route: OmegaRoute,
    /// Calibrated confidence for route selection.
    pub confidence: f32,
    /// Risk class for this decision.
    pub risk_level: OmegaRiskLevel,
    /// Fallback policy if execution fails.
    pub fallback_policy: OmegaFallbackPolicy,
    /// Tool trust class for this route decision.
    pub tool_trust_class: OmegaToolTrustClass,
    /// Human/audit-readable rationale.
    pub reason: String,
    /// Optional policy profile identifier.
    pub policy_id: Option<String>,
}
