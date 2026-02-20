use std::sync::Arc;
use std::time::Duration;

use anyhow::{Result, bail};
use tokio::sync::mpsc;
use tokio::time::{Instant, MissedTickBehavior};

use crate::jobs::{JobCompletion, JobManager};

use super::helpers::{apply_completion, completion_label, normalize_or_default};
use super::types::{RecurringScheduleConfig, RecurringScheduleOutcome};

/// Run a recurring scheduler loop using an existing `JobManager`.
///
/// The loop submits one job per tick, collects completion events, and stops when:
/// - `max_runs` submissions are reached, or
/// - Ctrl+C is received.
pub async fn run_recurring_schedule(
    manager: Arc<JobManager>,
    mut completion_rx: mpsc::Receiver<JobCompletion>,
    mut config: RecurringScheduleConfig,
) -> Result<RecurringScheduleOutcome> {
    let prompt = config.prompt.trim().to_string();
    if prompt.is_empty() {
        bail!("schedule prompt cannot be empty");
    }
    if let Some(max_runs) = config.max_runs
        && max_runs == 0
    {
        bail!("max_runs must be greater than zero when provided");
    }

    config.interval_secs = config.interval_secs.max(1);
    config.wait_for_completion_secs = config.wait_for_completion_secs.max(1);
    config.schedule_id = normalize_or_default(&config.schedule_id, "default");
    config.session_prefix = normalize_or_default(&config.session_prefix, "scheduler");
    config.recipient = normalize_or_default(&config.recipient, "scheduler");

    let effective_session_prefix =
        format!("{}:schedule:{}", config.session_prefix, config.schedule_id);
    let mut ticker = tokio::time::interval(Duration::from_secs(config.interval_secs));
    ticker.set_missed_tick_behavior(MissedTickBehavior::Skip);

    let mut outcome = RecurringScheduleOutcome::default();
    let mut interrupted = false;

    loop {
        let reached_limit = config
            .max_runs
            .is_some_and(|max_runs| outcome.submitted >= max_runs);
        if reached_limit || interrupted {
            break;
        }

        tokio::select! {
            _ = ticker.tick() => {
                let job_id = manager
                    .submit(
                        &effective_session_prefix,
                        config.recipient.clone(),
                        prompt.clone(),
                    )
                    .await?;
                outcome.submitted += 1;
                tracing::info!(
                    schedule_id = %config.schedule_id,
                    run = outcome.submitted,
                    interval_secs = config.interval_secs,
                    %job_id,
                    "scheduled background job queued"
                );
            }
            maybe_completion = completion_rx.recv() => {
                let Some(completion) = maybe_completion else {
                    break;
                };
                apply_completion(&mut outcome, &completion);
                tracing::info!(
                    schedule_id = %config.schedule_id,
                    job_id = %completion.job_id,
                    state = %completion_label(&completion.kind),
                    completed = outcome.completed,
                    submitted = outcome.submitted,
                    "scheduled background job completed"
                );
            }
            _ = tokio::signal::ctrl_c() => {
                interrupted = true;
                tracing::info!(
                    schedule_id = %config.schedule_id,
                    submitted = outcome.submitted,
                    "scheduler received Ctrl+C; stopping submissions"
                );
            }
        }
    }

    drain_in_flight_completions(&mut outcome, &mut completion_rx, &config).await;

    if outcome.completed < outcome.submitted {
        tracing::warn!(
            schedule_id = %config.schedule_id,
            submitted = outcome.submitted,
            completed = outcome.completed,
            wait_for_completion_secs = config.wait_for_completion_secs,
            "scheduler exited before all queued jobs completed"
        );
    }

    Ok(outcome)
}

async fn drain_in_flight_completions(
    outcome: &mut RecurringScheduleOutcome,
    completion_rx: &mut mpsc::Receiver<JobCompletion>,
    config: &RecurringScheduleConfig,
) {
    if outcome.completed >= outcome.submitted {
        return;
    }

    let deadline = Instant::now() + Duration::from_secs(config.wait_for_completion_secs);
    while outcome.completed < outcome.submitted {
        let now = Instant::now();
        if now >= deadline {
            break;
        }
        let wait = deadline - now;
        match tokio::time::timeout(wait, completion_rx.recv()).await {
            Ok(Some(completion)) => {
                apply_completion(outcome, &completion);
                tracing::info!(
                    schedule_id = %config.schedule_id,
                    job_id = %completion.job_id,
                    state = %completion_label(&completion.kind),
                    completed = outcome.completed,
                    submitted = outcome.submitted,
                    "scheduled completion observed during drain"
                );
            }
            Ok(None) | Err(_) => break,
        }
    }
}
