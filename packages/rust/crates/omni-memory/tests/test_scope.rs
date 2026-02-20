//! Scope isolation tests for `EpisodeStore`.

mod common;

use omni_memory::{Episode, EpisodeStore, StoreConfig};

const SCOPE_A: &str = "telegram:-100:111";
const SCOPE_B: &str = "telegram:-100:222";
const WRONG_SCOPE: &str = "legacy-scope";

fn build_store(test_name: &str) -> EpisodeStore {
    EpisodeStore::new(StoreConfig {
        path: common::test_store_path(test_name),
        embedding_dim: 4,
        table_name: test_name.to_string(),
    })
}

#[test]
fn scoped_recall_excludes_other_sessions() {
    let store = build_store("scope_isolation");
    let embedding_a = vec![1.0, 0.0, 0.0, 0.0];
    let embedding_b = vec![0.0, 1.0, 0.0, 0.0];

    store
        .store(Episode::new_scoped(
            "ep-a".to_string(),
            "session a intent".to_string(),
            embedding_a.clone(),
            "session a response".to_string(),
            "completed".to_string(),
            SCOPE_A.to_string(),
        ))
        .expect("scope A store should succeed");
    store
        .store(Episode::new_scoped(
            "ep-b".to_string(),
            "session b intent".to_string(),
            embedding_b,
            "session b response".to_string(),
            "completed".to_string(),
            SCOPE_B.to_string(),
        ))
        .expect("scope B store should succeed");

    let scoped = store.two_phase_recall_with_embedding_for_scope(SCOPE_A, &embedding_a, 8, 8, 0.0);
    assert_eq!(
        scoped.len(),
        1,
        "scoped recall must only include matching scope"
    );
    assert_eq!(scoped[0].0.id, "ep-a");
    assert_eq!(scoped[0].0.scope_key(), SCOPE_A);

    let global = store.two_phase_recall_with_embedding(&embedding_a, 8, 8, 0.0);
    assert_eq!(global.len(), 2, "global recall still sees all scopes");
}

#[test]
fn store_for_scope_overrides_episode_scope() {
    let store = build_store("scope_override");
    let embedding = vec![1.0, 0.0, 0.0, 0.0];

    store
        .store_for_scope(
            SCOPE_A,
            Episode::new_scoped(
                "ep-override".to_string(),
                "intent".to_string(),
                embedding,
                "experience".to_string(),
                "completed".to_string(),
                WRONG_SCOPE.to_string(),
            ),
        )
        .expect("scoped store should succeed");

    let stored = store
        .get("ep-override")
        .expect("episode should be persisted after scoped store");
    assert_eq!(stored.scope_key(), SCOPE_A);
}

#[test]
fn global_episodes_are_not_returned_by_scoped_recall() {
    let store = build_store("scope_global_exclusion");

    store
        .store(Episode::new(
            "ep-global".to_string(),
            "same intent".to_string(),
            vec![1.0, 0.0, 0.0, 0.0],
            "global episode".to_string(),
            "completed".to_string(),
        ))
        .expect("global store should succeed");

    let scoped = store.recall_for_scope(SCOPE_A, "same intent", 8);
    assert!(
        scoped.is_empty(),
        "session-scoped recall must not include global or legacy episodes"
    );
}

#[test]
fn legacy_agent_episode_ids_are_auto_scoped() {
    let store = build_store("scope_legacy_id_inference");
    let legacy_scope = "telegram:-200:7001";
    let legacy_id = format!("turn-{legacy_scope}-1700000000123");
    let embedding = vec![1.0, 0.0, 0.0, 0.0];

    // Legacy payloads may not contain scope but keep scoped ids.
    store
        .store(Episode::new(
            legacy_id,
            "legacy scoped intent".to_string(),
            embedding.clone(),
            "legacy response".to_string(),
            "completed".to_string(),
        ))
        .expect("legacy payload store should succeed");

    let scoped =
        store.two_phase_recall_with_embedding_for_scope(legacy_scope, &embedding, 8, 8, 0.0);
    assert_eq!(scoped.len(), 1, "legacy id scope should be inferred");
    assert_eq!(scoped[0].0.scope_key(), legacy_scope);
}
