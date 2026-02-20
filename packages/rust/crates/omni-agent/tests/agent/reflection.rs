use crate::contracts::{OmegaFallbackPolicy, OmegaRiskLevel, OmegaRoute, OmegaToolTrustClass};

use super::{ReflectiveRuntime, ReflectiveRuntimeStage, build_turn_reflection, derive_policy_hint};

#[test]
fn reflective_runtime_enforces_diagnose_plan_apply_order() {
    let mut runtime = ReflectiveRuntime::default();
    assert!(runtime.transition(ReflectiveRuntimeStage::Diagnose).is_ok());
    assert!(runtime.transition(ReflectiveRuntimeStage::Plan).is_ok());
    assert!(runtime.transition(ReflectiveRuntimeStage::Apply).is_ok());
    assert_eq!(runtime.stage(), Some(ReflectiveRuntimeStage::Apply));
}

#[test]
fn reflective_runtime_rejects_illegal_transition_with_explicit_error() {
    let mut runtime = ReflectiveRuntime::default();
    let error = runtime
        .transition(ReflectiveRuntimeStage::Plan)
        .expect_err("plan before diagnose must be rejected");
    assert_eq!(error.from, None);
    assert_eq!(error.to, ReflectiveRuntimeStage::Plan);
    assert!(
        error
            .to_string()
            .contains("illegal reflection lifecycle transition"),
        "error message must be explicit for runtime diagnostics"
    );
}

#[test]
fn derive_policy_hint_prefers_verification_after_error() {
    let reflection = build_turn_reflection(
        "react",
        "run regression suite",
        "tool call failed: timeout while waiting",
        "error",
        2,
    );
    let hint = derive_policy_hint(&reflection, 42).expect("error reflection should emit a hint");
    assert_eq!(hint.source_turn_id, 42);
    assert_eq!(hint.preferred_route, OmegaRoute::Graph);
    assert_eq!(hint.risk_floor, OmegaRiskLevel::Medium);
    assert_eq!(
        hint.fallback_override,
        Some(OmegaFallbackPolicy::SwitchToGraph)
    );
    assert_eq!(hint.tool_trust_class, OmegaToolTrustClass::Verification);
}

#[test]
fn derive_policy_hint_prefers_fast_path_for_stable_tool_free_turn() {
    let reflection = build_turn_reflection(
        "react",
        "summarize key points",
        "Summary completed successfully with clear output",
        "completed",
        0,
    );
    let hint = derive_policy_hint(&reflection, 7).expect("stable turn should emit a hint");
    assert_eq!(hint.preferred_route, OmegaRoute::React);
    assert_eq!(hint.tool_trust_class, OmegaToolTrustClass::Evidence);
    assert_eq!(hint.fallback_override, None);
}

#[test]
fn reflective_runtime_long_horizon_quality_thresholds() {
    const MIN_TURNS: usize = 15;
    const MIN_HINT_COVERAGE: f32 = 0.95;
    const MIN_VERIFICATION_HINTS: usize = 10;
    const MIN_FAST_PATH_HINTS: usize = 5;

    let turn_inputs = vec![
        ("error", 2, "tool timeout while waiting for dependency"),
        (
            "completed",
            0,
            "summary completed successfully with clear output",
        ),
        (
            "completed",
            5,
            "workflow completed after multiple tool calls",
        ),
        ("error", 3, "permission denied during validation"),
        ("completed", 0, "result generated with stable confidence"),
        (
            "completed",
            4,
            "complex plan resolved with structured steps",
        ),
        ("error", 1, "unexpected failure and retry requested"),
        ("completed", 0, "concise answer completed and verified"),
        (
            "completed",
            6,
            "heavy tool chain completed with checkpoints",
        ),
        ("error", 2, "failed to parse dependency output"),
        (
            "completed",
            0,
            "stable completion with deterministic output",
        ),
        ("completed", 4, "graph-style workflow executed successfully"),
        ("error", 2, "timeout reached while waiting for callback"),
        ("completed", 0, "final summary completed with no tools"),
        (
            "completed",
            5,
            "multi-step execution completed successfully",
        ),
    ];

    assert!(
        turn_inputs.len() >= MIN_TURNS,
        "test fixture must maintain long-horizon scale"
    );

    let mut hints_emitted = 0usize;
    let mut verification_hints = 0usize;
    let mut fast_path_hints = 0usize;
    let mut transition_successes = 0usize;

    for (index, (outcome, tool_calls, assistant_message)) in turn_inputs.iter().enumerate() {
        let mut runtime = ReflectiveRuntime::default();
        runtime
            .transition(ReflectiveRuntimeStage::Diagnose)
            .expect("diagnose transition should succeed");
        transition_successes += 1;
        runtime
            .transition(ReflectiveRuntimeStage::Plan)
            .expect("plan transition should succeed");
        transition_successes += 1;
        runtime
            .transition(ReflectiveRuntimeStage::Apply)
            .expect("apply transition should succeed");
        transition_successes += 1;

        let reflection = build_turn_reflection(
            "react",
            &format!("long-horizon objective #{index}"),
            assistant_message,
            outcome,
            *tool_calls,
        );
        let hint = derive_policy_hint(&reflection, (index + 1) as u64);
        if let Some(hint) = hint {
            hints_emitted += 1;
            match hint.tool_trust_class {
                OmegaToolTrustClass::Verification => verification_hints += 1,
                OmegaToolTrustClass::Evidence => fast_path_hints += 1,
                OmegaToolTrustClass::Other => {}
            }
        }
    }

    let hint_coverage = hints_emitted as f32 / turn_inputs.len() as f32;
    assert!(
        hint_coverage >= MIN_HINT_COVERAGE,
        "hint coverage below threshold: {hint_coverage:.2} < {MIN_HINT_COVERAGE:.2}"
    );
    assert!(
        verification_hints >= MIN_VERIFICATION_HINTS,
        "verification hints below threshold: {verification_hints} < {MIN_VERIFICATION_HINTS}"
    );
    assert!(
        fast_path_hints >= MIN_FAST_PATH_HINTS,
        "fast-path hints below threshold: {fast_path_hints} < {MIN_FAST_PATH_HINTS}"
    );
    assert_eq!(
        transition_successes,
        turn_inputs.len() * 3,
        "each long-horizon turn must execute diagnose->plan->apply transitions"
    );
}
