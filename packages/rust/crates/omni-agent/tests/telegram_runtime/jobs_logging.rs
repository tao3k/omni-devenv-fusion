use std::io;
use std::sync::{Arc, Mutex};

use anyhow::Result;
use tokio::sync::mpsc;
use tracing_subscriber::fmt::writer::MakeWriter;

use super::super::jobs::log_preview;
use super::{MockChannel, build_agent, build_job_manager, handle_inbound_message, inbound};
use crate::channels::traits::{Channel, ChannelMessage};

#[derive(Clone, Default)]
struct SharedLogBuffer {
    inner: Arc<Mutex<Vec<u8>>>,
}

impl SharedLogBuffer {
    fn as_string(&self) -> String {
        match self.inner.lock() {
            Ok(guard) => String::from_utf8_lossy(&guard).to_string(),
            Err(_) => String::new(),
        }
    }
}

struct SharedLogWriter {
    inner: Arc<Mutex<Vec<u8>>>,
}

impl<'a> MakeWriter<'a> for SharedLogBuffer {
    type Writer = SharedLogWriter;

    fn make_writer(&'a self) -> Self::Writer {
        SharedLogWriter {
            inner: Arc::clone(&self.inner),
        }
    }
}

impl io::Write for SharedLogWriter {
    fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
        if let Ok(mut guard) = self.inner.lock() {
            guard.extend_from_slice(buf);
            Ok(buf.len())
        } else {
            Err(io::Error::other("failed to lock shared log buffer"))
        }
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

#[test]
fn runtime_jobs_log_preview_flattens_newlines_and_truncates() {
    let input = format!("line1\n{}", "x".repeat(120));
    let preview = log_preview(&input);
    assert!(!preview.contains('\n'));
    assert!(preview.starts_with("line1 "));
    assert!(preview.ends_with("..."));
}

#[test]
fn runtime_jobs_log_preview_keeps_short_messages() {
    let preview = log_preview("short status");
    assert_eq!(preview, "short status");
}

#[tokio::test(flavor = "current_thread")]
async fn runtime_jobs_logs_structured_command_reply_event() -> Result<()> {
    let logs = SharedLogBuffer::default();
    let subscriber = tracing_subscriber::fmt()
        .with_ansi(false)
        .without_time()
        .with_writer(logs.clone())
        .finish();
    let _guard = tracing::subscriber::set_default(subscriber);

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let output = logs.as_string();
    assert!(output.contains("telegram command reply sent"));
    assert!(output.contains("telegram command reply json summary"));
    assert!(output.contains("telegram.command.session_status_json.replied"));
    assert!(output.contains("json_kind"));
    assert!(output.contains("session_context"));
    assert!(output.contains("json_logical_session_id"));
    assert!(output.contains("json_partition_key"));
    assert!(output.contains("json_keys="));
    assert!(output.contains("session_key"));
    assert!(output.contains("-200:888"));
    Ok(())
}

#[tokio::test(flavor = "current_thread")]
async fn runtime_jobs_logs_structured_memory_json_summary_fields() -> Result<()> {
    let logs = SharedLogBuffer::default();
    let subscriber = tracing_subscriber::fmt()
        .with_ansi(false)
        .without_time()
        .with_writer(logs.clone())
        .finish();
    let _guard = tracing::subscriber::set_default(subscriber);

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let message = ChannelMessage {
        id: "jobs-logging-memory-json".to_string(),
        sender: "888".to_string(),
        recipient: "-200".to_string(),
        session_key: "-200:888:jobs-logging-memory-json".to_string(),
        content: "/session memory json".to_string(),
        channel: "telegram".to_string(),
        timestamp: 0,
    };
    assert!(
        handle_inbound_message(message, &channel_dyn, &foreground_tx, &job_manager, &agent).await
    );
    assert!(foreground_rx.try_recv().is_err());

    let output = logs.as_string();
    assert!(output.contains("telegram command reply json summary"));
    assert!(output.contains("telegram.command.session_memory_json.replied"));
    assert!(output.contains("json_kind"));
    assert!(output.contains("session_memory"));
    assert!(output.contains("json_available=false") || output.contains("json_available=\"false\""));
    assert!(
        output.contains("json_status=not_found") || output.contains("json_status=\"not_found\"")
    );
    assert!(output.contains("json_runtime_backend_ready"));
    assert!(output.contains("json_runtime_startup_load_status"));
    Ok(())
}

#[tokio::test(flavor = "current_thread")]
async fn runtime_jobs_logs_structured_session_admin_json_summary_fields() -> Result<()> {
    let logs = SharedLogBuffer::default();
    let subscriber = tracing_subscriber::fmt()
        .with_ansi(false)
        .without_time()
        .with_writer(logs.clone())
        .finish();
    let _guard = tracing::subscriber::set_default(subscriber);

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session admin list json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let output = logs.as_string();
    assert!(output.contains("telegram command reply json summary"));
    assert!(output.contains("telegram.command.session_admin_json.replied"));
    assert!(output.contains("session_admin"));
    assert!(output.contains("json_override_admin_count"));
    Ok(())
}

#[tokio::test(flavor = "current_thread")]
async fn runtime_jobs_logs_structured_reset_snapshot_state_event() -> Result<()> {
    let logs = SharedLogBuffer::default();
    let subscriber = tracing_subscriber::fmt()
        .with_ansi(false)
        .without_time()
        .with_writer(logs.clone())
        .finish();
    let _guard = tracing::subscriber::set_default(subscriber);

    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/reset"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(foreground_rx.try_recv().is_err());

    let output = logs.as_string();
    assert!(output.contains("telegram command reset snapshot state"));
    assert!(output.contains("telegram.command.session_reset.snapshot_state"));
    assert!(output.contains("snapshot_state=none") || output.contains("snapshot_state=\"none\""));
    assert!(output.contains("session_key"));
    assert!(output.contains("-200:888"));
    Ok(())
}
