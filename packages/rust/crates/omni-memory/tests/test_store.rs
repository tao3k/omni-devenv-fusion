//! EpisodeStore tests.

mod common;

use omni_memory::{Episode, EpisodeStore, StoreConfig};

#[test]
fn test_store_creation() {
    let path = common::test_store_path("test");
    let store = EpisodeStore::new(StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    });

    assert_eq!(store.len(), 0);
    assert!(store.is_empty());
}

#[test]
fn test_store_episode() {
    let store = EpisodeStore::default();

    let episode = Episode::new(
        "ep-001".to_string(),
        "debug network error".to_string(),
        store.encoder().encode("debug network error"),
        "Checked firewall".to_string(),
        "success".to_string(),
    );

    let id = store.store(episode).unwrap();
    assert_eq!(id, "ep-001");
    assert_eq!(store.len(), 1);
}

#[test]
fn test_recall() {
    let store = EpisodeStore::default();

    for i in 0..5 {
        let episode = Episode::new(
            format!("ep-{}", i),
            format!("intent {}", i),
            store.encoder().encode(&format!("intent {}", i)),
            format!("experience {}", i),
            "success".to_string(),
        );
        store.store(episode).unwrap();
    }

    let results = store.recall("intent 0", 3);
    assert!(results.len() <= 3);
}

#[test]
fn test_two_phase_recall() {
    let store = EpisodeStore::default();

    for i in 0..5 {
        let episode = Episode::new(
            format!("ep-{}", i),
            format!("debug error {}", i),
            store.encoder().encode(&format!("debug error {}", i)),
            format!("experience {}", i),
            if i < 3 { "success" } else { "failure" }.to_string(),
        );
        store.store(episode).unwrap();
    }

    store.update_q("ep-0", 1.0);
    store.update_q("ep-1", 0.8);
    store.update_q("ep-2", 0.3);

    let results = store.two_phase_recall("debug error", 5, 3, 0.5);
    assert!(results.len() <= 3);
}

#[test]
fn test_q_update() {
    let store = EpisodeStore::default();

    let episode = Episode::new(
        "ep-001".to_string(),
        "test".to_string(),
        store.encoder().encode("test"),
        "experience".to_string(),
        "success".to_string(),
    );
    store.store(episode).unwrap();

    let q_initial = store.q_table.get_q("ep-001");
    assert_eq!(q_initial, 0.5);

    let q_new = store.update_q("ep-001", 1.0);
    assert!(q_new > 0.5);
}
