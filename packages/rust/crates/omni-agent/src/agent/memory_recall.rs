use omni_memory::Episode;
use omni_tokenizer::count_tokens;
use std::time::{SystemTime, UNIX_EPOCH};

use crate::session::ChatMessage;

/// System message name used for injected memory recall context.
pub(crate) const MEMORY_RECALL_MESSAGE_NAME: &str = "agent.memory.recall";
const RECENCY_HALF_LIFE_HOURS: f32 = 24.0 * 7.0;

#[derive(Debug, Clone, Copy)]
pub(crate) struct MemoryRecallInput {
    pub base_k1: usize,
    pub base_k2: usize,
    pub base_lambda: f32,
    pub context_budget_tokens: Option<usize>,
    pub context_budget_reserve_tokens: usize,
    pub context_tokens_before_recall: usize,
    pub active_turns_estimate: usize,
    pub window_max_turns: Option<usize>,
    pub summary_segment_count: usize,
}

#[derive(Debug, Clone, Copy)]
pub(crate) struct MemoryRecallPlan {
    pub k1: usize,
    pub k2: usize,
    pub lambda: f32,
    pub min_score: f32,
    pub max_context_chars: usize,
    pub budget_pressure: f32,
    pub window_pressure: f32,
    pub effective_budget_tokens: Option<usize>,
}

/// Estimate total token footprint for a message list.
pub(crate) fn estimate_messages_tokens(messages: &[ChatMessage]) -> usize {
    messages.iter().map(estimated_message_tokens).sum()
}

/// Derive dynamic memory-recall parameters from current context pressure.
pub(crate) fn plan_memory_recall(input: MemoryRecallInput) -> MemoryRecallPlan {
    let mut k1 = input.base_k1.max(1);
    let mut k2 = input.base_k2.max(1).min(k1);
    let mut lambda = clamp_lambda(input.base_lambda);
    let mut min_score = 0.08_f32;
    let mut max_context_chars = (320 + k2.saturating_mul(220)).clamp(480, 1_800);

    let effective_budget_tokens = input.context_budget_tokens.map(|budget| {
        budget
            .saturating_sub(input.context_budget_reserve_tokens)
            .max(1)
    });
    let budget_pressure = effective_budget_tokens.map_or(0.0, |effective| {
        input.context_tokens_before_recall as f32 / effective as f32
    });
    let window_pressure = match input.window_max_turns {
        Some(max_turns) if max_turns > 0 => input.active_turns_estimate as f32 / max_turns as f32,
        _ => 0.0,
    };

    if budget_pressure >= 1.0 {
        k2 = k2.min(2).max(1);
        k1 = k1.min(8).max(k2);
        lambda = (lambda + 0.2).clamp(0.0, 0.95);
        min_score = 0.20;
        max_context_chars = (300 + k2.saturating_mul(160)).clamp(320, 700);
    } else if budget_pressure >= 0.8 {
        k2 = k2.min(3).max(1);
        k1 = k1.min(12).max(k2);
        lambda = (lambda + 0.1).clamp(0.0, 0.90);
        min_score = 0.15;
        max_context_chars = (420 + k2.saturating_mul(180)).clamp(420, 1_000);
    } else if budget_pressure <= 0.45
        && (window_pressure >= 0.75 || input.summary_segment_count > 0)
    {
        let boosted_k2_cap = input.base_k2.saturating_add(2).max(2);
        let boosted_k1_cap = input.base_k1.saturating_add(8).max(4);
        k2 = k2.saturating_add(1).min(boosted_k2_cap).max(1);
        k1 = k1.saturating_add(4).min(boosted_k1_cap).max(k2);
        lambda = (lambda - 0.05).clamp(0.0, 0.90);
        min_score = 0.05;
        max_context_chars = (420 + k2.saturating_mul(240)).clamp(640, 2_200);
    }

    MemoryRecallPlan {
        k1,
        k2,
        lambda,
        min_score,
        max_context_chars,
        budget_pressure,
        window_pressure,
        effective_budget_tokens,
    }
}

/// Keep high-quality recalled episodes according to the dynamic recall plan.
pub(crate) fn filter_recalled_episodes(
    recalled: Vec<(Episode, f32)>,
    plan: &MemoryRecallPlan,
) -> Vec<(Episode, f32)> {
    filter_recalled_episodes_at(recalled, plan, now_unix_ms())
}

