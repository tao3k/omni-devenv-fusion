use crate::contracts::{
    OmegaDecision, OmegaFallbackPolicy, OmegaRiskLevel, OmegaRoute, OmegaToolTrustClass,
};
use crate::shortcuts::WorkflowBridgeMode;

use super::super::reflection::PolicyHintDirective;

pub(crate) fn decide_for_shortcut(
    mode: WorkflowBridgeMode,
    _user_message: &str,
    tool_name: &str,
) -> OmegaDecision {
    match mode {
        WorkflowBridgeMode::Graph => OmegaDecision {
            route: OmegaRoute::Graph,
            confidence: 0.99,
            risk_level: OmegaRiskLevel::Low,
            fallback_policy: OmegaFallbackPolicy::Abort,
            tool_trust_class: OmegaToolTrustClass::Evidence,
            reason: format!(
                "explicit graph shortcut selected deterministic MCP bridge for `{tool_name}`"
            ),
            policy_id: Some("omega.shortcut.graph.v1".to_string()),
        },
        WorkflowBridgeMode::Omega => OmegaDecision {
            route: OmegaRoute::Graph,
            confidence: 0.82,
            risk_level: OmegaRiskLevel::Medium,
            fallback_policy: OmegaFallbackPolicy::SwitchToGraph,
            tool_trust_class: OmegaToolTrustClass::Verification,
            reason: format!(
                "omega governance selected MCP workflow bridge for `{tool_name}` with fallback"
            ),
            policy_id: Some("omega.shortcut.omega.v1".to_string()),
        },
    }
}

pub(crate) fn decide_for_standard_turn(force_react: bool) -> OmegaDecision {
    if force_react {
        return OmegaDecision {
            route: OmegaRoute::React,
            confidence: 1.0,
            risk_level: OmegaRiskLevel::Low,
            fallback_policy: OmegaFallbackPolicy::Abort,
            tool_trust_class: OmegaToolTrustClass::Other,
            reason: "explicit react shortcut selected standard ReAct loop".to_string(),
            policy_id: Some("omega.standard.react_shortcut.v1".to_string()),
        };
    }

    OmegaDecision {
        route: OmegaRoute::React,
        confidence: 0.74,
        risk_level: OmegaRiskLevel::Low,
        fallback_policy: OmegaFallbackPolicy::Abort,
        tool_trust_class: OmegaToolTrustClass::Other,
        reason: "default runtime policy selected ReAct loop".to_string(),
        policy_id: Some("omega.standard.default.v1".to_string()),
    }
}

pub(crate) fn apply_policy_hint(
    mut decision: OmegaDecision,
    hint: Option<&PolicyHintDirective>,
) -> OmegaDecision {
    let Some(hint) = hint else {
        return decision;
    };

    decision.route = hint.preferred_route;
    decision.confidence = (decision.confidence + hint.confidence_delta).clamp(0.05, 0.99);
    decision.risk_level = max_risk(decision.risk_level, hint.risk_floor);
    if let Some(fallback_override) = hint.fallback_override {
        decision.fallback_policy = fallback_override;
    }
    decision.tool_trust_class = hint.tool_trust_class;
    decision.reason = format!("{} [policy_hint={}]", decision.reason, hint.reason);
    decision
}

fn max_risk(current: OmegaRiskLevel, floor: OmegaRiskLevel) -> OmegaRiskLevel {
    if risk_rank(current) >= risk_rank(floor) {
        current
    } else {
        floor
    }
}

const fn risk_rank(level: OmegaRiskLevel) -> u8 {
    match level {
        OmegaRiskLevel::Low => 0,
        OmegaRiskLevel::Medium => 1,
        OmegaRiskLevel::High => 2,
        OmegaRiskLevel::Critical => 3,
    }
}

#[cfg(test)]
#[path = "../../../tests/agent/omega_decision.rs"]
mod tests;
