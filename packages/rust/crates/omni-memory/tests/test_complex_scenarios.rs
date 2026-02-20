//! Complex Scenario Tests for Omni-Memory
//!
//! These tests validate the MemRL paper claims:
//! 1. Self-evolution via RL on episodic memory
//! 2. Two-phase retrieval (semantic + utility)
//! 3. Environmental feedback (reward signal)
//! 4. Noise reduction through utility filtering
//! 5. Memory decay for stale episodes
//! 6. Multi-hop reasoning
//! 7. Q-learning convergence

mod common;

use omni_memory::{Episode, EpisodeStore, StoreConfig};

/// Test 1: Self-Evolution via Feedback
///
/// Validates: "Agents can self-evolve at runtime by doing reinforcement learning
/// on episodic memory, without updating model weights."
///
/// Scenario: System learns from multiple success/failure experiences and adapts
#[test]
fn test_self_evolution_from_feedback() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // Store initial experience (no Q-value knowledge)
    let ep1 = Episode::new(
        "ep-1".to_string(),
        "fix network timeout".to_string(),
        encoder.encode("fix network timeout"),
        "Increased timeout to 30s".to_string(),
        "success".to_string(),
    );
    store.store(ep1.clone()).unwrap();

    // Initial Q-value should be 0.5 (default)
    let initial_q = store.q_table.get_q("ep-1");
    assert!(
        (initial_q - 0.5).abs() < 0.01,
        "Initial Q-value should be 0.5"
    );

    // Mark as success → Q-value should increase
    store.update_q("ep-1", 1.0);
    let after_success_q = store.q_table.get_q("ep-1");
    assert!(
        after_success_q > 0.5,
        "Q-value should increase after success"
    );

    // Store another experience
    let ep2 = Episode::new(
        "ep-2".to_string(),
        "debug api crash".to_string(),
        encoder.encode("debug api crash"),
        "Restarted service".to_string(),
        "failure".to_string(),
    );
    store.store(ep2).unwrap();

    // Mark as failure → Q-value should decrease
    store.update_q("ep-2", 0.0);
    let after_failure_q = store.q_table.get_q("ep-2");
    assert!(
        after_failure_q < 0.5,
        "Q-value should decrease after failure"
    );

    println!("✓ Self-evolution: Q-values adapted based on feedback");
    println!("  - Success episode Q: {} → {}", initial_q, after_success_q);
    println!("  - Failure episode Q: {} → {}", 0.5, after_failure_q);
}

/// Test 2: Two-Phase Retrieval Noise Reduction
///
/// Validates: "Two-phase retrieval filters noise and identifies high-utility
/// strategies using environmental feedback."
///
/// Scenario: Multiple similar episodes with different outcomes - two-phase should
/// prioritize high utility ones
#[test]
fn test_two_phase_noise_reduction() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // Store multiple similar experiences with different outcomes
    let intents = vec![
        ("fix database connection", "Restarted DB", "success"),
        (
            "fix database connection",
            "Changed connection string",
            "success",
        ),
        ("fix database connection", "Increased pool size", "success"),
        ("fix database connection", "Reinstalled driver", "failure"),
        ("fix database connection", "Cleared cache", "failure"),
        ("fix database connection", "Rebooted server", "failure"),
    ];

    for (i, (intent, exp, outcome)) in intents.iter().enumerate() {
        let ep = Episode::new(
            format!("ep-{}", i),
            intent.to_string(),
            encoder.encode(intent),
            exp.to_string(),
            outcome.to_string(),
        );
        store.store(ep).unwrap();
    }

    // Mark successes as high utility, failures as low
    for i in 0..3 {
        store.update_q(&format!("ep-{}", i), 1.0); // Success
    }
    for i in 3..6 {
        store.update_q(&format!("ep-{}", i), 0.0); // Failure
    }

    // Phase 1: Pure semantic recall (all similar)
    let query_emb = encoder.encode("database connection error");
    let phase1 = store.recall_with_embedding(&query_emb, 10);

    // Phase 2: Two-phase with Q-value reranking
    let phase2 = store.two_phase_recall_with_embedding(&query_emb, 10, 3, 0.5);

    // Two-phase should return more successful experiences
    let phase2_successes: usize = phase2.iter().filter(|(ep, _)| ep.q_value > 0.5).count();

    println!("✓ Two-phase noise reduction:");
    println!("  - Phase 1 (semantic): {} results", phase1.len());
    println!("  - Phase 2 (with Q-rerank): {} results", phase2.len());
    println!("  - High-utility in top-3: {}/3", phase2_successes);

    // Two-phase should prioritize successful experiences
    assert!(
        phase2_successes >= 2,
        "Two-phase should return mostly successful experiences"
    );
}

