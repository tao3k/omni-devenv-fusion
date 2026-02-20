//! Integration tests for omni-memory engine.
//!
//! These tests verify the full memory workflow:
//! 1. Store episodes
//! 2. Update Q-values through learning
//! 3. Recall with two-phase search

mod common;

use omni_memory::{
    Episode, EpisodeStore, IntentEncoder, QTable, StoreConfig, TwoPhaseConfig, TwoPhaseSearch,
};
use std::sync::Arc;

/// Helper to create test episodes with realistic data.
fn create_test_episodes(store: &EpisodeStore) -> Vec<Episode> {
    vec![
        Episode::new(
            "ep-001".to_string(),
            "debug network timeout error".to_string(),
            store.encoder().encode("debug network timeout error"),
            "Checked DNS configuration and firewall rules".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-002".to_string(),
            "fix memory leak in cache".to_string(),
            store.encoder().encode("fix memory leak in cache"),
            "Found unbounded HashMap, replaced with LRU cache".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-003".to_string(),
            "handle async error properly".to_string(),
            store.encoder().encode("handle async error properly"),
            "Added trycatch and error boundary".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-004".to_string(),
            "optimize slow database query".to_string(),
            store.encoder().encode("optimize slow database query"),
            "Added index but query still slow".to_string(),
            "failure".to_string(),
        ),
        Episode::new(
            "ep-005".to_string(),
            "debug connection refused".to_string(),
            store.encoder().encode("debug connection refused"),
            "Service was down, restarted it".to_string(),
            "success".to_string(),
        ),
    ]
}

#[test]
fn test_full_memory_workflow() {
    // Setup
    let path = common::test_store_path("test_memory");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "episodes".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Store episodes
    let episodes = create_test_episodes(&store);
    for ep in &episodes {
        store.store(ep.clone()).unwrap();
    }

    assert_eq!(store.len(), 5);

    // Verify Q-values initialized to 0.5
    assert_eq!(store.q_table.get_q("ep-001"), 0.5);
    assert_eq!(store.q_table.get_q("ep-002"), 0.5);

    // Simulate learning: update Q-values based on outcomes
    store.update_q("ep-001", 1.0); // Success
    store.update_q("ep-002", 1.0); // Success
    store.update_q("ep-003", 0.8); // Partial success
    store.update_q("ep-004", 0.2); // Failure

    // Verify Q-values updated
    assert!(store.q_table.get_q("ep-001") > 0.5);
    assert!(store.q_table.get_q("ep-004") < 0.5);
}

#[test]
fn test_two_phase_search_workflow() {
    // Setup
    let store = EpisodeStore::new(StoreConfig::default());
    let episodes = create_test_episodes(&store);
    for ep in &episodes {
        store.store(ep.clone()).unwrap();
    }

    // Update some Q-values to test reranking
    store.update_q("ep-001", 1.0); // High Q-value
    store.update_q("ep-002", 0.5); // Medium Q-value
    store.update_q("ep-004", 0.1); // Low Q-value

    // Phase 1 only (semantic recall)
    let results = store.recall("debug network", 3);
    assert!(!results.is_empty());
    assert!(results.len() <= 3);

    // Phase 1 + Phase 2 (two-phase recall)
    let results = store.two_phase_recall("debug network", 5, 3, 0.3);
    assert!(!results.is_empty());
    assert!(results.len() <= 3);

    // Higher lambda should prioritize Q-value
    let results = store.two_phase_recall("debug network", 5, 3, 0.8);
    assert!(!results.is_empty());
}

#[test]
fn test_q_learning_convergence() {
    let q_table = QTable::with_params(0.1, 0.95);

    // Repeatedly update with reward 1.0
    // Should converge to 1.0
    for _ in 0..100 {
        q_table.update("ep-test", 1.0);
    }

    let q_value = q_table.get_q("ep-test");
    assert!(
        (q_value - 1.0).abs() < 0.01,
        "Q-value should converge to 1.0, got {}",
        q_value
    );

    // Repeatedly update with reward 0.0
    // Should converge to 0.0
    for _ in 0..100 {
        q_table.update("ep-test-2", 0.0);
    }

    let q_value = q_table.get_q("ep-test-2");
    assert!(
        (q_value - 0.0).abs() < 0.01,
        "Q-value should converge to 0.0, got {}",
        q_value
    );
}

#[test]
fn test_intent_encoder_determinism() {
    let encoder = IntentEncoder::new(128);

    let emb1 = encoder.encode("test intent query");
    let emb2 = encoder.encode("test intent query");

    assert_eq!(emb1, emb2, "Same intent should produce same embedding");

    // Verify normalized
    let norm: f32 = emb1.iter().map(|x| x * x).sum::<f32>().sqrt();
    assert!((norm - 1.0).abs() < 0.001, "Embedding should be normalized");
}

