use crate::jobs::{JobCompletion, JobCompletionKind};

use super::types::RecurringScheduleOutcome;

pub(super) fn normalize_or_default(value: &str, fallback: &str) -> String {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        fallback.to_string()
    } else {
        trimmed.to_string()
    }
}

pub(super) fn apply_completion(outcome: &mut RecurringScheduleOutcome, completion: &JobCompletion) {
    outcome.completed += 1;
    match completion.kind {
        JobCompletionKind::Succeeded { .. } => {
            outcome.succeeded += 1;
        }
        JobCompletionKind::Failed { .. } => {
            outcome.failed += 1;
        }
        JobCompletionKind::TimedOut { .. } => {
            outcome.timed_out += 1;
        }
    }
}

pub(super) fn completion_label(kind: &JobCompletionKind) -> &'static str {
    match kind {
        JobCompletionKind::Succeeded { .. } => "succeeded",
        JobCompletionKind::Failed { .. } => "failed",
        JobCompletionKind::TimedOut { .. } => "timed_out",
    }
}
