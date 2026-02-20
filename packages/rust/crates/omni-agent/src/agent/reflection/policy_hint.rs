use serde::{Deserialize, Serialize};

use crate::contracts::{OmegaFallbackPolicy, OmegaRiskLevel, OmegaRoute, OmegaToolTrustClass};

use super::TurnReflection;

/// Next-turn runtime routing hint derived from completed reflection.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PolicyHintDirective {
    pub source_turn_id: u64,
    pub preferred_route: OmegaRoute,
    pub confidence_delta: f32,
    pub risk_floor: OmegaRiskLevel,
    pub fallback_override: Option<OmegaFallbackPolicy>,
    pub tool_trust_class: OmegaToolTrustClass,
    pub reason: String,
}

/// Derive a one-shot policy hint for the next turn.
#[must_use]
pub fn derive_policy_hint(
    reflection: &TurnReflection,
    source_turn_id: u64,
) -> Option<PolicyHintDirective> {
    if reflection.outcome == "error" {
        return Some(PolicyHintDirective {
            source_turn_id,
            preferred_route: OmegaRoute::Graph,
            confidence_delta: -0.18,
            risk_floor: OmegaRiskLevel::Medium,
            fallback_override: Some(OmegaFallbackPolicy::SwitchToGraph),
            tool_trust_class: OmegaToolTrustClass::Verification,
            reason: "previous_turn_error_requires_verification".to_string(),
        });
    }

    if reflection.tool_calls == 0 && reflection.confidence >= 0.8 {
        return Some(PolicyHintDirective {
            source_turn_id,
            preferred_route: OmegaRoute::React,
            confidence_delta: 0.08,
            risk_floor: OmegaRiskLevel::Low,
            fallback_override: None,
            tool_trust_class: OmegaToolTrustClass::Evidence,
            reason: "stable_turn_prefers_fast_path".to_string(),
        });
    }

    if reflection.tool_calls >= 4 || reflection.confidence < 0.45 {
        return Some(PolicyHintDirective {
            source_turn_id,
            preferred_route: OmegaRoute::Graph,
            confidence_delta: -0.1,
            risk_floor: OmegaRiskLevel::Medium,
            fallback_override: Some(OmegaFallbackPolicy::SwitchToGraph),
            tool_trust_class: OmegaToolTrustClass::Verification,
            reason: "complex_turn_prefers_structured_path".to_string(),
        });
    }

    None
}