/// Test 3: Memory Decay (Q-Value Decay)
///
/// Validates: Memory should decay Q-values over time (not delete episodes)
/// (Our enhancement, not in original MemRL paper)
///
/// Scenario: Q-values should decay towards 0.5 over time
#[test]
fn test_memory_decay_scenario() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // Store episode with high Q-value
    let ep1 = Episode::new(
        "fresh-high".to_string(),
        "recent success".to_string(),
        encoder.encode("recent success"),
        "Did X".to_string(),
        "success".to_string(),
    );
    store.store(ep1).unwrap();
    store.update_q("fresh-high", 0.9);

    // Store another episode with low Q-value
    let ep2 = Episode::new(
        "old-low".to_string(),
        "old failure".to_string(),
        encoder.encode("old failure"),
        "Did Y".to_string(),
        "failure".to_string(),
    );
    store.store(ep2).unwrap();
    store.update_q("old-low", 0.1);

    // Get Q-values before decay
    let q_before = store.q_table.get_q("fresh-high");
    let q_before_low = store.q_table.get_q("old-low");

    // Apply decay factor (simulating time passing)
    store.apply_decay(0.5);

    // Get Q-values after decay
    let q_after = store.q_table.get_q("fresh-high");
    let q_after_low = store.q_table.get_q("old-low");

    println!("✓ Memory decay (Q-value decay towards 0.5):");
    println!(
        "  - High Q before: {:.3} -> after: {:.3}",
        q_before, q_after
    );
    println!(
        "  - Low Q before: {:.3} -> after: {:.3}",
        q_before_low, q_after_low
    );

    // High Q should move towards 0.5
    assert!(q_after < q_before, "High Q should decay towards 0.5");
    // Low Q should move towards 0.5
    assert!(q_after_low > q_before_low, "Low Q should decay towards 0.5");
}

/// Test 4: Multi-hop Reasoning
///
/// Validates: Can chain multiple queries for complex reasoning
/// (Our enhancement, not in original MemRL paper)
///
/// Scenario: Query chain: "api error" → "timeout fix" → "network issue"
#[test]
fn test_multi_hop_reasoning_scenario() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // Store chain of related experiences
    let chain = vec![
        ("api error", "Checked logs", "success", 0.8),
        ("timeout fix", "Increased timeout", "success", 0.9),
        ("network issue", "Checked firewall", "success", 0.7),
        ("unrelated task", "Random fix", "failure", 0.2),
    ];

    for (i, (intent, exp, outcome, q)) in chain.iter().enumerate() {
        let ep = Episode::new(
            format!("ep-{}", i),
            intent.to_string(),
            encoder.encode(intent),
            exp.to_string(),
            outcome.to_string(),
        );
        store.store(ep).unwrap();
        store.update_q(&format!("ep-{}", i), *q);
    }

    // Multi-hop: chain queries
    let queries = vec![
        encoder.encode("api error"),
        encoder.encode("timeout fix"),
        encoder.encode("network issue"),
    ];

    let results = store.multi_hop_recall_with_embeddings(&queries, 3, 0.3);

    println!("✓ Multi-hop reasoning:");
    println!("  - Query chain: api error → timeout fix → network issue");
    println!("  - Results: {} episodes", results.len());

    // Should find related experiences
    assert!(
        !results.is_empty(),
        "Multi-hop should find related experiences"
    );
}

