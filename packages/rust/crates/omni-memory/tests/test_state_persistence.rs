//! State persistence tests for EpisodeStore.

use omni_memory::{Episode, EpisodeStore, StoreConfig};

#[test]
fn save_state_creates_parent_dirs_and_loads_roundtrip() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let store_root = temp_dir.path().join("nested").join("memory-state");

    let config = StoreConfig {
        path: store_root.to_string_lossy().to_string(),
        embedding_dim: 128,
        table_name: "episodes".to_string(),
    };

    let store = EpisodeStore::new(config.clone());
    let episode = Episode::new(
        "ep-1".to_string(),
        "fix timeout".to_string(),
        store.encoder().encode("fix timeout"),
        "Raised timeout and retried".to_string(),
        "success".to_string(),
    );
    store.store(episode).expect("failed to store episode");
    store.update_q("ep-1", 1.0);

    store.save_state().expect("failed to persist state");

    let episodes_path = store.episodes_state_path();
    let q_path = store.q_table_state_path();
    assert!(episodes_path.exists(), "episodes state file should exist");
    assert!(q_path.exists(), "q-table state file should exist");

    let reloaded = EpisodeStore::new(config);
    reloaded.load_state().expect("failed to load state");

    assert_eq!(reloaded.len(), 1);
    assert!(reloaded.get("ep-1").is_some());
    assert!(reloaded.q_table.get_q("ep-1") > 0.5);
}

#[test]
fn save_state_uses_table_scoped_filenames() {
    let temp_dir = tempfile::tempdir().expect("failed to create temp dir");
    let root = temp_dir.path().join("memory");

    let alpha = EpisodeStore::new(StoreConfig {
        path: root.to_string_lossy().to_string(),
        embedding_dim: 128,
        table_name: "alpha".to_string(),
    });
    alpha
        .store(Episode::new(
            "alpha-1".to_string(),
            "alpha task".to_string(),
            alpha.encoder().encode("alpha task"),
            "alpha experience".to_string(),
            "success".to_string(),
        ))
        .expect("failed to store alpha episode");
    alpha.save_state().expect("failed to save alpha state");

    let beta = EpisodeStore::new(StoreConfig {
        path: root.to_string_lossy().to_string(),
        embedding_dim: 128,
        table_name: "beta".to_string(),
    });
    beta.store(Episode::new(
        "beta-1".to_string(),
        "beta task".to_string(),
        beta.encoder().encode("beta task"),
        "beta experience".to_string(),
        "success".to_string(),
    ))
    .expect("failed to store beta episode");
    beta.save_state().expect("failed to save beta state");

    assert!(root.join("alpha.episodes.json").exists());
    assert!(root.join("alpha.q_table.json").exists());
    assert!(root.join("beta.episodes.json").exists());
    assert!(root.join("beta.q_table.json").exists());
}
