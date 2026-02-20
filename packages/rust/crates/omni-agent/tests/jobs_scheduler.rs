#![allow(missing_docs)]

use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use async_trait::async_trait;
use omni_agent::{
    JobManager, JobManagerConfig, RecurringScheduleConfig, TurnRunner, run_recurring_schedule,
};

struct MockRunner {
    delay: Duration,
    fail: bool,
}

impl MockRunner {
    fn success(delay: Duration) -> Self {
        Self { delay, fail: false }
    }

    fn failure(delay: Duration) -> Self {
        Self { delay, fail: true }
    }
}

#[async_trait]
impl TurnRunner for MockRunner {
    async fn run_turn(&self, _session_id: &str, user_message: &str) -> Result<String> {
        tokio::time::sleep(self.delay).await;
        if self.fail {
            anyhow::bail!("mock failure for prompt: {user_message}");
        }
        Ok(format!("ok: {user_message}"))
    }
}

#[tokio::test]
async fn recurring_scheduler_submits_and_collects_successes() {
    let runner: Arc<dyn TurnRunner> = Arc::new(MockRunner::success(Duration::from_millis(10)));
    let (manager, completion_rx) = JobManager::start(
        runner,
        JobManagerConfig {
            queue_capacity: 8,
            max_in_flight: 2,
            job_timeout_secs: 5,
            heartbeat_interval_secs: 60,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 120,
        },
    );

    let outcome = run_recurring_schedule(
        manager,
        completion_rx,
        RecurringScheduleConfig {
            schedule_id: "unit-success".to_string(),
            session_prefix: "scheduler".to_string(),
            recipient: "test-recipient".to_string(),
            prompt: "research rust scheduling".to_string(),
            interval_secs: 1,
            max_runs: Some(2),
            wait_for_completion_secs: 3,
        },
    )
    .await
    .expect("schedule should complete");

    assert_eq!(outcome.submitted, 2);
    assert_eq!(outcome.completed, 2);
    assert_eq!(outcome.succeeded, 2);
    assert_eq!(outcome.failed, 0);
    assert_eq!(outcome.timed_out, 0);
}

#[tokio::test]
async fn recurring_scheduler_tracks_failures() {
    let runner: Arc<dyn TurnRunner> = Arc::new(MockRunner::failure(Duration::from_millis(10)));
    let (manager, completion_rx) = JobManager::start(
        runner,
        JobManagerConfig {
            queue_capacity: 8,
            max_in_flight: 1,
            job_timeout_secs: 5,
            heartbeat_interval_secs: 60,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 120,
        },
    );

    let outcome = run_recurring_schedule(
        manager,
        completion_rx,
        RecurringScheduleConfig {
            schedule_id: "unit-failure".to_string(),
            session_prefix: "scheduler".to_string(),
            recipient: "test-recipient".to_string(),
            prompt: "research failure path".to_string(),
            interval_secs: 1,
            max_runs: Some(1),
            wait_for_completion_secs: 2,
        },
    )
    .await
    .expect("schedule should complete");

    assert_eq!(outcome.submitted, 1);
    assert_eq!(outcome.completed, 1);
    assert_eq!(outcome.succeeded, 0);
    assert_eq!(outcome.failed, 1);
    assert_eq!(outcome.timed_out, 0);
}

#[tokio::test]
async fn recurring_scheduler_rejects_empty_prompt() {
    let runner: Arc<dyn TurnRunner> = Arc::new(MockRunner::success(Duration::from_millis(1)));
    let (manager, completion_rx) = JobManager::start(
        runner,
        JobManagerConfig {
            queue_capacity: 4,
            max_in_flight: 1,
            job_timeout_secs: 5,
            heartbeat_interval_secs: 60,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 120,
        },
    );

    let error = run_recurring_schedule(
        manager,
        completion_rx,
        RecurringScheduleConfig {
            prompt: "   ".to_string(),
            interval_secs: 1,
            max_runs: Some(1),
            ..RecurringScheduleConfig::default()
        },
    )
    .await
    .expect_err("empty prompt should be rejected");

    assert!(
        error
            .to_string()
            .contains("schedule prompt cannot be empty")
    );
}