#[test]
fn test_two_phase_search_with_config() {
    let q_table = Arc::new(QTable::new());
    let encoder = Arc::new(IntentEncoder::new(128));

    let config = TwoPhaseConfig {
        k1: 10,
        k2: 3,
        lambda: 0.4,
    };
    let search = TwoPhaseSearch::new(q_table.clone(), encoder.clone(), config);

    // Create test episodes
    let episodes = vec![
        Episode::new(
            "ep-a".to_string(),
            "python async programming".to_string(),
            encoder.encode("python async programming"),
            "Used asyncio".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-b".to_string(),
            "rust async programming".to_string(),
            encoder.encode("rust async programming"),
            "Used tokio".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-c".to_string(),
            "javascript callback hell".to_string(),
            encoder.encode("javascript callback hell"),
            "Refactored to promises".to_string(),
            "failure".to_string(),
        ),
    ];

    // Test search
    let results = search.search(&episodes, "async code", None, None, None);
    assert!(!results.is_empty());

    // Test quick search
    let results = search.quick_search(&episodes, "async code");
    assert!(!results.is_empty());
}

#[test]
fn test_episode_utility_calculation() {
    let mut episode = Episode::new(
        "ep-test".to_string(),
        "test intent".to_string(),
        vec![0.1, 0.2, 0.3],
        "test experience".to_string(),
        "success".to_string(),
    );

    // Initial utility
    let initial_util = episode.utility();
    assert!(initial_util > 0.0);

    // After successes
    episode.mark_success();
    episode.mark_success();
    assert_eq!(episode.success_count, 2);

    // After failure
    episode.mark_failure();
    assert_eq!(episode.failure_count, 1);

    // Utility should reflect the success rate
    let util = episode.utility();
    assert!(util > 0.0);
}

#[test]
fn test_batch_operations() {
    let q_table = QTable::new();

    let updates = vec![
        ("ep-1".to_string(), 1.0),
        ("ep-2".to_string(), 0.8),
        ("ep-3".to_string(), 0.6),
        ("ep-4".to_string(), 0.4),
        ("ep-5".to_string(), 0.2),
    ];

    let results = q_table.update_batch(&updates);

    assert_eq!(results.len(), 5);

    // Verify all updated
    for (id, _) in &updates {
        assert!(q_table.get_q(id) > 0.0);
    }
}

#[test]
fn test_calculate_score_function() {
    use omni_memory::calculate_score;

    // Pure semantic (lambda = 0)
    let score = calculate_score(0.9, 0.5, 0.0);
    assert!((score - 0.9).abs() < 0.001);

    // Pure Q-value (lambda = 1)
    let score = calculate_score(0.9, 0.5, 1.0);
    assert!((score - 0.5).abs() < 0.001);

    // Balanced (lambda = 0.5)
    let score = calculate_score(0.9, 0.5, 0.5);
    assert!((score - 0.7).abs() < 0.001);
}

/// Regression test: Episode store persistence (save/load)
#[test]
fn test_episode_store_persistence() {
    use tempfile::TempDir;

    let temp_dir = TempDir::new().unwrap();
    let episodes_path = temp_dir.path().join("episodes.json");
    let qtable_path = temp_dir.path().join("qtable.json");

    // Create store and add episodes
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Store episodes
    let ep1 = Episode::new(
        "ep-1".to_string(),
        "debug api timeout".to_string(),
        store.encoder().encode("debug api timeout"),
        "Increased timeout".to_string(),
        "success".to_string(),
    );
    let ep2 = Episode::new(
        "ep-2".to_string(),
        "fix memory leak".to_string(),
        store.encoder().encode("fix memory leak"),
        "Replaced HashMap".to_string(),
        "success".to_string(),
    );
    let ep3 = Episode::new(
        "ep-3".to_string(),
        "optimize query".to_string(),
        store.encoder().encode("optimize query"),
        "Added index".to_string(),
        "failure".to_string(),
    );

    store.store(ep1).unwrap();
    store.store(ep2).unwrap();
    store.store(ep3).unwrap();

    // Update Q-values (returns f32, not Result)
    store.update_q("ep-1", 1.0); // Success
    store.update_q("ep-2", 1.0); // Success
    store.update_q("ep-3", 0.0); // Failure

    // Save to files
    store.save(episodes_path.to_str().unwrap()).unwrap();
    store.save_q_table(qtable_path.to_str().unwrap()).unwrap();

    // Verify files exist
    assert!(episodes_path.exists());
    assert!(qtable_path.exists());

    // Create new store and load
    let path2 = common::test_store_path("test2");
    let config2 = StoreConfig {
        path: path2.clone(),
        embedding_dim: 128,
        table_name: "test2".to_string(),
    };
    let store2 = EpisodeStore::new(config2);

    // Load from files
    store2.load(episodes_path.to_str().unwrap()).unwrap();
    store2.load_q_table(qtable_path.to_str().unwrap()).unwrap();

    // Verify loaded data
    assert_eq!(store2.len(), 3);

    // Verify Q-values loaded correctly (success -> 0.6, failure -> 0.4)
    assert!((store2.q_table.get_q("ep-1") - 0.6).abs() < 0.01);
    assert!((store2.q_table.get_q("ep-2") - 0.6).abs() < 0.01);
    assert!((store2.q_table.get_q("ep-3") - 0.4).abs() < 0.01);

    // Verify recall still works
    let results = store2.two_phase_recall("api timeout", 3, 3, 0.5);
    assert!(!results.is_empty());
}

