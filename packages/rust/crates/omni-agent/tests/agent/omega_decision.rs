use crate::contracts::{
    OmegaDecision, OmegaFallbackPolicy, OmegaRiskLevel, OmegaRoute, OmegaToolTrustClass,
};

use super::{apply_policy_hint, decide_for_standard_turn};
use crate::agent::reflection::PolicyHintDirective;

#[test]
fn standard_turn_defaults_to_other_trust_class() {
    let decision = decide_for_standard_turn(false);
    assert_eq!(decision.route, OmegaRoute::React);
    assert_eq!(decision.tool_trust_class, OmegaToolTrustClass::Other);
}

#[test]
fn apply_policy_hint_overrides_route_risk_and_trust() {
    let base = OmegaDecision {
        route: OmegaRoute::React,
        confidence: 0.74,
        risk_level: OmegaRiskLevel::Low,
        fallback_policy: OmegaFallbackPolicy::Abort,
        tool_trust_class: OmegaToolTrustClass::Other,
        reason: "base".to_string(),
        policy_id: Some("base".to_string()),
    };
    let hint = PolicyHintDirective {
        source_turn_id: 10,
        preferred_route: OmegaRoute::Graph,
        confidence_delta: -0.2,
        risk_floor: OmegaRiskLevel::High,
        fallback_override: Some(OmegaFallbackPolicy::SwitchToGraph),
        tool_trust_class: OmegaToolTrustClass::Verification,
        reason: "requires_verification".to_string(),
    };

    let decision = apply_policy_hint(base, Some(&hint));
    assert_eq!(decision.route, OmegaRoute::Graph);
    assert_eq!(decision.risk_level, OmegaRiskLevel::High);
    assert_eq!(decision.fallback_policy, OmegaFallbackPolicy::SwitchToGraph);
    assert_eq!(decision.tool_trust_class, OmegaToolTrustClass::Verification);
    assert!(
        decision
            .reason
            .contains("policy_hint=requires_verification"),
        "reason should include applied hint for observability"
    );
}
