use async_trait::async_trait;

use crate::channels::traits::{Channel, ChannelMessage, RecipientCommandAdminUsersMutation};

use super::super::session_partition::TelegramSessionPartition;
use super::TelegramChannel;

#[async_trait]
impl Channel for TelegramChannel {
    fn name(&self) -> &str {
        "telegram"
    }

    fn session_partition_mode(&self) -> Option<String> {
        Some(self.session_partition().to_string())
    }

    fn set_session_partition_mode(&self, mode: &str) -> anyhow::Result<()> {
        let parsed = mode
            .parse::<TelegramSessionPartition>()
            .map_err(|_| anyhow::anyhow!("invalid session partition mode: {mode}"))?;
        self.set_session_partition(parsed);
        Ok(())
    }

    fn is_admin_user(&self, identity: &str) -> bool {
        self.is_admin_identity(identity)
    }

    fn is_authorized_for_control_command(&self, identity: &str, command_text: &str) -> bool {
        self.authorize_control_command(identity, command_text)
    }

    fn is_authorized_for_control_command_for_recipient(
        &self,
        identity: &str,
        command_text: &str,
        recipient: &str,
    ) -> bool {
        self.authorize_control_command_for_recipient(identity, command_text, recipient)
    }

    fn is_authorized_for_slash_command(&self, identity: &str, command_scope: &str) -> bool {
        self.authorize_slash_command(identity, command_scope)
    }

    fn is_authorized_for_slash_command_for_recipient(
        &self,
        identity: &str,
        command_scope: &str,
        recipient: &str,
    ) -> bool {
        self.authorize_slash_command_for_recipient(identity, command_scope, recipient)
    }

    fn recipient_command_admin_users(
        &self,
        recipient: &str,
    ) -> anyhow::Result<Option<Vec<String>>> {
        self.ensure_acl_fresh();
        self.recipient_override_admin_users(recipient)
    }

    fn mutate_recipient_command_admin_users(
        &self,
        recipient: &str,
        mutation: RecipientCommandAdminUsersMutation,
    ) -> anyhow::Result<Option<Vec<String>>> {
        self.ensure_acl_fresh();
        self.mutate_recipient_override_admin_users(recipient, mutation)
    }

    async fn send(&self, message: &str, recipient: &str) -> anyhow::Result<()> {
        self.send_text(message, recipient).await
    }

    async fn listen(&self, tx: tokio::sync::mpsc::Sender<ChannelMessage>) -> anyhow::Result<()> {
        self.listen_updates(tx).await
    }

    async fn health_check(&self) -> bool {
        self.health_probe().await
    }

    async fn start_typing(&self, recipient: &str) -> anyhow::Result<()> {
        self.send_chat_action(recipient, "typing").await
    }
}
