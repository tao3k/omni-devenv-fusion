use std::collections::HashMap;
use std::sync::Arc;
use std::sync::{PoisonError, RwLock};

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::{Mutex, mpsc};

use crate::channels::traits::{Channel, ChannelMessage, RecipientCommandAdminUsersMutation};

use super::{build_agent, build_job_manager, handle_inbound_message, inbound};

struct SessionAdminMockChannel {
    sent: Mutex<Vec<(String, String)>>,
    overrides: RwLock<HashMap<String, Vec<String>>>,
}

impl SessionAdminMockChannel {
    fn new() -> Self {
        Self {
            sent: Mutex::new(Vec::new()),
            overrides: RwLock::new(HashMap::new()),
        }
    }

    async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }
}

#[async_trait]
impl Channel for SessionAdminMockChannel {
    fn name(&self) -> &str {
        "session-admin-mock"
    }

    fn is_admin_user(&self, identity: &str) -> bool {
        identity == "888"
    }

    fn recipient_command_admin_users(
        &self,
        recipient: &str,
    ) -> anyhow::Result<Option<Vec<String>>> {
        if !recipient.starts_with('-') {
            return Err(anyhow::anyhow!(
                "recipient-scoped admin override is only supported for group chats"
            ));
        }
        Ok(self
            .overrides
            .read()
            .unwrap_or_else(PoisonError::into_inner)
            .get(recipient)
            .cloned())
    }

    fn mutate_recipient_command_admin_users(
        &self,
        recipient: &str,
        mutation: RecipientCommandAdminUsersMutation,
    ) -> anyhow::Result<Option<Vec<String>>> {
        if !recipient.starts_with('-') {
            return Err(anyhow::anyhow!(
                "recipient-scoped admin override is only supported for group chats"
            ));
        }
        let mut overrides = self
            .overrides
            .write()
            .unwrap_or_else(PoisonError::into_inner);
        let current = overrides.get(recipient).cloned().unwrap_or_default();
        let next = match mutation {
            RecipientCommandAdminUsersMutation::Set(entries) => dedup(entries),
            RecipientCommandAdminUsersMutation::Add(entries) => {
                let mut merged = current;
                merged.extend(entries);
                dedup(merged)
            }
            RecipientCommandAdminUsersMutation::Remove(entries) => {
                let removals = dedup(entries);
                let filtered: Vec<String> = current
                    .into_iter()
                    .filter(|entry| !removals.iter().any(|removal| removal == entry))
                    .collect();
                dedup(filtered)
            }
            RecipientCommandAdminUsersMutation::Clear => Vec::new(),
        };
        if next.is_empty() {
            overrides.remove(recipient);
            return Ok(None);
        }
        overrides.insert(recipient.to_string(), next.clone());
        Ok(Some(next))
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

fn dedup(entries: Vec<String>) -> Vec<String> {
    let mut out = Vec::new();
    for entry in entries {
        if !out.iter().any(|existing: &String| existing == &entry) {
            out.push(entry);
        }
    }
    out
}

#[tokio::test]
async fn runtime_handle_inbound_session_admin_add_and_list_json() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SessionAdminMockChannel::new());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    assert!(
        handle_inbound_message(
            inbound("/session admin add 1001,1002"),
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
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
    assert!(
        foreground_rx.try_recv().is_err(),
        "session admin commands should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 2);
    assert!(sent[0].0.contains("Session delegated admins updated."));
    assert!(sent[0].0.contains("action=add"));
    let payload: serde_json::Value = serde_json::from_str(&sent[1].0)?;
    assert_eq!(payload["kind"], "session_admin");
    assert_eq!(payload["updated"], false);
    assert_eq!(payload["scope"], "group");
    assert_eq!(
        payload["override_admin_users"],
        serde_json::json!(["1001", "1002"])
    );
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_admin_requires_admin() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SessionAdminMockChannel::new());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut non_admin = inbound("/session admin add 1001");
    non_admin.sender = "999".to_string();

    assert!(
        handle_inbound_message(
            non_admin,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent,
        )
        .await
    );
    assert!(
        foreground_rx.try_recv().is_err(),
        "session admin command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Control Command Permission Denied"));
    assert!(sent[0].0.contains("`command`: `/session admin`"));
    Ok(())
}

#[tokio::test]
async fn runtime_handle_inbound_session_admin_direct_chat_returns_scope_error() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(SessionAdminMockChannel::new());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let mut msg = inbound("/session admin list");
    msg.recipient = "12345".to_string();

    assert!(handle_inbound_message(msg, &channel_dyn, &foreground_tx, &job_manager, &agent).await);
    assert!(
        foreground_rx.try_recv().is_err(),
        "session admin command should not forward to foreground queue"
    );

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(
        sent[0]
            .0
            .contains("Failed to inspect session delegated admins")
    );
    assert!(
        sent[0]
            .0
            .contains("recipient-scoped admin override is only supported for group chats")
    );
    Ok(())
}
