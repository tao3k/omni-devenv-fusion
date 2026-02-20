#![allow(missing_docs)]

use anyhow::Result;
use omni_agent::{BoundedSessionStore, SessionSummarySegment};

fn sample_segment(
    summary: &str,
    turns: usize,
    tools: u32,
    created_at_ms: u64,
) -> SessionSummarySegment {
    SessionSummarySegment::new(summary.to_string(), turns, tools, created_at_ms)
}

#[tokio::test]
async fn bounded_store_summary_is_bounded_and_trimmed() -> Result<()> {
    let store = BoundedSessionStore::new_with_limits(16, 2, 20)?;
    let session_id = "s-summary-bounded";

    store
        .append_summary_segment(
            session_id,
            sample_segment(
                "first summary should be dropped after third insert",
                2,
                1,
                100,
            ),
        )
        .await?;
    store
        .append_summary_segment(
            session_id,
            sample_segment("second summary is kept", 3, 0, 101),
        )
        .await?;
    store
        .append_summary_segment(
            session_id,
            sample_segment("third summary is kept too", 1, 2, 102),
        )
        .await?;

    let summaries = store.get_recent_summary_segments(session_id, 10).await?;
    assert_eq!(summaries.len(), 2);
    assert!(summaries[0].summary.starts_with("second"));
    assert!(summaries[1].summary.starts_with("third"));
    assert!(summaries[0].summary.chars().count() <= 20);
    assert!(summaries[1].summary.chars().count() <= 20);
    Ok(())
}

#[tokio::test]
async fn clear_session_removes_summary_segments() -> Result<()> {
    let store = BoundedSessionStore::new_with_limits(8, 4, 128)?;
    let session_id = "s-summary-clear";

    store.append_turn(session_id, "u1", "a1", 1).await?;
    store
        .append_summary_segment(session_id, sample_segment("done", 1, 1, 200))
        .await?;

    assert!(store.get_stats(session_id).await?.is_some());
    assert_eq!(
        store
            .get_recent_summary_segments(session_id, 10)
            .await?
            .len(),
        1
    );

    store.clear(session_id).await?;

    assert!(store.get_stats(session_id).await?.is_none());
    assert!(
        store
            .get_recent_summary_segments(session_id, 10)
            .await?
            .is_empty()
    );
    Ok(())
}
