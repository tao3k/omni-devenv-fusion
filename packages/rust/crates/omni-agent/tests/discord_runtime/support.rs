use std::sync::Arc;

use anyhow::Result;
use async_trait::async_trait;
use tokio::sync::{Mutex, RwLock, mpsc};

use crate::agent::Agent;
use crate::channels::traits::{Channel, ChannelMessage};
use crate::config::AgentConfig;
use crate::jobs::{JobManager, JobManagerConfig, TurnRunner};

pub(super) use super::super::dispatch::process_discord_message;

#[derive(Default)]
pub(super) struct MockChannel {
    sent: Mutex<Vec<(String, String)>>,
    partition_mode: RwLock<String>,
    allow_control_commands: bool,
    denied_slash_scopes: Vec<String>,
}

impl MockChannel {
    pub(super) fn with_acl(
        allow_control_commands: bool,
        denied_slash_scopes: impl IntoIterator<Item = impl AsRef<str>>,
    ) -> Self {
        Self {
            sent: Mutex::new(Vec::new()),
            partition_mode: RwLock::new("guild_channel_user".to_string()),
            allow_control_commands,
            denied_slash_scopes: denied_slash_scopes
                .into_iter()
                .map(|scope| scope.as_ref().to_string())
                .collect(),
        }
    }

    pub(super) async fn sent_messages(&self) -> Vec<(String, String)> {
        self.sent.lock().await.clone()
    }

    pub(super) async fn partition_mode(&self) -> String {
        self.partition_mode.read().await.clone()
    }
}

#[async_trait]
impl Channel for MockChannel {
    fn name(&self) -> &str {
        "discord-runtime-mock"
    }

    fn session_partition_mode(&self) -> Option<String> {
        Some(
            self.partition_mode
                .try_read()
                .map(|guard| guard.clone())
                .unwrap_or_else(|_| "guild_channel_user".to_string()),
        )
    }

    fn set_session_partition_mode(&self, mode: &str) -> anyhow::Result<()> {
        if let Ok(mut guard) = self.partition_mode.try_write() {
            *guard = mode.to_string();
            Ok(())
        } else {
            Err(anyhow::anyhow!("failed to acquire partition write lock"))
        }
    }

    fn is_authorized_for_control_command(&self, _identity: &str, _command_text: &str) -> bool {
        self.allow_control_commands
    }

    fn is_authorized_for_slash_command(&self, _identity: &str, command_scope: &str) -> bool {
        !self
            .denied_slash_scopes
            .iter()
            .any(|scope| scope == command_scope)
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

pub(super) fn inbound(content: &str) -> ChannelMessage {
    ChannelMessage {
        id: "discord_msg_1".to_string(),
        sender: "1001".to_string(),
        recipient: "2001".to_string(),
        session_key: "3001:2001:1001".to_string(),
        content: content.to_string(),
        channel: "discord".to_string(),
        timestamp: 0,
    }
}

pub(super) async fn build_agent() -> Result<Arc<Agent>> {
    let config = AgentConfig {
        inference_url: "http://127.0.0.1:1/v1/chat/completions".to_string(),
        model: "gpt-4o-mini".to_string(),
        api_key: None,
        max_tool_rounds: 1,
        ..AgentConfig::default()
    };
    Ok(Arc::new(Agent::from_config(config).await?))
}

pub(super) fn start_job_manager(agent: Arc<Agent>) -> Arc<JobManager> {
    let runner: Arc<dyn TurnRunner> = agent.clone();
    let (manager, _completion_rx) = JobManager::start(runner, JobManagerConfig::default());
    manager
}
