use serde::{Deserialize, Serialize};

const OBJECTIVE_MAX_CHARS: usize = 160;
const RESULT_MAX_CHARS: usize = 220;

/// Structured turn-level reflection payload for memory self-evolution.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TurnReflection {
    pub schema: &'static str,
    pub route: String,
    pub objective: String,
    pub result_signal: String,
    pub outcome: String,
    pub tool_calls: u32,
    pub confidence: f32,
    pub next_action: String,
}

/// Build deterministic reflection from one completed turn.
pub fn build_turn_reflection(
    route: &str,
    user_message: &str,
    assistant_message: &str,
    outcome: &str,
    tool_calls: u32,
) -> TurnReflection {
    let normalized_outcome = normalize_outcome(outcome);
    let confidence = infer_confidence(normalized_outcome, assistant_message, tool_calls);
    let next_action = infer_next_action(normalized_outcome, assistant_message, tool_calls);

    TurnReflection {
        schema: "omni.agent.reflection.v1",
        route: route.trim().to_lowercase(),
        objective: truncate(user_message.trim(), OBJECTIVE_MAX_CHARS),
        result_signal: truncate(&squash_whitespace(assistant_message), RESULT_MAX_CHARS),
        outcome: normalized_outcome.to_string(),
        tool_calls,
        confidence,
        next_action,
    }
}

/// Render a compact markdown block for user-visible or logging output.
#[allow(dead_code)]
pub fn render_turn_reflection_block(reflection: &TurnReflection) -> String {
    format!(
        "### Reflection\n- route: `{}`\n- outcome: `{}` confidence=`{:.2}` tool_calls=`{}`\n- objective: {}\n- next_action: {}",
        reflection.route,
        reflection.outcome,
        reflection.confidence,
        reflection.tool_calls,
        reflection.objective,
        reflection.next_action
    )
}

/// Render reflection for memory episode experience append.
#[allow(dead_code)]
pub fn render_turn_reflection_for_memory(reflection: &TurnReflection) -> String {
    format!(
        "[reflection]\nroute={}\noutcome={}\nconfidence={:.2}\ntool_calls={}\nobjective={}\nnext_action={}",
        reflection.route,
        reflection.outcome,
        reflection.confidence,
        reflection.tool_calls,
        reflection.objective,
        reflection.next_action
    )
}

fn normalize_outcome(outcome: &str) -> &'static str {
    let normalized = outcome.trim().to_ascii_lowercase();
    match normalized.as_str() {
        "error" | "failure" | "failed" => "error",
        _ => "completed",
    }
}

fn infer_confidence(outcome: &str, assistant_message: &str, tool_calls: u32) -> f32 {
    let mut score: f32 = if outcome == "error" { 0.28 } else { 0.82 };
    let lower = assistant_message.to_ascii_lowercase();
    if lower.contains("maybe") || lower.contains("unclear") || lower.contains("not sure") {
        score -= 0.12;
    }
    if lower.contains("timeout") || lower.contains("failed") || lower.contains("error") {
        score -= 0.18;
    }
    if tool_calls >= 6 {
        score -= 0.06;
    }
    round2(score.clamp(0.05, 0.98))
}

fn infer_next_action(outcome: &str, assistant_message: &str, tool_calls: u32) -> String {
    let lower = assistant_message.to_ascii_lowercase();
    if outcome == "error" {
        if lower.contains("timeout") {
            return "Retry with reduced scope and explicit timeout budget.".to_string();
        }
        if lower.contains("permission") || lower.contains("denied") {
            return "Fix authorization/config first, then replay the same step.".to_string();
        }
        return "Narrow the task and rerun with deterministic tool arguments.".to_string();
    }
    if tool_calls == 0 {
        return "Validate result quickly; tool execution was not required.".to_string();
    }
    "Run a focused verification step and persist the validated takeaway.".to_string()
}

fn truncate(value: &str, max_chars: usize) -> String {
    if value.chars().count() <= max_chars {
        return value.to_string();
    }
    let mut out = String::new();
    for ch in value.chars().take(max_chars.saturating_sub(3)) {
        out.push(ch);
    }
    out.push_str("...");
    out
}

fn squash_whitespace(value: &str) -> String {
    value.split_whitespace().collect::<Vec<_>>().join(" ")
}

fn round2(value: f32) -> f32 {
    (value * 100.0).round() / 100.0
}