/// Test 5: Q-Learning Convergence
///
/// Validates: Q-values should converge towards true utility over many updates
///
/// Scenario: Repeatedly update Q-value with same reward, should converge
#[test]
fn test_q_learning_convergence_scenario() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    let ep = Episode::new(
        "converge-test".to_string(),
        "test task".to_string(),
        encoder.encode("test task"),
        "Did X".to_string(),
        "success".to_string(),
    );
    store.store(ep).unwrap();

    // Update Q-value many times with reward = 1.0 (QTable uses default learning rate)
    let _learning_rate = 0.2;
    let mut q_values = vec![0.5];

    for _ in 0..20 {
        store.update_q("converge-test", 1.0);
        let q = store.q_table.get_q("converge-test");
        q_values.push(q);
    }

    let final_q = *q_values.last().unwrap();

    println!("✓ Q-learning convergence:");
    println!("  - Initial Q: 0.5");
    println!("  - After 20 success updates: {:.4}", final_q);
    println!("  - Converged towards 1.0: {}", final_q > 0.9);

    // Should converge towards 1.0
    assert!(
        final_q > 0.9,
        "Q-value should converge towards reward (1.0)"
    );
}

/// Test 6: Conflicting Experiences
///
/// Validates: System should handle conflicting experiences (same intent,
/// different outcomes) by using Q-values to distinguish
///
/// Scenario: Same intent "fix bug" with success and failure outcomes
#[test]
fn test_conflicting_experiences() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();
    let intent = "fix critical bug";

    // Store conflicting experiences
    let ep1 = Episode::new(
        "fix-1".to_string(),
        intent.to_string(),
        encoder.encode(intent),
        "Solution A worked".to_string(),
        "success".to_string(),
    );
    let ep2 = Episode::new(
        "fix-2".to_string(),
        intent.to_string(),
        encoder.encode(intent),
        "Solution B failed".to_string(),
        "failure".to_string(),
    );
    let ep3 = Episode::new(
        "fix-3".to_string(),
        intent.to_string(),
        encoder.encode(intent),
        "Solution C worked better".to_string(),
        "success".to_string(),
    );

    store.store(ep1).unwrap();
    store.store(ep2).unwrap();
    store.store(ep3).unwrap();

    // Update Q-values using rewards (not direct Q-values)
    // Q_new = Q_old + α * (reward - Q_old)
    // With α=0.2: reward 1.0 → Q≈0.6, reward 0.0 → Q≈0.4
    store.update_q("fix-1", 1.0); // Success → higher Q
    store.update_q("fix-2", 0.0); // Failure → lower Q
    store.update_q("fix-3", 1.0); // Success → higher Q

    // Two-phase should prefer high Q-value experiences
    // Use higher q_weight to emphasize Q-value
    let query_emb = encoder.encode(intent);
    let results = store.two_phase_recall_with_embedding(&query_emb, 3, 3, 0.8);

    // The two_phase_recall updates episode.q_value from Q-table
    // So results[0].0.q_value should reflect the Q-table value
    let top_episode_q = results[0].0.q_value;

    println!("✓ Conflicting experiences handling:");
    println!("  - Stored 3 experiences for same intent");
    println!("  - Updated with rewards: fix-1=1.0, fix-2=0.0, fix-3=1.0");
    println!(
        "  - Two-phase top result: {} with q_value={:.2}",
        results[0].0.id, top_episode_q
    );

    // With high q_weight (0.8), should prefer highest Q-value
    // Success rewards should give higher Q (~0.6) than failure (~0.4)
    assert!(
        top_episode_q >= 0.5,
        "Should prefer successful experience, got {}",
        top_episode_q
    );
}

