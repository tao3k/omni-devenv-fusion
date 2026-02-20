use super::memory_recall::MemoryRecallPlan;

const FAILURE_KEYWORDS: [&str; 10] = [
    "error",
    "failed",
    "failure",
    "exception",
    "traceback",
    "timeout",
    "timed out",
    "panic",
    "unavailable",
    "invalid",
];

const FEEDBACK_SUCCESS_KEYWORDS: [&str; 8] =
    ["success", "succeeded", "good", "ok", "pass", "up", "+", "1"];
const FEEDBACK_FAILURE_KEYWORDS: [&str; 8] =
    ["failure", "failed", "bad", "error", "down", "-", "0", "no"];

pub(super) const RECALL_FEEDBACK_SOURCE_USER: &str = "user_feedback";
pub(super) const RECALL_FEEDBACK_SOURCE_TOOL: &str = "tool_execution";
pub(super) const RECALL_FEEDBACK_SOURCE_ASSISTANT: &str = "assistant_heuristic";
pub(super) const RECALL_FEEDBACK_SOURCE_COMMAND: &str = "session_feedback_command";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(super) enum RecallOutcome {
    Success,
    Failure,
}

impl RecallOutcome {
    pub(super) fn as_memory_label(self) -> &'static str {
        match self {
            Self::Success => "completed",
            Self::Failure => "error",
        }
    }

    pub(super) fn as_feedback_delta(self) -> f32 {
        match self {
            Self::Success => 1.0,
            Self::Failure => -1.0,
        }
    }

    pub(super) fn as_str(self) -> &'static str {
        match self {
            Self::Success => "success",
            Self::Failure => "failure",
        }
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub(super) struct ToolExecutionSummary {
    pub(super) attempted: u32,
    pub(super) succeeded: u32,
    pub(super) failed: u32,
}

impl ToolExecutionSummary {
    pub(super) fn record_result(&mut self, is_error: bool) {
        self.attempted = self.attempted.saturating_add(1);
        if is_error {
            self.failed = self.failed.saturating_add(1);
        } else {
            self.succeeded = self.succeeded.saturating_add(1);
        }
    }

    pub(super) fn record_transport_failure(&mut self) {
        self.attempted = self.attempted.saturating_add(1);
        self.failed = self.failed.saturating_add(1);
    }

    pub(super) fn inferred_outcome(self) -> Option<RecallOutcome> {
        if self.attempted == 0 {
            return None;
        }
        if self.failed > 0 && self.succeeded == 0 {
            return Some(RecallOutcome::Failure);
        }
        if self.succeeded > 0 && self.failed == 0 {
            return Some(RecallOutcome::Success);
        }
        None
    }
}

pub(super) fn classify_assistant_outcome(message: &str) -> RecallOutcome {
    let lower = message.to_lowercase();
    if FAILURE_KEYWORDS
        .iter()
        .any(|keyword| lower.contains(keyword))
    {
        RecallOutcome::Failure
    } else {
        RecallOutcome::Success
    }
}

pub(super) fn parse_explicit_user_feedback(message: &str) -> Option<RecallOutcome> {
    let normalized = message.trim().to_ascii_lowercase();
    if normalized.is_empty() {
        return None;
    }

    if let Some(rest) = normalized.strip_prefix("/feedback") {
        return parse_feedback_suffix(rest);
    }
    if let Some(rest) = normalized.strip_prefix("feedback:") {
        return parse_feedback_suffix(rest);
    }
    if normalized.starts_with("[feedback:") && normalized.ends_with(']') {
        let body = &normalized["[feedback:".len()..normalized.len().saturating_sub(1)];
        return parse_feedback_suffix(body);
    }
    None
}

pub(super) fn resolve_feedback_outcome(
    user_message: &str,
    tool_summary: Option<&ToolExecutionSummary>,
    assistant_message: &str,
) -> (RecallOutcome, &'static str) {
    if let Some(outcome) = parse_explicit_user_feedback(user_message) {
        return (outcome, RECALL_FEEDBACK_SOURCE_USER);
    }
    if let Some(outcome) = tool_summary.and_then(|summary| summary.inferred_outcome()) {
        return (outcome, RECALL_FEEDBACK_SOURCE_TOOL);
    }
    (
        classify_assistant_outcome(assistant_message),
        RECALL_FEEDBACK_SOURCE_ASSISTANT,
    )
}

pub(super) fn update_feedback_bias(previous: f32, outcome: RecallOutcome) -> f32 {
    let previous = previous.clamp(-1.0, 1.0);
    let delta = outcome.as_feedback_delta();
    ((previous * 0.85) + (delta * 0.15)).clamp(-1.0, 1.0)
}

pub(super) fn apply_feedback_to_plan(
    mut plan: MemoryRecallPlan,
    feedback_bias: f32,
) -> MemoryRecallPlan {
    let feedback_bias = feedback_bias.clamp(-1.0, 1.0);
    if feedback_bias <= -0.25 {
        let strength = (-feedback_bias).min(1.0);
        let extra_k2 = if strength >= 0.7 { 2 } else { 1 };
        let extra_k1 = extra_k2 * 3;
        plan.k2 = plan.k2.saturating_add(extra_k2);
        plan.k1 = plan.k1.saturating_add(extra_k1).max(plan.k2);
        plan.lambda = (plan.lambda - (0.06 * strength)).clamp(0.0, 1.0);
        plan.min_score = (plan.min_score - (0.05 * strength)).clamp(0.01, 1.0);
        plan.max_context_chars = plan
            .max_context_chars
            .saturating_add((240.0 * strength) as usize)
            .clamp(320, 2_400);
    } else if feedback_bias >= 0.35 {
        let strength = feedback_bias.min(1.0);
        let reduce_k2 = if strength >= 0.7 { 2 } else { 1 };
        let reduce_k1 = reduce_k2 * 2;
        plan.k2 = plan.k2.saturating_sub(reduce_k2).max(1);
        plan.k1 = plan.k1.saturating_sub(reduce_k1).max(plan.k2);
        plan.lambda = (plan.lambda + (0.05 * strength)).clamp(0.0, 1.0);
        plan.min_score = (plan.min_score + (0.04 * strength)).clamp(0.01, 0.35);
        plan.max_context_chars = plan
            .max_context_chars
            .saturating_sub((160.0 * strength) as usize)
            .clamp(320, 2_400);
    }

    plan.k1 = plan.k1.max(1);
    plan.k2 = plan.k2.max(1).min(plan.k1);
    plan
}

fn parse_feedback_suffix(raw: &str) -> Option<RecallOutcome> {
    let token = raw
        .trim()
        .trim_start_matches([':', '='])
        .split_whitespace()
        .next()
        .unwrap_or_default()
        .trim_matches(|c: char| c == '"' || c == '\'' || c == ',' || c == ';');
    parse_feedback_token(token)
}

fn parse_feedback_token(token: &str) -> Option<RecallOutcome> {
    if token.is_empty() {
        return None;
    }
    if FEEDBACK_SUCCESS_KEYWORDS.contains(&token) {
        return Some(RecallOutcome::Success);
    }
    if FEEDBACK_FAILURE_KEYWORDS.contains(&token) {
        return Some(RecallOutcome::Failure);
    }
    None
}

#[cfg(test)]
#[path = "../../tests/agent/memory_recall_feedback.rs"]
mod tests;
