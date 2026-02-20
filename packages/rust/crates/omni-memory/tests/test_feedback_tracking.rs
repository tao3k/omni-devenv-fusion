#![allow(missing_docs)]

use anyhow::Result;
use omni_memory::{Episode, EpisodeStore, StoreConfig};

fn new_store() -> EpisodeStore {
    let tmp = tempfile::tempdir().expect("tempdir");
    EpisodeStore::new(StoreConfig {
        path: tmp.path().join("memory").to_string_lossy().to_string(),
        embedding_dim: 8,
        table_name: "feedback_tracking".to_string(),
    })
}

fn episode(id: &str) -> Episode {
    Episode::new(
        id.to_string(),
        "intent".to_string(),
        vec![0.1; 8],
        "experience".to_string(),
        "completed".to_string(),
    )
}

#[test]
fn record_feedback_updates_success_and_failure_counts() -> Result<()> {
    let store = new_store();
    store.store(episode("ep-1"))?;

    assert!(store.record_feedback("ep-1", true));
    assert!(store.record_feedback("ep-1", false));

    let ep = store.get("ep-1").expect("episode should exist");
    assert_eq!(ep.success_count, 1);
    assert_eq!(ep.failure_count, 1);
    Ok(())
}

#[test]
fn record_feedback_returns_false_for_missing_episode() {
    let store = new_store();
    assert!(!store.record_feedback("missing", true));
}