/// Regression test: Memory decay mechanism
#[test]
fn test_memory_decay() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Store episodes
    let ep1 = Episode::new(
        "ep-1".to_string(),
        "debug api timeout".to_string(),
        store.encoder().encode("debug api timeout"),
        "Increased timeout".to_string(),
        "success".to_string(),
    );
    let ep2 = Episode::new(
        "ep-2".to_string(),
        "fix memory leak".to_string(),
        store.encoder().encode("fix memory leak"),
        "Replaced HashMap".to_string(),
        "success".to_string(),
    );

    store.store(ep1).unwrap();
    store.store(ep2).unwrap();

    // Update Q-values to extremes
    store.update_q("ep-1", 1.0); // High Q
    store.update_q("ep-2", 0.0); // Low Q

    // Verify initial Q-values
    let q1_before = store.q_table.get_q("ep-1");
    let q2_before = store.q_table.get_q("ep-2");
    assert!(
        (q1_before - 0.6).abs() < 0.01,
        "Expected q1=0.6, got {}",
        q1_before
    );
    assert!(
        (q2_before - 0.4).abs() < 0.01,
        "Expected q2=0.4, got {}",
        q2_before
    );

    // Apply decay (0.5 = strong decay for testing)
    // With age_hours ~ 0, it applies decay_factor directly
    // Q_decay = 0.5 + (Q - 0.5) * decay_factor
    // For Q=0.6: 0.5 + (0.6-0.5)*0.5 = 0.5 + 0.05 = 0.55
    store.apply_decay(0.5);

    // Q-values should move towards 0.5
    let q1_after = store.q_table.get_q("ep-1");
    let q2_after = store.q_table.get_q("ep-2");

    // High Q should decrease (0.6 -> 0.55)
    assert!(
        q1_after < q1_before,
        "Expected q1 {} < {}",
        q1_after,
        q1_before
    );
    assert!(q1_after > 0.5, "Expected q1 > 0.5, got {}", q1_after);

    // Low Q should increase (0.4 -> 0.45)
    assert!(
        q2_after > q2_before,
        "Expected q2 {} > {}",
        q2_after,
        q2_before
    );
    assert!(q2_after < 0.5, "Expected q2 < 0.5, got {}", q2_after);

    // Apply decay again (now Q is 0.55)
    // Q_decay = 0.5 + (0.55-0.5)*0.5 = 0.5 + 0.025 = 0.525
    store.apply_decay(0.5);
    let q1_final = store.q_table.get_q("ep-1");

    // Should be even closer to 0.5 (but not cross it for high Q)
    assert!(
        q1_final > 0.5 && q1_final < q1_before,
        "Expected 0.5 < q1_final {} < q1_before {}",
        q1_final,
        q1_before
    );
}

/// Regression test: Memory stats
#[test]
fn test_memory_stats() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Empty store stats
    let stats = store.stats();
    assert_eq!(stats.total_episodes, 0);
    assert_eq!(stats.q_table_size, 0);

    // Add episodes
    let ep1 = Episode::new(
        "ep-1".to_string(),
        "debug api timeout".to_string(),
        store.encoder().encode("debug api timeout"),
        "Increased timeout".to_string(),
        "success".to_string(),
    );
    store.store(ep1).unwrap();

    let stats = store.stats();
    assert_eq!(stats.total_episodes, 1);
    assert_eq!(stats.q_table_size, 1);
}

/// Regression test: Incremental learning - update episode
#[test]
fn test_incremental_update_episode() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Add episode
    let ep = Episode::new(
        "ep-1".to_string(),
        "debug api".to_string(),
        store.encoder().encode("debug api"),
        "Solution v1".to_string(),
        "failure".to_string(),
    );
    store.store(ep).unwrap();

    // Verify initial state
    let retrieved = store.get("ep-1").unwrap();
    assert_eq!(retrieved.experience, "Solution v1");
    assert_eq!(retrieved.outcome, "failure");

    // Update episode
    let updated = store.update_episode("ep-1", "Solution v2 - fixed", "success");
    assert!(updated, "Update should return true");

    // Verify updated state
    let retrieved = store.get("ep-1").unwrap();
    assert_eq!(retrieved.experience, "Solution v2 - fixed");
    assert_eq!(retrieved.outcome, "success");
}

