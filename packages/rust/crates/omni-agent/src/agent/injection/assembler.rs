use std::collections::HashSet;

use xiuxian_qianhuan::{
    InjectionOrderStrategy, InjectionPolicy, InjectionSnapshot, PromptContextBlock,
    PromptContextCategory, RoleMixProfile, RoleMixRole,
};

pub(super) fn assemble_snapshot(
    session_id: &str,
    turn_id: u64,
    policy: InjectionPolicy,
    blocks: Vec<PromptContextBlock>,
) -> InjectionSnapshot {
    let mut dropped_block_ids = Vec::new();

    let mut selected = blocks
        .into_iter()
        .filter_map(|mut block| {
            if !policy.enabled_categories.contains(&block.category) {
                dropped_block_ids.push(block.block_id);
                return None;
            }
            block.anchor = block.anchor || policy.anchor_categories.contains(&block.category);
            Some(block)
        })
        .collect::<Vec<_>>();

    sort_blocks(&mut selected, &policy);
    let role_mix = select_role_mix(&policy, &selected);

    let mut retained = Vec::new();
    for block in selected {
        if retained.len() < policy.max_blocks {
            retained.push(block);
            continue;
        }

        if block.anchor
            && let Some(replace_index) = retained.iter().rposition(|existing| !existing.anchor)
        {
            let evicted = std::mem::replace(&mut retained[replace_index], block);
            dropped_block_ids.push(evicted.block_id);
            continue;
        }

        dropped_block_ids.push(block.block_id);
    }

    let (final_blocks, mut budget_dropped, truncated_block_ids) =
        apply_char_budget(prioritize_anchors(retained), policy.max_chars);
    dropped_block_ids.append(&mut budget_dropped);

    let mut snapshot = InjectionSnapshot::from_blocks(
        format!("injection:{session_id}:{turn_id}"),
        session_id,
        turn_id,
        policy,
        role_mix,
        final_blocks,
    );
    snapshot.dropped_block_ids = dedup_preserve_order(dropped_block_ids);
    snapshot.truncated_block_ids = dedup_preserve_order(truncated_block_ids);
    snapshot
}

fn sort_blocks(blocks: &mut [PromptContextBlock], policy: &InjectionPolicy) {
    match policy.ordering {
        InjectionOrderStrategy::PriorityDesc => {
            blocks.sort_by(|left, right| {
                right
                    .priority
                    .cmp(&left.priority)
                    .then_with(|| left.block_id.cmp(&right.block_id))
            });
        }
        InjectionOrderStrategy::CategoryThenPriority => {
            blocks.sort_by(|left, right| {
                category_rank(&policy.enabled_categories, left.category)
                    .cmp(&category_rank(&policy.enabled_categories, right.category))
                    .then_with(|| right.priority.cmp(&left.priority))
                    .then_with(|| left.block_id.cmp(&right.block_id))
            });
        }
    }
}

fn category_rank(enabled: &[PromptContextCategory], category: PromptContextCategory) -> usize {
    enabled
        .iter()
        .position(|value| *value == category)
        .unwrap_or(usize::MAX)
}

fn apply_char_budget(
    blocks: Vec<PromptContextBlock>,
    max_chars: usize,
) -> (Vec<PromptContextBlock>, Vec<String>, Vec<String>) {
    if max_chars == 0 {
        let dropped = blocks.into_iter().map(|block| block.block_id).collect();
        return (Vec::new(), dropped, Vec::new());
    }

    let mut kept = Vec::new();
    let mut dropped_block_ids = Vec::new();
    let mut truncated_block_ids = Vec::new();
    let mut used_chars = 0usize;

    for mut block in blocks {
        if used_chars >= max_chars {
            dropped_block_ids.push(block.block_id);
            continue;
        }

        let remaining = max_chars.saturating_sub(used_chars);
        if block.payload_chars <= remaining {
            used_chars = used_chars.saturating_add(block.payload_chars);
            kept.push(block);
            continue;
        }

        if remaining == 0 {
            dropped_block_ids.push(block.block_id);
            continue;
        }

        block.payload = truncate_chars(&block.payload, remaining);
        block.payload_chars = block.payload.chars().count();
        used_chars = used_chars.saturating_add(block.payload_chars);
        truncated_block_ids.push(block.block_id.clone());
        kept.push(block);
    }

    (kept, dropped_block_ids, truncated_block_ids)
}

