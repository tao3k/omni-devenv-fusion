use anyhow::Result;
use omni_memory::{Episode, EpisodeStore, StoreConfig};

use super::{apply_recall_credit, select_recall_credit_candidates};
use crate::agent::memory_recall_feedback::RecallOutcome;

fn new_store() -> EpisodeStore {
    let tmp = tempfile::tempdir().expect("tempdir");
    EpisodeStore::new(StoreConfig {
        path: tmp.path().join("memory").to_string_lossy().to_string(),
        embedding_dim: 8,
        table_name: "agent_recall_credit".to_string(),
    })
}

fn episode(id: &str) -> Episode {
    Episode::new(
        id.to_string(),
        format!("intent-{id}"),
        vec![0.1; 8],
        format!("experience-{id}"),
        "completed".to_string(),
    )
}

#[test]
fn select_recall_credit_candidates_keeps_rank_order_and_limit() -> Result<()> {
    let store = new_store();
    store.store(episode("ep-1"))?;
    store.store(episode("ep-2"))?;
    store.store(episode("ep-3"))?;

    let recalled = vec![
        (store.get("ep-1").expect("ep-1"), 0.91),
        (store.get("ep-2").expect("ep-2"), 0.72),
        (store.get("ep-3").expect("ep-3"), 0.61),
    ];

    let selected = select_recall_credit_candidates(&recalled, 2);
    assert_eq!(selected.len(), 2);
    assert_eq!(selected[0].episode_id, "ep-1");
    assert_eq!(selected[1].episode_id, "ep-2");
    Ok(())
}

#[test]
fn apply_recall_credit_success_increases_q_and_tracks_success() -> Result<()> {
    let store = new_store();
    store.store(episode("ep-1"))?;
    store.update_q("ep-1", 0.2);
    let candidates = vec![super::RecalledEpisodeCandidate {
        episode_id: "ep-1".to_string(),
        score: 0.9,
    }];

    let updates = apply_recall_credit(&store, &candidates, RecallOutcome::Success);
    assert_eq!(updates.len(), 1);
    assert!(updates[0].updated_q > updates[0].previous_q);

    let ep = store.get("ep-1").expect("episode should exist");
    assert_eq!(ep.success_count, 1);
    assert_eq!(ep.failure_count, 0);
    Ok(())
}

#[test]
fn apply_recall_credit_failure_decreases_q_and_tracks_failure() -> Result<()> {
    let store = new_store();
    store.store(episode("ep-1"))?;
    store.update_q("ep-1", 0.9);
    let candidates = vec![super::RecalledEpisodeCandidate {
        episode_id: "ep-1".to_string(),
        score: 0.8,
    }];

    let updates = apply_recall_credit(&store, &candidates, RecallOutcome::Failure);
    assert_eq!(updates.len(), 1);
    assert!(updates[0].updated_q < updates[0].previous_q);

    let ep = store.get("ep-1").expect("episode should exist");
    assert_eq!(ep.success_count, 0);
    assert_eq!(ep.failure_count, 1);
    Ok(())
}
