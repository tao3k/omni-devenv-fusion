#![allow(missing_docs)]

use std::sync::Arc;
use std::time::Duration;

use anyhow::Result;
use async_trait::async_trait;
use omni_agent::{
    HeartbeatProbeState, JobCompletionKind, JobHealthState, JobManager, JobManagerConfig,
    JobMetricsSnapshot, JobState, TurnRunner, classify_heartbeat_probe_result, classify_job_health,
};

struct MockRunner {
    delay: Duration,
    output: Option<String>,
    error: Option<String>,
}

impl MockRunner {
    fn success(delay: Duration, output: &str) -> Self {
        Self {
            delay,
            output: Some(output.to_string()),
            error: None,
        }
    }

    fn failure(delay: Duration, error: &str) -> Self {
        Self {
            delay,
            output: None,
            error: Some(error.to_string()),
        }
    }
}

#[async_trait]
impl TurnRunner for MockRunner {
    async fn run_turn(&self, _session_id: &str, _user_message: &str) -> Result<String> {
        tokio::time::sleep(self.delay).await;
        if let Some(ref output) = self.output {
            return Ok(output.clone());
        }
        Err(anyhow::anyhow!(
            self.error
                .clone()
                .unwrap_or_else(|| "unknown mock error".to_string())
        ))
    }
}

#[tokio::test]
async fn background_job_succeeds_and_updates_status() {
    let runner: Arc<dyn TurnRunner> =
        Arc::new(MockRunner::success(Duration::from_millis(20), "done"));
    let (manager, mut completion_rx) = JobManager::start(
        runner,
        JobManagerConfig {
            queue_capacity: 8,
            max_in_flight: 2,
            job_timeout_secs: 10,
            heartbeat_interval_secs: 60,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 120,
        },
    );

    let job_id = manager
        .submit(
            "telegram:alice",
            "alice".to_string(),
            "research rust".to_string(),
        )
        .await
        .expect("submit should succeed");

    let completion = tokio::time::timeout(Duration::from_secs(2), completion_rx.recv())
        .await
        .expect("completion wait should not time out")
        .expect("completion should exist");

    assert_eq!(completion.job_id, job_id);
    match completion.kind {
        JobCompletionKind::Succeeded { output } => assert_eq!(output, "done"),
        _ => panic!("expected success completion"),
    }

    let status = manager
        .get_status(&job_id)
        .await
        .expect("job status should exist");
    assert_eq!(status.state, JobState::Succeeded);
    assert!(status.output_preview.is_some());

    let metrics = manager.metrics().await;
    assert_eq!(metrics.succeeded, 1);
    assert_eq!(metrics.failed, 0);
    assert_eq!(metrics.timed_out, 0);
}

#[tokio::test]
async fn background_job_timeout_marks_timed_out() {
    let runner: Arc<dyn TurnRunner> =
        Arc::new(MockRunner::success(Duration::from_millis(1_200), "late"));
    let (manager, mut completion_rx) = JobManager::start(
        runner,
        JobManagerConfig {
            queue_capacity: 8,
            max_in_flight: 1,
            job_timeout_secs: 1,
            heartbeat_interval_secs: 60,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 120,
        },
    );

    let job_id = manager
        .submit(
            "telegram:bob",
            "bob".to_string(),
            "research this should timeout".to_string(),
        )
        .await
        .expect("submit should succeed");

    let completion = tokio::time::timeout(Duration::from_secs(2), completion_rx.recv())
        .await
        .expect("completion wait should not time out")
        .expect("completion should exist");

    assert_eq!(completion.job_id, job_id);
    match completion.kind {
        JobCompletionKind::TimedOut { timeout_secs } => assert_eq!(timeout_secs, 1),
        _ => panic!("expected timeout completion"),
    }

    let status = manager
        .get_status(&job_id)
        .await
        .expect("job status should exist");
    assert_eq!(status.state, JobState::TimedOut);
}

#[tokio::test]
async fn background_job_failure_marks_failed() {
    let runner: Arc<dyn TurnRunner> = Arc::new(MockRunner::failure(
        Duration::from_millis(10),
        "tool failed",
    ));
    let (manager, mut completion_rx) = JobManager::start(
        runner,
        JobManagerConfig {
            queue_capacity: 8,
            max_in_flight: 1,
            job_timeout_secs: 10,
            heartbeat_interval_secs: 60,
            heartbeat_probe_timeout_secs: 2,
            max_queued_age_secs: 120,
            max_running_age_secs: 120,
        },
    );

    let job_id = manager
        .submit(
            "telegram:carol",
            "carol".to_string(),
            "research expected failure".to_string(),
        )
        .await
        .expect("submit should succeed");

    let completion = tokio::time::timeout(Duration::from_secs(2), completion_rx.recv())
        .await
        .expect("completion wait should not time out")
        .expect("completion should exist");

    assert_eq!(completion.job_id, job_id);
    match completion.kind {
        JobCompletionKind::Failed { error } => assert!(error.contains("tool failed")),
        _ => panic!("expected failed completion"),
    }

    let status = manager
        .get_status(&job_id)
        .await
        .expect("job status should exist");
    assert_eq!(status.state, JobState::Failed);
}

#[tokio::test]
async fn classify_heartbeat_probe_timeout() {
    let probe = tokio::time::timeout(Duration::from_millis(1), async {
        tokio::time::sleep(Duration::from_millis(20)).await;
    })
    .await;
    let state = classify_heartbeat_probe_result(&probe);
    assert_eq!(state, HeartbeatProbeState::Timeout);
}

#[test]
fn classify_job_health_detects_stalled_states() {
    let healthy = JobMetricsSnapshot {
        total_jobs: 2,
        queued: 1,
        running: 1,
        succeeded: 0,
        failed: 0,
        timed_out: 0,
        oldest_queued_age_secs: Some(5),
        longest_running_age_secs: Some(8),
        health_state: JobHealthState::Healthy,
    };
    assert_eq!(
        classify_job_health(&healthy, 10, 10),
        JobHealthState::Healthy
    );

    let queued_stalled = JobMetricsSnapshot {
        total_jobs: 1,
        queued: 1,
        running: 0,
        succeeded: 0,
        failed: 0,
        timed_out: 0,
        oldest_queued_age_secs: Some(30),
        longest_running_age_secs: None,
        health_state: JobHealthState::Healthy,
    };
    assert_eq!(
        classify_job_health(&queued_stalled, 10, 10),
        JobHealthState::QueueStalled
    );

    let running_stalled = JobMetricsSnapshot {
        total_jobs: 1,
        queued: 0,
        running: 1,
        succeeded: 0,
        failed: 0,
        timed_out: 0,
        oldest_queued_age_secs: None,
        longest_running_age_secs: Some(42),
        health_state: JobHealthState::Healthy,
    };
    assert_eq!(
        classify_job_health(&running_stalled, 10, 10),
        JobHealthState::RunningStalled
    );
}
