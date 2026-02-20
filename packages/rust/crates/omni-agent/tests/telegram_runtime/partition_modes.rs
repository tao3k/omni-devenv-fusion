use std::sync::Arc;

use anyhow::Result;
use tokio::sync::mpsc;

use crate::channels::telegram::TelegramSessionPartition;
use crate::channels::traits::{Channel, ChannelMessage};

use super::{
    MockChannel, SessionIdentity, build_agent, build_job_manager, handle_inbound_message,
    partitioned_inbound_message, run_partition_reset_status_flow,
};

#[tokio::test]
async fn runtime_partition_chat_user_isolates_users() -> Result<()> {
    run_partition_reset_status_flow(
        TelegramSessionPartition::ChatUser,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: None,
        },
        SessionIdentity {
            chat_id: -200,
            user_id: 999,
            thread_id: None,
        },
        false,
    )
    .await
}

#[tokio::test]
async fn runtime_partition_chat_only_shares_users_in_same_chat() -> Result<()> {
    run_partition_reset_status_flow(
        TelegramSessionPartition::ChatOnly,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: None,
        },
        SessionIdentity {
            chat_id: -200,
            user_id: 999,
            thread_id: None,
        },
        true,
    )
    .await
}

#[tokio::test]
async fn runtime_partition_chat_only_isolates_same_user_across_chats() -> Result<()> {
    run_partition_reset_status_flow(
        TelegramSessionPartition::ChatOnly,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: None,
        },
        SessionIdentity {
            chat_id: -201,
            user_id: 888,
            thread_id: None,
        },
        false,
    )
    .await
}

#[tokio::test]
async fn runtime_partition_user_only_shares_across_chats() -> Result<()> {
    run_partition_reset_status_flow(
        TelegramSessionPartition::UserOnly,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: None,
        },
        SessionIdentity {
            chat_id: -201,
            user_id: 888,
            thread_id: None,
        },
        true,
    )
    .await
}

#[tokio::test]
async fn runtime_partition_chat_thread_user_isolates_threads() -> Result<()> {
    run_partition_reset_status_flow(
        TelegramSessionPartition::ChatThreadUser,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: Some(11),
        },
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: Some(22),
        },
        false,
    )
    .await
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
async fn runtime_partition_chat_user_concurrent_resets_stay_isolated() -> Result<()> {
    let agent = build_agent().await?;
    let channel = Arc::new(MockChannel::default());
    let channel_dyn: Arc<dyn Channel> = channel.clone();
    let job_manager = build_job_manager(agent.clone());
    let (foreground_tx, mut foreground_rx) = mpsc::channel::<ChannelMessage>(8);

    let reset_user_888 = partitioned_inbound_message(
        TelegramSessionPartition::ChatUser,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: None,
        },
        "/reset",
    )?;
    let reset_user_999 = partitioned_inbound_message(
        TelegramSessionPartition::ChatUser,
        SessionIdentity {
            chat_id: -200,
            user_id: 999,
            thread_id: None,
        },
        "/reset",
    )?;
    let session_888 = format!("{}:{}", reset_user_888.channel, reset_user_888.session_key);
    let session_999 = format!("{}:{}", reset_user_999.channel, reset_user_999.session_key);
    assert_ne!(session_888, session_999);

    agent
        .append_turn_for_session(&session_888, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_888, "u2", "a2")
        .await?;
    agent
        .append_turn_for_session(&session_999, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_999, "u2", "a2")
        .await?;

    let f1 = handle_inbound_message(
        reset_user_888,
        &channel_dyn,
        &foreground_tx,
        &job_manager,
        &agent,
    );
    let f2 = handle_inbound_message(
        reset_user_999,
        &channel_dyn,
        &foreground_tx,
        &job_manager,
        &agent,
    );
    let (handled_1, handled_2) = tokio::join!(f1, f2);
    assert!(handled_1);
    assert!(handled_2);

    let status_888 = partitioned_inbound_message(
        TelegramSessionPartition::ChatUser,
        SessionIdentity {
            chat_id: -200,
            user_id: 888,
            thread_id: None,
        },
        "/resume status",
    )?;
    let status_999 = partitioned_inbound_message(
        TelegramSessionPartition::ChatUser,
        SessionIdentity {
            chat_id: -200,
            user_id: 999,
            thread_id: None,
        },
        "/resume status",
    )?;

    assert!(
        handle_inbound_message(
            status_888,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent
        )
        .await
    );
    assert!(
        handle_inbound_message(
            status_999,
            &channel_dyn,
            &foreground_tx,
            &job_manager,
            &agent
        )
        .await
    );

    assert!(
        foreground_rx.try_recv().is_err(),
        "session commands should not enter foreground queue"
    );
    let sent = channel.sent_messages().await;
    assert_eq!(sent.len(), 4);
    assert!(sent[0].0.contains("messages_cleared=4"));
    assert!(sent[1].0.contains("messages_cleared=4"));
    assert!(sent[2].0.contains("Saved session context snapshot:"));
    assert!(sent[2].0.contains("messages=4"));
    assert!(sent[3].0.contains("Saved session context snapshot:"));
    assert!(sent[3].0.contains("messages=4"));
    Ok(())
}
