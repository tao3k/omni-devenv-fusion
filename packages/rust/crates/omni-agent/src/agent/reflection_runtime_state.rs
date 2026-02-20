use super::Agent;
use super::reflection::{
    PolicyHintDirective, ReflectiveRuntime, ReflectiveRuntimeError, ReflectiveRuntimeStage,
    build_turn_reflection, derive_policy_hint,
};
use crate::contracts::{OmegaFallbackPolicy, OmegaRoute};
use crate::observability::SessionEvent;

impl Agent {
    pub(super) async fn take_reflection_policy_hint(
        &self,
        session_id: &str,
    ) -> Option<PolicyHintDirective> {
        self.reflection_policy_hints
            .write()
            .await
            .remove(session_id)
    }

    pub(super) async fn reflect_turn_and_update_policy_hint(
        &self,
        session_id: &str,
        turn_id: u64,
        route: OmegaRoute,
        user_message: &str,
        assistant_signal: &str,
        outcome: &str,
        tool_calls: u32,
    ) {
        let mut runtime = ReflectiveRuntime::default();
        for stage in [
            ReflectiveRuntimeStage::Diagnose,
            ReflectiveRuntimeStage::Plan,
            ReflectiveRuntimeStage::Apply,
        ] {
            if let Err(error) = runtime.transition(stage) {
                record_reflection_transition_error(session_id, turn_id, &error);
                return;
            }
            record_reflection_transition(session_id, turn_id, stage);
        }

        let reflection = build_turn_reflection(
            route.as_str(),
            user_message,
            assistant_signal,
            outcome,
            tool_calls,
        );
        let Some(policy_hint) = derive_policy_hint(&reflection, turn_id) else {
            return;
        };
        let reason = policy_hint.reason.clone();
        let preferred_route = policy_hint.preferred_route;
        let risk_floor = policy_hint.risk_floor;
        let fallback_override = policy_hint.fallback_override;
        let tool_trust_class = policy_hint.tool_trust_class;
        self.reflection_policy_hints
            .write()
            .await
            .insert(session_id.to_string(), policy_hint);
        tracing::debug!(
            event = SessionEvent::ReflectionPolicyHintStored.as_str(),
            session_id,
            turn_id,
            preferred_route = preferred_route.as_str(),
            risk_floor = risk_floor.as_str(),
            fallback_override = fallback_override.map(OmegaFallbackPolicy::as_str),
            tool_trust_class = tool_trust_class.as_str(),
            reason = %reason,
            "reflection policy hint stored for next turn"
        );
    }
}

fn record_reflection_transition(session_id: &str, turn_id: u64, stage: ReflectiveRuntimeStage) {
    tracing::debug!(
        event = SessionEvent::ReflectionLifecycleTransition.as_str(),
        session_id,
        turn_id,
        stage = stage.as_str(),
        "reflection lifecycle transition applied"
    );
}

fn record_reflection_transition_error(
    session_id: &str,
    turn_id: u64,
    error: &ReflectiveRuntimeError,
) {
    tracing::warn!(
        event = SessionEvent::ReflectionLifecycleError.as_str(),
        session_id,
        turn_id,
        from = error.from.map(ReflectiveRuntimeStage::as_str),
        to = error.to.as_str(),
        error = %error,
        "reflection lifecycle transition rejected"
    );
}
