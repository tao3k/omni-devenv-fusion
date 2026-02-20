#![allow(missing_docs)]

use omni_memory::Episode;

use super::{
    MemoryRecallInput, build_memory_context_message, filter_recalled_episodes,
    filter_recalled_episodes_at, plan_memory_recall,
};

fn make_episode(id: &str, intent: &str, experience: &str) -> Episode {
    Episode::new(
        id.to_string(),
        intent.to_string(),
        vec![0.0; 8],
        experience.to_string(),
        "completed".to_string(),
    )
}

fn make_episode_with_created_at(
    id: &str,
    intent: &str,
    experience: &str,
    created_at: i64,
) -> Episode {
    let mut episode = make_episode(id, intent, experience);
    episode.created_at = created_at;
    episode
}

#[test]
fn high_budget_pressure_tightens_recall_plan() {
    let plan = plan_memory_recall(MemoryRecallInput {
        base_k1: 20,
        base_k2: 6,
        base_lambda: 0.3,
        context_budget_tokens: Some(1_000),
        context_budget_reserve_tokens: 200,
        context_tokens_before_recall: 1_200,
        active_turns_estimate: 24,
        window_max_turns: Some(64),
        summary_segment_count: 0,
    });

    assert!(plan.budget_pressure >= 1.0);
    assert!(plan.k2 <= 2);
    assert!(plan.k1 <= 8);
    assert!(plan.lambda >= 0.45);
    assert!(plan.min_score >= 0.15);
    assert!(plan.max_context_chars <= 700);
}

#[test]
fn low_budget_pressure_with_window_pressure_boosts_recall_plan() {
    let plan = plan_memory_recall(MemoryRecallInput {
        base_k1: 10,
        base_k2: 3,
        base_lambda: 0.3,
        context_budget_tokens: Some(5_000),
        context_budget_reserve_tokens: 300,
        context_tokens_before_recall: 1_200,
        active_turns_estimate: 50,
        window_max_turns: Some(60),
        summary_segment_count: 2,
    });

    assert!(plan.budget_pressure < 0.45);
    assert!(plan.window_pressure > 0.75);
    assert!(plan.k2 >= 4);
    assert!(plan.k1 >= 14);
    assert!(plan.lambda <= 0.30);
    assert!(plan.max_context_chars >= 640);
    assert!(plan.min_score <= 0.05);
}

#[test]
fn filter_recalled_episodes_applies_threshold_and_keeps_positive_fallback() {
    let plan = plan_memory_recall(MemoryRecallInput {
        base_k1: 8,
        base_k2: 3,
        base_lambda: 0.4,
        context_budget_tokens: Some(900),
        context_budget_reserve_tokens: 100,
        context_tokens_before_recall: 1_100,
        active_turns_estimate: 20,
        window_max_turns: Some(40),
        summary_segment_count: 0,
    });

    let recalled = vec![
        (make_episode("a", "intent a", "experience a"), 0.18),
        (make_episode("b", "intent b", "experience b"), 0.09),
        (make_episode("c", "intent c", "experience c"), -0.10),
    ];
    let selected = filter_recalled_episodes(recalled, &plan);
    assert!(!selected.is_empty());
    assert!(selected.len() <= plan.k2);
    assert!(selected.iter().all(|(_, score)| *score > 0.0));
}

#[test]
fn build_memory_context_message_respects_char_budget() {
    let recalled = vec![
        (
            make_episode(
                "a",
                "how to deploy",
                &"step-by-step deployment checklist ".repeat(40),
            ),
            0.62,
        ),
        (
            make_episode(
                "b",
                "debug webhook timeout",
                &"collect logs and inspect retries ".repeat(30),
            ),
            0.54,
        ),
    ];

    let max_chars = 420;
    let message =
        build_memory_context_message(&recalled, max_chars).expect("context block should exist");
    assert!(message.chars().count() <= max_chars);
    assert!(message.contains("Relevant past experiences"));
    assert!(message.contains("score="));
}

#[test]
fn recency_fusion_prefers_recent_when_base_scores_are_close() {
    let plan = plan_memory_recall(MemoryRecallInput {
        base_k1: 8,
        base_k2: 3,
        base_lambda: 0.4,
        context_budget_tokens: Some(3_000),
        context_budget_reserve_tokens: 300,
        context_tokens_before_recall: 1_000,
        active_turns_estimate: 24,
        window_max_turns: Some(32),
        summary_segment_count: 0,
    });

    let now = 1_800_000_000_000_i64;
    let one_hour_ms = 60_i64 * 60 * 1000;
    let one_month_ms = 30_i64 * 24 * one_hour_ms;
    let old_episode = make_episode_with_created_at("old", "intent old", "exp", now - one_month_ms);
    let new_episode = make_episode_with_created_at("new", "intent new", "exp", now - one_hour_ms);

    let recalled = vec![(old_episode, 0.44), (new_episode, 0.43)];
    let selected = filter_recalled_episodes_at(recalled, &plan, now);
    assert!(!selected.is_empty());
    assert_eq!(selected[0].0.id, "new");
}

#[test]
fn recency_fusion_does_not_override_strong_relevance_signal() {
    let plan = plan_memory_recall(MemoryRecallInput {
        base_k1: 8,
        base_k2: 3,
        base_lambda: 0.4,
        context_budget_tokens: Some(3_000),
        context_budget_reserve_tokens: 300,
        context_tokens_before_recall: 1_000,
        active_turns_estimate: 24,
        window_max_turns: Some(32),
        summary_segment_count: 0,
    });

    let now = 1_800_000_000_000_i64;
    let one_hour_ms = 60_i64 * 60 * 1000;
    let one_year_ms = 365_i64 * 24 * one_hour_ms;
    let strong_old =
        make_episode_with_created_at("strong-old", "intent old", "exp", now - one_year_ms);
    let weak_new = make_episode_with_created_at("weak-new", "intent new", "exp", now - one_hour_ms);

    let recalled = vec![(strong_old, 0.95), (weak_new, 0.20)];
    let selected = filter_recalled_episodes_at(recalled, &plan, now);
    assert!(!selected.is_empty());
    assert_eq!(selected[0].0.id, "strong-old");
}
