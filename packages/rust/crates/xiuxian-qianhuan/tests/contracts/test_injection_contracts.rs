use std::hash::{Hash, Hasher};

use xiuxian_qianhuan::{
    InjectionMode, InjectionPolicy, InjectionSnapshot, PromptContextBlock, PromptContextCategory,
    PromptContextSource,
};

#[test]
fn prompt_context_block_computes_payload_chars() {
    let block = PromptContextBlock::new(
        "blk-1",
        PromptContextSource::MemoryRecall,
        PromptContextCategory::MemoryRecall,
        90,
        "telegram:100:200",
        "alpha beta",
        false,
    );

    assert_eq!(block.payload_chars, 10);
    assert_eq!(block.block_id, "blk-1");
    assert_eq!(block.priority, 90);
}

#[test]
fn injection_policy_roundtrip_keeps_snake_case_mode() {
    let policy = InjectionPolicy {
        mode: InjectionMode::Hybrid,
        ..InjectionPolicy::default()
    };

    let raw = serde_json::to_value(&policy).unwrap_or_else(|error| {
        panic!("failed to serialize policy: {error}");
    });

    assert_eq!(raw["mode"], "hybrid");

    let decoded: InjectionPolicy = serde_json::from_value(raw).unwrap_or_else(|error| {
        panic!("failed to deserialize policy: {error}");
    });
    assert_eq!(decoded.mode, InjectionMode::Hybrid);
}

#[test]
fn injection_snapshot_validate_rejects_budget_violation() {
    let block = PromptContextBlock::new(
        "blk-2",
        PromptContextSource::Knowledge,
        PromptContextCategory::Knowledge,
        80,
        "telegram:100:200",
        "x".repeat(64),
        false,
    );
    let policy = InjectionPolicy {
        max_chars: 32,
        ..InjectionPolicy::default()
    };
    let snapshot =
        InjectionSnapshot::from_blocks("snap-1", "telegram:100:200", 7, policy, None, vec![block]);

    let error = snapshot
        .validate()
        .expect_err("expected max_chars validation failure");
    assert!(error.contains("max_chars"));
}

#[test]
fn injection_snapshot_roundtrip_is_stable() {
    let block = PromptContextBlock::new(
        "blk-3",
        PromptContextSource::SessionXml,
        PromptContextCategory::SessionXml,
        70,
        "telegram:group-1:user-9",
        "<qa><q>q</q><a>a</a></qa>",
        true,
    );
    let snapshot = InjectionSnapshot::from_blocks(
        "snap-2",
        "telegram:group-1:user-9",
        42,
        InjectionPolicy::default(),
        None,
        vec![block],
    );
    snapshot.validate().expect("snapshot should be valid");

    let raw = serde_json::to_string(&snapshot).unwrap_or_else(|error| {
        panic!("failed to serialize snapshot: {error}");
    });
    let decoded: InjectionSnapshot = serde_json::from_str(&raw).unwrap_or_else(|error| {
        panic!("failed to deserialize snapshot: {error}");
    });

    assert_eq!(decoded.snapshot_id, "snap-2");
    assert_eq!(decoded.turn_id, 42);
    assert_eq!(decoded.blocks.len(), 1);
    assert_eq!(
        decoded.blocks[0].category,
        PromptContextCategory::SessionXml
    );
}

#[test]
fn injection_snapshot_content_hash_is_stable_across_turn_loop() {
    let policy = InjectionPolicy {
        mode: InjectionMode::Classified,
        ..InjectionPolicy::default()
    };
    let blocks = vec![
        PromptContextBlock::new(
            "blk-memory",
            PromptContextSource::MemoryRecall,
            PromptContextCategory::MemoryRecall,
            910,
            "telegram:scope-a",
            "memory recall context",
            false,
        ),
        PromptContextBlock::new(
            "blk-policy",
            PromptContextSource::Policy,
            PromptContextCategory::Policy,
            950,
            "telegram:scope-a",
            "do not bypass verification gates",
            true,
        ),
    ];

    let snapshot_turn_1 = InjectionSnapshot::from_blocks(
        "snap-turn-1",
        "telegram:scope-a",
        1,
        policy.clone(),
        None,
        blocks.clone(),
    );
    let snapshot_turn_2 =
        InjectionSnapshot::from_blocks("snap-turn-2", "telegram:scope-a", 2, policy, None, blocks);
    snapshot_turn_1
        .validate()
        .expect("turn 1 snapshot must be valid");
    snapshot_turn_2
        .validate()
        .expect("turn 2 snapshot must be valid");

    let hash_1 = snapshot_content_hash(&snapshot_turn_1);
    let hash_2 = snapshot_content_hash(&snapshot_turn_2);
    assert_eq!(
        hash_1, hash_2,
        "content hash should remain stable across turns for identical snapshot payload"
    );
}

fn snapshot_content_hash(snapshot: &InjectionSnapshot) -> u64 {
    let canonical = serde_json::json!({
        "policy": &snapshot.policy,
        "role_mix": &snapshot.role_mix,
        "blocks": &snapshot.blocks,
        "total_chars": snapshot.total_chars,
        "dropped_block_ids": &snapshot.dropped_block_ids,
        "truncated_block_ids": &snapshot.truncated_block_ids,
    });
    let encoded = serde_json::to_string(&canonical).unwrap_or_else(|error| {
        panic!("failed to serialize canonical snapshot payload: {error}");
    });
    let mut hasher = std::collections::hash_map::DefaultHasher::new();
    encoded.hash(&mut hasher);
    hasher.finish()
}