fn prioritize_anchors(blocks: Vec<PromptContextBlock>) -> Vec<PromptContextBlock> {
    let (anchors, others): (Vec<_>, Vec<_>) = blocks.into_iter().partition(|block| block.anchor);
    anchors.into_iter().chain(others).collect()
}

fn select_role_mix(
    policy: &InjectionPolicy,
    blocks: &[PromptContextBlock],
) -> Option<RoleMixProfile> {
    let mut roles = Vec::new();
    let mut seen = HashSet::new();

    let has_governance = blocks.iter().any(|block| {
        matches!(
            block.category,
            PromptContextCategory::Safety | PromptContextCategory::Policy
        )
    });
    if has_governance {
        push_role(
            &mut roles,
            &mut seen,
            "governance_guardian",
            0.36,
            "safety/policy anchors present",
        );
    }

    let has_memory = blocks.iter().any(|block| {
        matches!(
            block.category,
            PromptContextCategory::MemoryRecall | PromptContextCategory::WindowSummary
        )
    });
    if has_memory {
        push_role(
            &mut roles,
            &mut seen,
            "memory_strategist",
            0.31,
            "memory recall or window summary context present",
        );
    }

    let has_session_xml = blocks
        .iter()
        .any(|block| block.category == PromptContextCategory::SessionXml);
    if has_session_xml {
        push_role(
            &mut roles,
            &mut seen,
            "session_context_curator",
            0.27,
            "session XML context present",
        );
    }

    let has_knowledge = blocks
        .iter()
        .any(|block| block.category == PromptContextCategory::Knowledge);
    if has_knowledge {
        push_role(
            &mut roles,
            &mut seen,
            "knowledge_synthesizer",
            0.33,
            "knowledge retrieval context present",
        );
    }

    let has_reflection = blocks.iter().any(|block| {
        matches!(
            block.category,
            PromptContextCategory::Reflection | PromptContextCategory::RuntimeHint
        )
    });
    if has_reflection {
        push_role(
            &mut roles,
            &mut seen,
            "reflection_optimizer",
            0.29,
            "reflection/runtime hint context present",
        );
    }

    let qualifies_multi_domain = roles.len() >= 2;
    let force_hybrid = matches!(policy.mode, xiuxian_qianhuan::InjectionMode::Hybrid);
    if !force_hybrid && !qualifies_multi_domain {
        return None;
    }
    if roles.is_empty() {
        return None;
    }

    let rationale = if force_hybrid {
        "policy.mode=hybrid requested role-mix injection".to_string()
    } else {
        format!(
            "multi-domain context detected across {} role domains",
            roles.len()
        )
    };
    Some(RoleMixProfile {
        profile_id: "role_mix.hybrid.v1".to_string(),
        roles,
        rationale,
    })
}

fn push_role(
    roles: &mut Vec<RoleMixRole>,
    seen: &mut HashSet<&'static str>,
    role: &'static str,
    weight: f32,
    _reason: &'static str,
) {
    if seen.insert(role) {
        roles.push(RoleMixRole {
            role: role.to_string(),
            weight,
        });
    }
}

fn truncate_chars(input: &str, max_chars: usize) -> String {
    if max_chars == 0 {
        return String::new();
    }
    if max_chars <= 3 {
        return ".".repeat(max_chars);
    }
    if input.chars().count() <= max_chars {
        return input.to_string();
    }

    let mut out = input
        .chars()
        .take(max_chars.saturating_sub(3))
        .collect::<String>();
    out.push_str("...");
    out
}

fn dedup_preserve_order(values: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    values
        .into_iter()
        .filter(|value| seen.insert(value.clone()))
        .collect()
}