/// Test 7: Utility vs Similarity Trade-off
///
/// Validates: λ (q_weight) parameter controls utility vs similarity trade-off
///
/// Scenario: Test λ=0 (similarity only) vs λ=1 (Q only) vs λ=0.5 (balanced)
#[test]
fn test_utility_similarity_tradeoff() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // High similarity, low Q (old failure)
    let ep1 = Episode::new(
        "high-sim-low-q".to_string(),
        "debug api timeout".to_string(),
        encoder.encode("debug api timeout"),
        "Old failed fix".to_string(),
        "failure".to_string(),
    );

    // Low similarity, high Q (recent success)
    let ep2 = Episode::new(
        "low-sim-high-q".to_string(),
        "fix database connection pool".to_string(),
        encoder.encode("fix database connection pool"),
        "New successful fix".to_string(),
        "success".to_string(),
    );

    store.store(ep1).unwrap();
    store.store(ep2).unwrap();
    store.update_q("high-sim-low-q", 0.1);
    store.update_q("low-sim-high-q", 0.95);

    let query = encoder.encode("api timeout error");

    // λ = 0: Similarity only
    let results_lambda_0 = store.two_phase_recall_with_embedding(&query, 2, 2, 0.0);

    // λ = 1: Q only
    let results_lambda_1 = store.two_phase_recall_with_embedding(&query, 2, 2, 1.0);

    // λ = 0.5: Balanced
    let results_lambda_5 = store.two_phase_recall_with_embedding(&query, 2, 2, 0.5);

    println!("✓ Utility vs Similarity trade-off:");
    println!(
        "  - λ=0 (similarity only): {:?}",
        results_lambda_0
            .iter()
            .map(|(e, _)| e.id.as_str())
            .collect::<Vec<_>>()
    );
    println!(
        "  - λ=0.5 (balanced): {:?}",
        results_lambda_5
            .iter()
            .map(|(e, _)| e.id.as_str())
            .collect::<Vec<_>>()
    );
    println!(
        "  - λ=1 (Q only): {:?}",
        results_lambda_1
            .iter()
            .map(|(e, _)| e.id.as_str())
            .collect::<Vec<_>>()
    );

    // λ=0 should prefer high-similarity
    assert_eq!(
        results_lambda_0[0].0.id, "high-sim-low-q",
        "λ=0 should prefer similarity"
    );

    // λ=1 should prefer high-Q
    assert_eq!(
        results_lambda_1[0].0.id, "low-sim-high-q",
        "λ=1 should prefer Q-value"
    );
}

/// Test 8: Persistence and Recovery
///
/// Validates: Episodes and Q-values persist across restarts
#[test]
fn test_persistence_and_recovery() {
    use tempfile::TempDir;

    let temp_dir = TempDir::new().unwrap();
    let store_path = temp_dir.path().join("store.json");
    let q_path = temp_dir.path().join("qtable.json");

    // Create store and add episodes
    {
        let path = common::test_store_path("test");
        let config = StoreConfig {
            path: path.clone(),
            embedding_dim: 128,
            table_name: "test".to_string(),
        };
        let store = EpisodeStore::new(config);

        let ep = Episode::new(
            "persist-1".to_string(),
            "important task".to_string(),
            store.encoder().encode("important task"),
            "Critical fix".to_string(),
            "success".to_string(),
        );
        store.store(ep).unwrap();

        // Update Q-value multiple times to ensure it's in the table
        store.update_q("persist-1", 1.0);
        store.update_q("persist-1", 0.85);

        // Save
        store.save(store_path.to_str().unwrap()).unwrap();
        store.save_q_table(q_path.to_str().unwrap()).unwrap();

        // Verify saved Q-value
        let saved_q = store.q_table.get_q("persist-1");
        println!("  Saved Q-value: {:.2}", saved_q);
    }

    // Load into new store
    {
        let path = common::test_store_path("test");
        let config = StoreConfig {
            path: path.clone(),
            embedding_dim: 128,
            table_name: "test".to_string(),
        };
        let store = EpisodeStore::new(config);

        store.load(store_path.to_str().unwrap()).unwrap();
        store.load_q_table(q_path.to_str().unwrap()).unwrap();

        // Verify
        assert_eq!(store.len(), 1, "Should have 1 episode");

        // First verify the episode was loaded
        let loaded_ep = store.get("persist-1").expect("Episode should exist");
        println!("  Loaded episode Q-value: {:.2}", loaded_ep.q_value);

        // Then verify Q-table was loaded
        let q = store.q_table.get_q("persist-1");
        println!("  Loaded Q-table value: {:.2}", q);

        // With Q-learning, final value after two updates (1.0 then 0.85)
        // Q1 = 0.5 + 0.2 * (1.0 - 0.5) = 0.6
        // Q2 = 0.6 + 0.2 * (0.85 - 0.6) = 0.65
        assert!((q - 0.65).abs() < 0.1, "Q-value should persist");

        println!("✓ Persistence and recovery: Episode and Q-value persisted correctly");
    }
}