pub(crate) fn filter_recalled_episodes_at(
    recalled: Vec<(Episode, f32)>,
    plan: &MemoryRecallPlan,
    now_unix_ms: i64,
) -> Vec<(Episode, f32)> {
    let recency_beta = recency_beta(plan);
    let mut finite = recalled
        .into_iter()
        .filter(|(_, score)| score.is_finite())
        .map(|(episode, score)| {
            let recency = episode_recency_score(&episode, now_unix_ms, RECENCY_HALF_LIFE_HOURS);
            let fused_score = fuse_with_recency(score, recency, recency_beta);
            (episode, fused_score)
        })
        .collect::<Vec<_>>();
    finite.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

    let mut selected = finite
        .iter()
        .filter(|(_, score)| *score >= plan.min_score)
        .take(plan.k2)
        .map(|(episode, score)| (episode.clone(), *score))
        .collect::<Vec<_>>();

    // Keep one positive candidate if all were filtered by min-score.
    if selected.is_empty()
        && let Some((episode, score)) = finite.first()
        && *score > 0.0
    {
        selected.push((episode.clone(), *score));
    }

    selected
}

fn recency_beta(plan: &MemoryRecallPlan) -> f32 {
    if plan.budget_pressure >= 1.0 {
        0.28
    } else if plan.budget_pressure >= 0.8 {
        0.24
    } else if plan.window_pressure >= 0.75 {
        0.18
    } else {
        0.14
    }
}

fn episode_recency_score(episode: &Episode, now_unix_ms: i64, half_life_hours: f32) -> f32 {
    if !half_life_hours.is_finite() || half_life_hours <= 0.0 {
        return 1.0;
    }
    let age_ms = now_unix_ms.saturating_sub(episode.created_at).max(0) as f32;
    let age_hours = age_ms / (1000.0 * 60.0 * 60.0);
    let exponent = -(std::f32::consts::LN_2 * age_hours / half_life_hours);
    exponent.exp().clamp(0.0, 1.0)
}

fn fuse_with_recency(base_score: f32, recency_score: f32, recency_beta: f32) -> f32 {
    let beta = recency_beta.clamp(0.0, 0.9);
    ((1.0 - beta) * base_score + beta * recency_score).clamp(-1.0, 1.0)
}

/// Build one bounded memory context block for system prompt injection.
pub(crate) fn build_memory_context_message(
    recalled: &[(Episode, f32)],
    max_context_chars: usize,
) -> Option<String> {
    if recalled.is_empty() || max_context_chars == 0 {
        return None;
    }

    let header = "Relevant past experiences (use to inform your response):";
    let mut lines = vec![header.to_string()];
    let mut remaining_chars = max_context_chars.saturating_sub(header.chars().count() + 1);

    for (index, (episode, score)) in recalled.iter().enumerate() {
        if remaining_chars < 80 {
            break;
        }

        let intent = clip_to_chars(&episode.intent, 72);
        let outcome = clip_to_chars(&episode.outcome, 56);
        let prefix = format!(
            "- [{}] score={:.3} intent={} outcome={} experience=",
            index + 1,
            score,
            intent,
            outcome
        );

        let prefix_chars = prefix.chars().count();
        if prefix_chars >= remaining_chars {
            break;
        }

        let experience_budget = remaining_chars.saturating_sub(prefix_chars).clamp(48, 260);
        let experience = clip_to_chars(&episode.experience, experience_budget);
        let line = format!("{prefix}{experience}");
        remaining_chars = remaining_chars.saturating_sub(line.chars().count() + 1);
        lines.push(line);
    }

    if lines.len() <= 1 {
        return None;
    }

    Some(lines.join("\n"))
}

fn estimated_message_tokens(message: &ChatMessage) -> usize {
    let mut total = estimated_message_overhead_tokens(message);
    if let Some(content) = &message.content {
        total = total.saturating_add(count_tokens(content));
    }
    total
}

fn estimated_message_overhead_tokens(message: &ChatMessage) -> usize {
    let mut total = 6usize.saturating_add(count_tokens(&message.role));
    if let Some(name) = &message.name {
        total = total.saturating_add(count_tokens(name));
    }
    if let Some(tool_call_id) = &message.tool_call_id {
        total = total.saturating_add(count_tokens(tool_call_id));
    }
    if let Some(tool_calls) = &message.tool_calls {
        let encoded = serde_json::to_string(tool_calls).unwrap_or_default();
        total = total.saturating_add(count_tokens(&encoded));
    }
    total
}

fn clip_to_chars(input: &str, max_chars: usize) -> String {
    if max_chars == 0 {
        return String::new();
    }

    if input.chars().count() <= max_chars {
        return input.to_string();
    }

    let keep = max_chars.saturating_sub(3);
    let mut out = input.chars().take(keep).collect::<String>();
    out.push_str("...");
    out
}

fn clamp_lambda(value: f32) -> f32 {
    if value.is_finite() {
        value.clamp(0.0, 1.0)
    } else {
        0.3
    }
}

fn now_unix_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as i64)
        .unwrap_or(0)
}

#[cfg(test)]
#[path = "../../tests/agent/memory_recall.rs"]
mod tests;
