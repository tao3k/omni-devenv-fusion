#![allow(missing_docs)]

use std::time::{SystemTime, UNIX_EPOCH};

use omni_agent::{Agent, AgentConfig, BoundedSessionStore, SessionContextMode, SessionStore};

fn unique_session_id(prefix: &str) -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("{prefix}-{nanos}")
}

async fn build_agent(window_max_turns: Option<usize>) -> anyhow::Result<Agent> {
    let mut config = AgentConfig::default();
    config.inference_url = "http://127.0.0.1:4000/v1/chat/completions".to_string();
    config.window_max_turns = window_max_turns;
    config.memory = None;
    config.consolidation_threshold_turns = None;
    Agent::from_config(config).await
}

fn live_redis_url() -> Option<String> {
    if let Ok(url) = std::env::var("VALKEY_URL")
        && !url.trim().is_empty()
    {
        return Some(url);
    }
    None
}

async fn build_agent_with_shared_redis(
    redis_url: &str,
    key_prefix: &str,
    window_max_turns: usize,
) -> anyhow::Result<Agent> {
    let mut config = AgentConfig::default();
    config.inference_url = "http://127.0.0.1:4000/v1/chat/completions".to_string();
    config.window_max_turns = Some(window_max_turns);
    config.memory = None;
    config.consolidation_threshold_turns = None;

    let session = SessionStore::new_with_redis(
        redis_url.to_string(),
        Some(key_prefix.to_string()),
        Some(120),
    )?;
    let bounded_session = Some(BoundedSessionStore::new_with_redis_and_limits(
        window_max_turns,
        redis_url.to_string(),
        Some(key_prefix.to_string()),
        Some(120),
        config.summary_max_segments,
        config.summary_max_chars,
    )?);

    Agent::from_config_with_session_backends_for_test(config, session, bounded_session).await
}

#[tokio::test]
async fn resume_context_returns_none_without_snapshot() -> anyhow::Result<()> {
    let agent = build_agent(None).await?;
    let session_id = unique_session_id("session-context-empty");

    let info = agent.peek_context_window_backup(&session_id).await?;
    assert!(info.is_none());

    let restored = agent.resume_context_window(&session_id).await?;
    assert!(restored.is_none());
    Ok(())
}

#[tokio::test]
async fn reset_resume_unbounded_keeps_snapshot_across_repeated_reset() -> anyhow::Result<()> {
    let agent = build_agent(None).await?;
    let session_id = unique_session_id("session-context-unbounded");

    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;

    let first_reset = agent.reset_context_window(&session_id).await?;
    assert_eq!(first_reset.messages, 4);
    assert_eq!(first_reset.summary_segments, 0);

    let info = agent
        .peek_context_window_backup(&session_id)
        .await?
        .expect("reset should persist a snapshot");
    assert_eq!(info.messages, 4);
    assert_eq!(info.summary_segments, 0);
    assert!(info.saved_at_unix_ms.is_some());
    assert!(info.saved_age_secs.is_some());
    assert!(info.saved_age_secs.unwrap_or_default() <= 60);

    let second_reset = agent.reset_context_window(&session_id).await?;
    assert_eq!(second_reset.messages, 0);
    assert_eq!(second_reset.summary_segments, 0);

    let resumed = agent.resume_context_window(&session_id).await?;
    let resumed = resumed.expect("snapshot from first reset should still be restorable");
    assert_eq!(resumed.messages, 4);
    assert_eq!(resumed.summary_segments, 0);

    let info_after_resume = agent.peek_context_window_backup(&session_id).await?;
    assert!(info_after_resume.is_none());

    Ok(())
}

#[tokio::test]
async fn reset_resume_bounded_restores_messages() -> anyhow::Result<()> {
    let agent = build_agent(Some(16)).await?;
    let session_id = unique_session_id("session-context-bounded");

    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u3", "a3")
        .await?;

    let reset_stats = agent.reset_context_window(&session_id).await?;
    assert_eq!(reset_stats.messages, 6);

    let resumed = agent.resume_context_window(&session_id).await?;
    let resumed = resumed.expect("bounded session snapshot should be restorable");
    assert_eq!(resumed.messages, 6);
    assert_eq!(resumed.summary_segments, 0);

    let second_resume = agent.resume_context_window(&session_id).await?;
    assert!(second_resume.is_none());

    let post_restore_reset = agent.reset_context_window(&session_id).await?;
    assert_eq!(post_restore_reset.messages, 6);

    Ok(())
}

#[tokio::test]
async fn inspect_context_window_reports_unbounded_counts() -> anyhow::Result<()> {
    let agent = build_agent(None).await?;
    let session_id = unique_session_id("session-context-inspect-unbounded");

    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;

    let info = agent.inspect_context_window(&session_id).await?;
    assert_eq!(info.mode, SessionContextMode::Unbounded);
    assert_eq!(info.messages, 4);
    assert_eq!(info.summary_segments, 0);
    assert_eq!(info.window_turns, None);
    assert_eq!(info.window_slots, None);
    assert_eq!(info.total_tool_calls, None);
    Ok(())
}

