use xiuxian_qianhuan::{
    InjectionMode, InjectionOrderStrategy, InjectionPolicy, PromptContextBlock,
    PromptContextCategory, PromptContextSource,
};

use super::assembler::assemble_snapshot;

fn make_block(
    id: &str,
    source: PromptContextSource,
    category: PromptContextCategory,
    priority: u16,
    payload: &str,
) -> PromptContextBlock {
    PromptContextBlock::new(
        id.to_string(),
        source,
        category,
        priority,
        "telegram:test:1",
        payload.to_string(),
        false,
    )
}

#[test]
fn anchor_categories_survive_block_and_char_budget_pressure() {
    let policy = InjectionPolicy {
        mode: InjectionMode::Classified,
        max_blocks: 3,
        max_chars: 8,
        ordering: InjectionOrderStrategy::PriorityDesc,
        ..InjectionPolicy::default()
    };

    let blocks = vec![
        make_block(
            "non-anchor-memory",
            PromptContextSource::MemoryRecall,
            PromptContextCategory::MemoryRecall,
            990,
            "MMMMMMMMMMMMMMMMMMMM",
        ),
        make_block(
            "anchor-safety",
            PromptContextSource::Policy,
            PromptContextCategory::Safety,
            120,
            "SAFE",
        ),
        make_block(
            "anchor-policy",
            PromptContextSource::Policy,
            PromptContextCategory::Policy,
            110,
            "RULE",
        ),
    ];

    let snapshot = assemble_snapshot("telegram:test:1", 1, policy, blocks);
    snapshot
        .validate()
        .expect("snapshot should satisfy policy after assembly");

    let kept_ids = snapshot
        .blocks
        .iter()
        .map(|block| block.block_id.as_str())
        .collect::<Vec<_>>();
    assert!(
        kept_ids.contains(&"anchor-safety"),
        "safety anchor should remain after truncation pressure"
    );
    assert!(
        kept_ids.contains(&"anchor-policy"),
        "policy anchor should remain after truncation pressure"
    );
    assert!(
        snapshot
            .dropped_block_ids
            .iter()
            .any(|id| id == "non-anchor-memory"),
        "non-anchor block should be dropped before anchor blocks"
    );
}

#[test]
fn role_mix_profile_attaches_for_multi_domain_snapshot() {
    let policy = InjectionPolicy {
        mode: InjectionMode::Classified,
        ..InjectionPolicy::default()
    };
    let blocks = vec![
        make_block(
            "memory",
            PromptContextSource::MemoryRecall,
            PromptContextCategory::MemoryRecall,
            900,
            "recent memory episode",
        ),
        make_block(
            "knowledge",
            PromptContextSource::Knowledge,
            PromptContextCategory::Knowledge,
            850,
            "durable knowledge excerpt",
        ),
    ];

    let snapshot = assemble_snapshot("telegram:test:2", 9, policy, blocks);
    let role_mix = snapshot
        .role_mix
        .expect("multi-domain snapshot should include role mix profile");
    assert_eq!(role_mix.profile_id, "role_mix.hybrid.v1");
    assert!(
        role_mix
            .roles
            .iter()
            .any(|role| role.role == "memory_strategist")
    );
    assert!(
        role_mix
            .roles
            .iter()
            .any(|role| role.role == "knowledge_synthesizer")
    );
}

#[test]
fn role_mix_is_not_attached_for_single_domain_non_hybrid_policy() {
    let policy = InjectionPolicy {
        mode: InjectionMode::Classified,
        ..InjectionPolicy::default()
    };
    let blocks = vec![make_block(
        "memory-only",
        PromptContextSource::MemoryRecall,
        PromptContextCategory::MemoryRecall,
        900,
        "single domain memory context",
    )];

    let snapshot = assemble_snapshot("telegram:test:3", 10, policy, blocks);
    assert!(
        snapshot.role_mix.is_none(),
        "single-domain classified snapshot should not attach role-mix profile"
    );
}
