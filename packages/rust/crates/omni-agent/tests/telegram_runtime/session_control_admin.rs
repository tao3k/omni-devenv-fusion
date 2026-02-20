use std::sync::Arc;

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::{Mutex, mpsc};

use crate::channels::traits::{Channel, ChannelMessage};

use super::{build_agent, build_job_manager, handle_inbound_message, inbound};

#[derive(Default)]
struct AdminRestrictedMockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl AdminRestrictedMockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for AdminRestrictedMockChannel {
    fn name(&self) -> &str {
        "admin-restricted-mock"
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

#[tokio::test]
async fn runtime_handle_inbound_reset_requires_admin() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(AdminRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/reset");
    msg.sender = "999".to_string();
    msg.session_key = "-200:999".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "reset command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Control Command Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `admin_required`"));
    assert!(sent[0].0.contains("`command`: `/reset`"));
    assert!(sent[0].0.contains("`sender`: `999`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_resume_drop_requires_admin() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(AdminRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/resume drop");
    msg.sender = "999".to_string();
    msg.session_key = "-200:999".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "resume drop command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Control Command Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `admin_required`"));
    assert!(sent[0].0.contains("`command`: `/resume drop`"));
    assert!(sent[0].0.contains("`sender`: `999`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_resume_status_is_read_only_for_non_admin() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(AdminRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/resume status");
    msg.sender = "999".to_string();
    msg.session_key = "-200:999".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "resume status command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("No saved session context snapshot found.")
    );
    assert!(!sent[0].0.contains("reason=admin_required"));
    Ok(())
}

#[derive(Default)]
struct CommandScopedResetMockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl CommandScopedResetMockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for CommandScopedResetMockChannel {
    fn name(&self) -> &str {
        "command-scoped-reset-mock"
    }

    fn is_admin_user(&self, _identity: &str) -> bool {
        false
    }

    fn is_authorized_for_control_command(&self, identity: &str, command_text: &str) -> bool {
        identity == "777" && command_text.trim_start().starts_with("/reset")
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
async fn runtime_handle_inbound_reset_uses_command_scoped_authorization() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(CommandScopedResetMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/reset");
    msg.sender = "777".to_string();
    msg.session_key = "-200:777".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "reset command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("Session context reset."));
    assert!(!sent[0].0.contains("reason=admin_required"));
    Ok(())
}
