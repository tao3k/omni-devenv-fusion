use std::sync::Arc;
use std::sync::{PoisonError, RwLock};

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::{Mutex, mpsc};

use crate::channels::traits::{Channel, ChannelMessage};

use super::{build_agent, build_job_manager, handle_inbound_message, inbound};

struct SwitchableMockChannel {
    sent: Mutex<Vec<(String, String)>>,
    mode: RwLock<String>,
}

impl SwitchableMockChannel {
    fn new(initial_mode: &str) -> Self {
        Self {
            sent: Mutex::new(Vec::new()),
            mode: RwLock::new(initial_mode.to_string()),
        }
    }

    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }

    fn current_mode(&self) -> String {
        self.mode
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .clone()
    }
}

#[async_trait]
impl Channel for SwitchableMockChannel {
    fn name(&self) -> &str {
        "switchable-mock"
    }

    fn session_partition_mode(&self) -> Option<String> {
        Some(self.current_mode())
    }

    fn set_session_partition_mode(&self, mode: &str) -> anyhow::Result<()> {
        *self.mode.write().unwrap_or_else(PoisonError::into_inner) = mode.to_string();
        Ok(())
    }

    fn is_admin_user(&self, identity: &str) -> bool {
        identity == "888"
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

struct CommandScopedMockChannel {
    sent: Mutex<Vec<(String, String)>>,
    mode: RwLock<String>,
}

impl CommandScopedMockChannel {
    fn new(initial_mode: &str) -> Self {
        Self {
            sent: Mutex::new(Vec::new()),
            mode: RwLock::new(initial_mode.to_string()),
        }
    }

    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for CommandScopedMockChannel {
    fn name(&self) -> &str {
        "command-scoped-mock"
    }

    fn session_partition_mode(&self) -> Option<String> {
        Some(
            self.mode
                .read()
                .unwrap_or_else(PoisonError::into_inner)
                .clone(),
        )
    }

    fn set_session_partition_mode(&self, mode: &str) -> anyhow::Result<()> {
        *self.mode.write().unwrap_or_else(PoisonError::into_inner) = mode.to_string();
        Ok(())
    }

    fn is_admin_user(&self, _identity: &str) -> bool {
        false
    }

    fn is_authorized_for_control_command(&self, identity: &str, command_text: &str) -> bool {
        identity == "777" && command_text.starts_with("/session partition")
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
async fn runtime_handle_inbound_session_partition_status_and_toggle() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SwitchableMockChannel::new("chat_user"));
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session partition"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/session partition on"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        handle_inbound_message(
            inbound("/session partition json"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );

    assert!(
        foreground_rx.try_recv().is_err(),
        "session partition commands should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 3);
    assert!(sent[0].0.contains("Session partition status."));
    assert!(sent[0].0.contains("current_mode=chat_user"));
    assert!(sent[1].0.contains("Session partition updated."));
    assert!(sent[1].0.contains("requested_mode=chat"));
    assert!(sent[1].0.contains("current_mode=chat"));
    let status_json: serde_json::Value = serde_json::from_str(&sent[2].0)?;
    assert_eq!(status_json["kind"], "session_partition");
    assert_eq!(status_json["updated"], false);
    assert_eq!(status_json["current_mode"], "chat");
    assert_eq!(
        status_json["supported_modes"],
        serde_json::json!(["chat", "chat_user", "user", "chat_thread_user"])
    );
    assert_eq!(status_json["quick_toggle"], "/session partition on|off");
    assert_eq!(channel.current_mode(), "chat");
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_partition_requires_admin() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SwitchableMockChannel::new("chat_user"));
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut non_admin = inbound("/session partition on");
    non_admin.sender = "999".to_string();
    assert!(
        handle_inbound_message(
            non_admin,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session partition command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Session Partition Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `admin_required`"));
    assert!(sent[0].0.contains("`sender`: `999`"));
    assert_eq!(channel.current_mode(), "chat_user");
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_partition_uses_command_scoped_authorization() -> Result<()>
{
    let agent = build_agent().await?;
    let channel = Arc::new(CommandScopedMockChannel::new("chat_user"));
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/session partition on");
    msg.sender = "777".to_string();
    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "session partition command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("Session partition updated."));
    Ok(())
}
