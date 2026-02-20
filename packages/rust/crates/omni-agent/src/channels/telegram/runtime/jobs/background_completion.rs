use std::sync::Arc;

use crate::channels::traits::Channel;
use crate::jobs::{JobCompletion, JobCompletionKind};

use super::observability::send_with_observability;

const EVENT_TELEGRAM_COMMAND_BACKGROUND_COMPLETION_SUCCEEDED_REPLIED: &str =
    "telegram.command.background_completion_succeeded.replied";
const EVENT_TELEGRAM_COMMAND_BACKGROUND_COMPLETION_FAILED_REPLIED: &str =
    "telegram.command.background_completion_failed.replied";
const EVENT_TELEGRAM_COMMAND_BACKGROUND_COMPLETION_TIMED_OUT_REPLIED: &str =
    "telegram.command.background_completion_timed_out.replied";

pub(super) async fn push_background_completion(
    channel: &Arc<dyn Channel>,
    completion: JobCompletion,
) {
    let (event_name, message) = match completion.kind {
        JobCompletionKind::Succeeded { output } => (
            EVENT_TELEGRAM_COMMAND_BACKGROUND_COMPLETION_SUCCEEDED_REPLIED,
            format!(
                "Background job `{}` completed.\n\n{}",
                completion.job_id, output
            ),
        ),
        JobCompletionKind::Failed { error } => (
            EVENT_TELEGRAM_COMMAND_BACKGROUND_COMPLETION_FAILED_REPLIED,
            format!("Background job `{}` failed: {}", completion.job_id, error),
        ),
        JobCompletionKind::TimedOut { timeout_secs } => (
            EVENT_TELEGRAM_COMMAND_BACKGROUND_COMPLETION_TIMED_OUT_REPLIED,
            format!(
                "Background job `{}` timed out after {}s.",
                completion.job_id, timeout_secs
            ),
        ),
    };
    send_with_observability(
        channel,
        &message,
        &completion.recipient,
        "Failed to send background completion",
        Some(event_name),
        None,
    )
    .await;
}
