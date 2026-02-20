use omni_agent::{
    DiscoverConfidence, DiscoverMatch, MemoryGateDecision, MemoryGateVerdict, OmegaDecision,
    OmegaFallbackPolicy, OmegaRiskLevel, OmegaRoute, OmegaToolTrustClass,
};

#[test]
fn omega_decision_serializes_with_snake_case_enums() {
    let decision = OmegaDecision {
        route: OmegaRoute::Graph,
        confidence: 0.91,
        risk_level: OmegaRiskLevel::Medium,
        fallback_policy: OmegaFallbackPolicy::RetryReact,
        tool_trust_class: OmegaToolTrustClass::Verification,
        reason: "Long-horizon task requires graph decomposition.".to_string(),
        policy_id: Some("omega.policy.v1".to_string()),
    };

    let raw = serde_json::to_value(&decision).unwrap_or_else(|error| {
        panic!("failed to serialize omega decision: {error}");
    });

    assert_eq!(raw["route"], "graph");
    assert_eq!(raw["risk_level"], "medium");
    assert_eq!(raw["fallback_policy"], "retry_react");
    assert_eq!(raw["tool_trust_class"], "verification");
}

#[test]
fn memory_gate_decision_roundtrip_stays_stable() {
    let decision = MemoryGateDecision {
        verdict: MemoryGateVerdict::Promote,
        confidence: 0.88,
        react_evidence_refs: vec!["react:tool_retry:42".to_string()],
        graph_evidence_refs: vec!["graph:path:checkout->commit".to_string()],
        omega_factors: vec!["runtime_utility_trend=up".to_string()],
        reason: "Repeatedly validated high-value pattern.".to_string(),
        next_action: "promote".to_string(),
    };

    let raw = serde_json::to_string(&decision).unwrap_or_else(|error| {
        panic!("failed to serialize memory gate decision: {error}");
    });
    let decoded: MemoryGateDecision = serde_json::from_str(&raw).unwrap_or_else(|error| {
        panic!("failed to deserialize memory gate decision: {error}");
    });

    assert_eq!(decoded.verdict, MemoryGateVerdict::Promote);
    assert_eq!(decoded.next_action, "promote");
    assert_eq!(decoded.react_evidence_refs.len(), 1);
}

#[test]
fn discover_match_contract_carries_confidence_and_digest() {
    let row = DiscoverMatch {
        tool: "skill.discover".to_string(),
        usage: "@omni(\"skill.discover\", {\"intent\": \"<intent: string>\"})".to_string(),
        score: 0.73,
        final_score: 0.84,
        confidence: DiscoverConfidence::High,
        ranking_reason: "Strong intent overlap + schema compatibility.".to_string(),
        input_schema_digest: "sha256:abc123".to_string(),
        documentation_path: Some("/tmp/SKILL.md".to_string()),
    };

    let raw = serde_json::to_value(&row).unwrap_or_else(|error| {
        panic!("failed to serialize discover match: {error}");
    });

    assert_eq!(raw["confidence"], "high");
    assert_eq!(raw["input_schema_digest"], "sha256:abc123");
    let final_score = raw["final_score"]
        .as_f64()
        .unwrap_or_else(|| panic!("missing final_score number in serialized payload"));
    assert!((final_score - 0.84).abs() < 1e-6);
}
