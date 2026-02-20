use std::sync::Arc;

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::Mutex;
use tokio::sync::mpsc;

use crate::agent::{SessionMemoryRecallDecision, SessionMemoryRecallSnapshot};
use crate::channels::traits::{Channel, ChannelMessage};

use super::{MockChannel, build_agent, build_job_manager, handle_inbound_message, inbound};

#[derive(Default)]
struct TelegramNamedMockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl TelegramNamedMockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for TelegramNamedMockChannel {
    fn name(&self) -> &str {
        "telegram"
    }

    fn is_admin_user(&self, _identity: &str) -> bool {
        true
    }

    async fn send(&self, message: &str, recipient: &str) -> Result<()> {
        self.sent
            .lock()
            .await
            .push((message.to_string(), recipient.to_string()));
        Ok(())
    }

    async fn listen(&self, _tx: mpsc::Sender<ChannelMessage>) -> Result<()> {
        Ok(())
    }
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_without_snapshot() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session memory"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session memory command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("No memory recall snapshot found for this session yet.")
    );
    assert!(sent[0].0.contains("### Persistence"));
    assert!(sent[0].0.contains("`startup_load_status=not_configured`"));
    assert!(sent[0].0.contains("`backend_ready=no`"));
    assert!(sent[0].0.contains("`gate_promote_threshold=-`"));
    assert!(sent[0].0.contains("`gate_obsolete_threshold=-`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_without_snapshot_reports_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session memory json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session memory json command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_memory");
    assert_eq!(payload["available"], false);
    assert_eq!(payload["status"], "not_found");
    assert!(payload["runtime"].is_object());
    assert_eq!(payload["runtime"]["memory_enabled"], false);
    assert_eq!(payload["runtime"]["startup_load_status"], "not_configured");
    assert_eq!(payload["runtime"]["backend_ready"], false);
    assert!(payload["runtime"]["gate_promote_threshold"].is_null());
    assert!(payload["runtime"]["gate_obsolete_threshold"].is_null());
    assert!(payload["metrics"].is_object());
    assert_eq!(payload["metrics"]["planned_total"], 0);
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_reports_latest_snapshot() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .record_memory_recall_snapshot(
            session_id,
            SessionMemoryRecallSnapshot {
                created_at_unix_ms: 1_739_900_000_123,
                query_tokens: 14,
                recall_feedback_bias: -0.21,
                embedding_source: "embedding",
                k1: 12,
                k2: 4,
                lambda: 0.35,
                min_score: 0.08,
                max_context_chars: 1_280,
                budget_pressure: 0.62,
                window_pressure: 0.41,
                effective_budget_tokens: Some(5_488),
                active_turns_estimate: 18,
                summary_segment_count: 2,
                recalled_total: 9,
                recalled_selected: 4,
                recalled_injected: 3,
                context_chars_injected: 512,
                best_score: Some(0.71),
                weakest_score: Some(0.22),
                pipeline_duration_ms: 18,
                decision: SessionMemoryRecallDecision::Injected,
            },
        )
        .await;

    assert!(
        handle_inbound_message(
            inbound("/session memory"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session memory command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Session Memory"));
    assert!(sent[0].0.contains("- Decision: `injected`"));
    assert!(sent[0].0.contains("- Query tokens: `14`"));
    assert!(sent[0].0.contains("- Recall feedback bias: `-0.210`"));
    assert!(sent[0].0.contains("- Embedding source: `embedding`"));
    assert!(sent[0].0.contains("- Pipeline duration: `18 ms`"));
    assert!(sent[0].0.contains("- `k1=12` / `k2=4`"));
    assert!(sent[0].0.contains("- `context_chars_injected=512`"));
    assert!(sent[0].0.contains("- `recalled_injected=3`"));
    assert!(sent[0].0.contains("### Persistence"));
    assert!(sent[0].0.contains("`memory_enabled=no`"));
    assert!(sent[0].0.contains("`gate_promote_threshold=-`"));
    assert!(sent[0].0.contains("### Process Metrics"));
    assert!(sent[0].0.contains("- `planned_total=0`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_reports_latest_snapshot_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .record_memory_recall_snapshot(
            session_id,
            SessionMemoryRecallSnapshot {
                created_at_unix_ms: 1_739_900_000_456,
                query_tokens: 9,
                recall_feedback_bias: 0.34,
                embedding_source: "hash",
                k1: 8,
                k2: 2,
                lambda: 0.45,
                min_score: 0.15,
                max_context_chars: 640,
                budget_pressure: 1.12,
                window_pressure: 0.30,
                effective_budget_tokens: Some(3_600),
                active_turns_estimate: 24,
                summary_segment_count: 0,
                recalled_total: 6,
                recalled_selected: 2,
                recalled_injected: 0,
                context_chars_injected: 0,
                best_score: Some(0.52),
                weakest_score: Some(0.17),
                pipeline_duration_ms: 9,
                decision: SessionMemoryRecallDecision::Skipped,
            },
        )
        .await;

    assert!(
        handle_inbound_message(
            inbound("/session recall json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session recall json command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    let payload: serde_json::Value = serde_json::from_str(&sent[0].0)?;
    assert_eq!(payload["kind"], "session_memory");
    assert_eq!(payload["available"], true);
    assert_eq!(payload["decision"], "skipped");
    assert_eq!(payload["query_tokens"], 9);
    let recall_feedback_bias = payload["recall_feedback_bias"]
        .as_f64()
        .expect("recall_feedback_bias should be a number");
    assert!((recall_feedback_bias - 0.34).abs() < 1e-6);
    assert_eq!(payload["embedding_source"], "hash");
    assert_eq!(payload["pipeline_duration_ms"], 9);
    assert_eq!(payload["plan"]["k1"], 8);
    assert_eq!(payload["plan"]["k2"], 2);
    assert_eq!(payload["result"]["context_chars_injected"], 0);
    assert_eq!(payload["result"]["recalled_selected"], 2);
    assert!(payload["runtime"].is_object());
    assert_eq!(payload["runtime"]["memory_enabled"], false);
    assert_eq!(payload["runtime"]["startup_load_status"], "not_configured");
    assert_eq!(payload["runtime"]["backend_ready"], false);
    assert!(payload["runtime"]["gate_promote_min_usage"].is_null());
    assert!(payload["runtime"]["gate_obsolete_min_usage"].is_null());
    assert!(payload["metrics"].is_object());
    assert_eq!(payload["metrics"]["planned_total"], 0);
    assert_eq!(payload["metrics"]["completed_total"], 0);
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_telegram_uses_compact_not_found_view() -> Result<()>
{
    let agent = build_agent().await?;
    let channel = Arc::new(TelegramNamedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session memory"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Session Memory"));
    assert!(sent[0].0.contains("### Persistence"));
    assert!(
        sent[0].0.contains(
            "- `memory_enabled=no` `backend_ready=no` `startup_load_status=not_configured`"
        )
    );
    assert!(sent[0].0.contains("`promote(threshold=-,min_usage=-"));
    assert!(
        sent[0]
            .0
            .contains("Use `/session memory json` for full payload.")
    );
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_telegram_uses_compact_snapshot_view() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(TelegramNamedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);
    let session_id = "telegram:-200:888";

    agent
        .record_memory_recall_snapshot(
            session_id,
            SessionMemoryRecallSnapshot {
                created_at_unix_ms: 1_739_900_000_123,
                query_tokens: 14,
                recall_feedback_bias: -0.21,
                embedding_source: "embedding",
                k1: 12,
                k2: 4,
                lambda: 0.35,
                min_score: 0.08,
                max_context_chars: 1_280,
                budget_pressure: 0.62,
                window_pressure: 0.41,
                effective_budget_tokens: Some(5_488),
                active_turns_estimate: 18,
                summary_segment_count: 2,
                recalled_total: 9,
                recalled_selected: 4,
                recalled_injected: 3,
                context_chars_injected: 512,
                best_score: Some(0.71),
                weakest_score: Some(0.22),
                pipeline_duration_ms: 18,
                decision: SessionMemoryRecallDecision::Injected,
            },
        )
        .await;

    assert!(
        handle_inbound_message(
            inbound("/session memory"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("### Trigger - Decision"));
    assert!(
        sent[0]
            .0
            .contains("- `decision=injected` `query_tokens=14` `pipeline_ms=18`")
    );
    assert!(sent[0].0.contains("### Recall Result"));
    assert!(
        sent[0]
            .0
            .contains("- `injected=3` / `selected=4` / `total=9`")
    );
    assert!(sent[0].0.contains("### Adaptive Metrics"));
    assert!(sent[0].0.contains("`promote(threshold=-,min_usage=-"));
    assert!(
        sent[0]
            .0
            .contains("Tip: run `/session memory json` for full payload.")
    );
    assert!(!sent[0].0.contains("### Recall Plan"));
    Ok(())
}