/// Test 9: Batch Operations Performance
///
/// Validates: System handles large batch of episodes efficiently
#[test]
fn test_batch_operations_performance() {
    use std::time::Instant;

    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    let start = Instant::now();

    // Store 1000 episodes
    for i in 0..1000 {
        let ep = Episode::new(
            format!("batch-{}", i),
            format!("task {}", i % 100), // 100 unique intents
            encoder.encode(&format!("task {}", i % 100)),
            format!("Solution {}", i),
            if i % 3 == 0 { "failure" } else { "success" }.to_string(),
        );
        store.store(ep).unwrap();
    }

    let store_time = start.elapsed();

    // Query
    let query = encoder.encode("task 50");
    let recall_start = Instant::now();
    let results = store.recall_with_embedding(&query, 10);
    let recall_time = recall_start.elapsed();

    println!("✓ Batch operations performance:");
    println!("  - Store 1000 episodes: {:?}", store_time);
    println!("  - Recall top-10: {:?}", recall_time);
    println!("  - Results: {} episodes", results.len());

    // Should be reasonably fast
    assert!(store_time.as_millis() < 1000, "Store should be fast");
    assert!(recall_time.as_millis() < 100, "Recall should be fast");
}

/// Test 10: Incremental Learning
///
/// Validates: System can update episodes incrementally without full rebuild
#[test]
fn test_incremental_learning() {
    let path = common::test_store_path("test");
    let config = StoreConfig {
        path: path.clone(),
        embedding_dim: 128,
        table_name: "test".to_string(),
    };
    let store = EpisodeStore::new(config);
    let encoder = store.encoder();

    // Initial episode
    let ep = Episode::new(
        "learn-1".to_string(),
        "initial approach".to_string(),
        encoder.encode("initial approach"),
        "Initial solution".to_string(),
        "success".to_string(),
    );
    store.store(ep).unwrap();
    store.update_q("learn-1", 0.6);

    // First improvement (experience and outcome only, Q updates separately)
    store.update_episode("learn-1", "improved approach", "success");

    // Check update - experience should be updated
    let retrieved = store.get("learn-1").unwrap();
    assert_eq!(
        retrieved.experience, "improved approach",
        "Experience should be updated"
    );
    // Q-value should still be what we set before (0.6)
    assert!(
        (retrieved.q_value - 0.6).abs() < 0.1,
        "Q-value should remain unchanged"
    );

    // Mark as accessed (for adaptive decay)
    store.mark_accessed("learn-1");

    // Delete outdated
    let ep_old = Episode::new(
        "old-1".to_string(),
        "deprecated".to_string(),
        encoder.encode("deprecated"),
        "Old".to_string(),
        "failure".to_string(),
    );
    store.store(ep_old).unwrap();
    store.delete_episode("old-1");

    assert!(
        store.get("old-1").is_none(),
        "Deleted episode should be gone"
    );

    println!("✓ Incremental learning: Update and delete work correctly");
}
