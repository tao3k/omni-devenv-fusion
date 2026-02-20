use std::sync::Arc;

use anyhow::Result;

use crate::channels::traits::Channel;

use super::support::{
    MockChannel, build_agent, inbound, process_discord_message, start_job_manager,
};

#[tokio::test]
async fn process_discord_message_denies_unauthorized_control_command() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(false, std::iter::empty::<&str>()));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(agent, channel_dyn, inbound("/reset"), &job_manager, 10).await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Control Command Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `admin_required`"));
    assert!(sent[0].0.contains("`command`: `/reset`"));
    Ok(())
}

#[tokio::test]
async fn process_discord_message_denies_unauthorized_slash_command() -> Result<()> {
    let agent = build_agent().await?;
    let job_manager = start_job_manager(agent.clone());
    let channel = Arc::new(MockChannel::with_acl(true, ["session.memory"]));
    let channel_dyn: Arc<dyn Channel> = channel.clone();

    process_discord_message(
        agent,
        channel_dyn,
        inbound("/session memory"),
        &job_manager,
        10,
    )
    .await;

    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 1);
    assert!(sent[0].0.contains("## Slash Command Permission Denied"));
    assert!(sent[0].0.contains("`reason`: `slash_permission_required`"));
    assert!(sent[0].0.contains("`command`: `/session memory`"));
    Ok(())
}