/// Regression test: Incremental learning - delete episode
#[test]
fn test_incremental_delete_episode() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Add episodes
    let ep1 = Episode::new(
        "ep-1".to_string(),
        "debug api".to_string(),
        store.encoder().encode("debug api"),
        "Solution".to_string(),
        "success".to_string(),
    );
    let ep2 = Episode::new(
        "ep-2".to_string(),
        "fix memory".to_string(),
        store.encoder().encode("fix memory"),
        "Solution".to_string(),
        "success".to_string(),
    );
    store.store(ep1).unwrap();
    store.store(ep2).unwrap();

    assert_eq!(store.len(), 2);

    // Delete one episode
    let deleted = store.delete_episode("ep-1");
    assert!(deleted, "Delete should return true");

    assert_eq!(store.len(), 1);
    assert!(store.get("ep-1").is_none(), "ep-1 should be deleted");
    assert!(store.get("ep-2").is_some(), "ep-2 should still exist");

    // Verify Q-table also updated
    assert_eq!(
        store.q_table.get_q("ep-1"),
        0.5,
        "Deleted ep should have default Q"
    );
    assert_eq!(
        store.q_table.get_q("ep-2"),
        0.5,
        "Remaining ep should have Q"
    );
}

/// Regression test: Incremental learning - mark accessed
#[test]
fn test_incremental_mark_accessed() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Add episode
    let ep = Episode::new(
        "ep-1".to_string(),
        "debug api".to_string(),
        store.encoder().encode("debug api"),
        "Solution".to_string(),
        "success".to_string(),
    );
    store.store(ep).unwrap();

    // Verify initial state
    let retrieved = store.get("ep-1").unwrap();
    assert_eq!(retrieved.success_count, 0);

    // Mark as accessed multiple times
    store.mark_accessed("ep-1");
    store.mark_accessed("ep-1");
    store.mark_accessed("ep-1");

    // Verify access count
    let retrieved = store.get("ep-1").unwrap();
    assert_eq!(retrieved.success_count, 3, "Should have 3 access counts");
}

/// Regression test: Multi-hop reasoning
#[test]
fn test_multi_hop_recall() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);

    // Store diverse episodes
    let episodes = vec![
        ("debug api timeout", "Increased timeout to 60s", "success"),
        ("debug database slow", "Added index on column", "success"),
        ("debug memory leak", "Replaced HashMap with LRU", "success"),
        ("debug network error", "Checked DNS settings", "success"),
        ("debug file upload", "Increased size limit", "success"),
    ];

    for (i, (intent, exp, outcome)) in episodes.iter().enumerate() {
        let ep = Episode::new(
            format!("ep-{}", i),
            intent.to_string(),
            store.encoder().encode(intent),
            exp.to_string(),
            outcome.to_string(),
        );
        store.store(ep).unwrap();
    }

    // Single hop: "database problem"
    let single_hop = store.multi_hop_recall(&["database problem".to_string()], 3, 0.5);
    assert!(!single_hop.is_empty(), "Should have results for single hop");

    // Multi-hop: "database" -> "performance"
    let multi_hop = store.multi_hop_recall(
        &[
            "database problem".to_string(),
            "performance optimization".to_string(),
        ],
        3,
        0.5,
    );
    assert!(!multi_hop.is_empty(), "Should have results for multi-hop");

    // Multi-hop should return results (may be different from single hop due to chaining)
    println!("Single hop results: {:?}", single_hop.len());
    println!("Multi-hop results: {:?}", multi_hop.len());
}

/// Regression test: Multi-hop with embeddings
#[test]
fn test_multi_hop_recall_with_embeddings() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // Store episodes
    let episodes = vec![
        ("debug api timeout", "Increased timeout"),
        ("debug database slow", "Added index"),
        ("fix performance issue", "Used caching"),
    ];

    for (i, (intent, exp)) in episodes.iter().enumerate() {
        let ep = Episode::new(
            format!("ep-{}", i),
            intent.to_string(),
            encoder.encode(intent),
            exp.to_string(),
            "success".to_string(),
        );
        store.store(ep).unwrap();
    }

    // Multi-hop with embeddings
    let embeddings = vec![
        encoder.encode("api problem"),
        encoder.encode("timeout issue"),
    ];

    let results = store.multi_hop_recall_with_embeddings(&embeddings, 3, 0.5);
    assert!(!results.is_empty(), "Should have results");
}

// Note: LanceDB persistence test removed due to API changes in newer LanceDB versions.
// Use JSON persistence tests instead (test_episode_store_persistence).
