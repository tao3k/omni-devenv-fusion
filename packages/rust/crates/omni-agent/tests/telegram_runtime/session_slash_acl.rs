use std::sync::Arc;

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::{Mutex, mpsc};

use crate::channels::traits::{Channel, ChannelMessage};

use super::{build_agent, build_job_manager, handle_inbound_message, inbound};

#[derive(Default)]
struct SlashRestrictedMockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl SlashRestrictedMockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for SlashRestrictedMockChannel {
    fn name(&self) -> &str {
        "slash-restricted-mock"
    }

    fn is_authorized_for_slash_command(&self, identity: &str, command_scope: &str) -> bool {
        identity == "888" && command_scope == "session.memory"
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

#[derive(Default)]
struct RecipientScopedSlashMockChannel {
    sent: Mutex<Vec<(String, String)>>,
}

impl RecipientScopedSlashMockChannel {
    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for RecipientScopedSlashMockChannel {
    fn name(&self) -> &str {
        "recipient-scoped-slash-mock"
    }

    fn is_authorized_for_slash_command(&self, _identity: &str, _command_scope: &str) -> bool {
        false
    }

    fn is_authorized_for_slash_command_for_recipient(
        &self,
        identity: &str,
        command_scope: &str,
        recipient: &str,
    ) -> bool {
        identity == "777" && command_scope == "session.memory" && recipient == "-200:42"
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
async fn runtime_handle_inbound_session_memory_requires_slash_permission() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SlashRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/session memory");
    msg.sender = "999".to_string();
    msg.session_key = "-200:999".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "managed slash commands should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Slash Command Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `slash_permission_required`"));
    assert!(sent[0].0.contains("`command`: `/session memory`"));
    assert!(sent[0].0.contains("`sender`: `999`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_allows_authorized_sender() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SlashRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let msg = inbound("/session memory");

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "managed slash commands should be handled by runtime command path"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0].0.contains("## Session Memory")
            || sent[0].0.contains("No memory recall snapshot found")
    );
    assert!(!sent[0].0.contains("reason=slash_permission_required"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_budget_denies_when_scope_not_granted() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SlashRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let msg = inbound("/session budget");

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "managed slash command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Slash Command Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `slash_permission_required`"));
    assert!(sent[0].0.contains("`command`: `/session budget`"));
    assert!(sent[0].0.contains("`sender`: `888`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_plain_text_is_not_blocked_by_slash_acl() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SlashRestrictedMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("hello from non-slash turn");
    msg.sender = "999".to_string();
    msg.session_key = "-200:999".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);

    let forwarded = foreground_rx
        .try_recv()
        .expect("plain text turn should be forwarded");
    assert_eq!(forwarded.content, "hello from non-slash turn");
    assert_eq!(forwarded.sender, "999");

    let sent = channel.sent_messages().await;
    assert!(
        sent.is_empty(),
        "plain text turns should not trigger slash-permission denial replies"
    );
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_memory_honors_recipient_scoped_slash_authorization()
-> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(RecipientScopedSlashMockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/session memory");
    msg.sender = "777".to_string();
    msg.recipient = "-200:42".to_string();
    msg.session_key = "-200:42:777".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "managed slash commands should be handled by runtime command path"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0].0.contains("## Session Memory")
            || sent[0].0.contains("No memory recall snapshot found")
    );
    assert!(!sent[0].0.contains("slash_permission_required"));
    Ok(())
}