#[tokio::test]
async fn inspect_context_window_reports_bounded_counts() -> anyhow::Result<()> {
    let agent = build_agent(Some(8)).await?;
    let session_id = unique_session_id("session-context-inspect-bounded");

    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u3", "a3")
        .await?;

    let info = agent.inspect_context_window(&session_id).await?;
    assert_eq!(info.mode, SessionContextMode::Bounded);
    assert_eq!(info.messages, 6);
    assert_eq!(info.summary_segments, 0);
    assert_eq!(info.window_turns, Some(3));
    assert_eq!(info.window_slots, Some(6));
    assert_eq!(info.total_tool_calls, Some(0));
    Ok(())
}

#[tokio::test]
async fn drop_context_window_backup_clears_snapshot_without_restore() -> anyhow::Result<()> {
    let agent = build_agent(Some(8)).await?;
    let session_id = unique_session_id("session-context-drop");

    agent
        .append_turn_for_session(&session_id, "u1", "a1")
        .await?;
    agent
        .append_turn_for_session(&session_id, "u2", "a2")
        .await?;

    let reset_stats = agent.reset_context_window(&session_id).await?;
    assert_eq!(reset_stats.messages, 4);

    let dropped = agent.drop_context_window_backup(&session_id).await?;
    assert!(dropped, "snapshot should exist after reset");

    let info_after_drop = agent.peek_context_window_backup(&session_id).await?;
    assert!(info_after_drop.is_none());

    let resumed = agent.resume_context_window(&session_id).await?;
    assert!(resumed.is_none(), "drop should prevent later restore");

    let dropped_again = agent.drop_context_window_backup(&session_id).await?;
    assert!(!dropped_again, "dropping twice should be idempotent");
    Ok(())
}

#[tokio::test]
async fn reset_resume_bounded_preserves_tool_call_counts() -> anyhow::Result<()> {
    let agent = build_agent(Some(8)).await?;
    let session_id = unique_session_id("session-context-bounded-tools");

    agent
        .append_turn_with_tool_count_for_session(&session_id, "u1", "a1", 2)
        .await?;
    agent
        .append_turn_with_tool_count_for_session(&session_id, "u2", "a2", 1)
        .await?;

    let before = agent.inspect_context_window(&session_id).await?;
    assert_eq!(before.mode, SessionContextMode::Bounded);
    assert_eq!(before.window_turns, Some(2));
    assert_eq!(before.window_slots, Some(4));
    assert_eq!(before.total_tool_calls, Some(3));

    let _ = agent.reset_context_window(&session_id).await?;
    let resumed = agent.resume_context_window(&session_id).await?;
    assert!(
        resumed.is_some(),
        "bounded session snapshot should be restored"
    );

    let after = agent.inspect_context_window(&session_id).await?;
    assert_eq!(after.mode, SessionContextMode::Bounded);
    assert_eq!(after.window_turns, Some(2));
    assert_eq!(after.window_slots, Some(4));
    assert_eq!(after.total_tool_calls, Some(3));
    Ok(())
}

#[tokio::test]
#[ignore = "requires live valkey server"]
async fn reset_resume_bounded_restores_across_agent_instances_with_valkey() -> anyhow::Result<()> {
    let Some(redis_url) = live_redis_url() else {
        eprintln!("skip: set VALKEY_URL");
        return Ok(());
    };

    let prefix = unique_session_id("session-context-cross-instance");
    let session_id = unique_session_id("session-context-shared");
    let agent_a = build_agent_with_shared_redis(&redis_url, &prefix, 8).await?;
    let agent_b = build_agent_with_shared_redis(&redis_url, &prefix, 8).await?;

    agent_a
        .append_turn_with_tool_count_for_session(&session_id, "u1", "a1", 2)
        .await?;
    agent_a
        .append_turn_with_tool_count_for_session(&session_id, "u2", "a2", 1)
        .await?;

    let before_reset = agent_b.inspect_context_window(&session_id).await?;
    assert_eq!(before_reset.mode, SessionContextMode::Bounded);
    assert_eq!(before_reset.window_turns, Some(2));
    assert_eq!(before_reset.window_slots, Some(4));
    assert_eq!(before_reset.total_tool_calls, Some(3));

    let reset_stats = agent_a.reset_context_window(&session_id).await?;
    assert_eq!(reset_stats.messages, 4);
    assert_eq!(reset_stats.summary_segments, 0);

    let after_reset = agent_b.inspect_context_window(&session_id).await?;
    assert_eq!(after_reset.messages, 0);
    assert_eq!(after_reset.window_turns, Some(0));
    assert_eq!(after_reset.window_slots, Some(0));
    assert_eq!(after_reset.total_tool_calls, Some(0));

    let resumed = agent_b.resume_context_window(&session_id).await?;
    let resumed = resumed.expect("snapshot should be restored by second agent instance");
    assert_eq!(resumed.messages, 4);
    assert_eq!(resumed.summary_segments, 0);

    let after_resume = agent_a.inspect_context_window(&session_id).await?;
    assert_eq!(after_resume.mode, SessionContextMode::Bounded);
    assert_eq!(after_resume.window_turns, Some(2));
    assert_eq!(after_resume.window_slots, Some(4));
    assert_eq!(after_resume.total_tool_calls, Some(3));

    assert!(
        agent_a
            .peek_context_window_backup(&session_id)
            .await?
            .is_none()
    );
    assert!(
        agent_b
            .peek_context_window_backup(&session_id)
            .await?
            .is_none()
    );

    // Cleanup active state for this unique session key.
    let _ = agent_a.reset_context_window(&session_id).await?;
    let _ = agent_a.drop_context_window_backup(&session_id).await?;
    Ok(())
}
