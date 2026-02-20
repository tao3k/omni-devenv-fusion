use omni_memory::{Episode, EpisodeStore};

use super::super::memory_recall_feedback::RecallOutcome;

#[derive(Debug, Clone, PartialEq)]
pub(in crate::agent) struct RecalledEpisodeCandidate {
    pub episode_id: String,
    pub score: f32,
}

#[derive(Debug, Clone, PartialEq)]
pub(in crate::agent) struct RecallCreditUpdate {
    pub episode_id: String,
    pub score: f32,
    pub weight: f32,
    pub previous_q: f32,
    pub effective_reward: f32,
    pub updated_q: f32,
}

pub(in crate::agent) fn select_recall_credit_candidates(
    recalled: &[(Episode, f32)],
    max_candidates: usize,
) -> Vec<RecalledEpisodeCandidate> {
    recalled
        .iter()
        .take(max_candidates.max(1))
        .map(|(episode, score)| RecalledEpisodeCandidate {
            episode_id: episode.id.clone(),
            score: *score,
        })
        .collect()
}

pub(in crate::agent) fn apply_recall_credit(
    store: &EpisodeStore,
    candidates: &[RecalledEpisodeCandidate],
    outcome: RecallOutcome,
) -> Vec<RecallCreditUpdate> {
    if candidates.is_empty() {
        return Vec::new();
    }
    let target_reward = match outcome {
        RecallOutcome::Success => 1.0,
        RecallOutcome::Failure => 0.0,
    };
    let mut updates = Vec::with_capacity(candidates.len());
    for (index, candidate) in candidates.iter().enumerate() {
        if store.get(&candidate.episode_id).is_none() {
            continue;
        }
        let previous_q = store.q_table.get_q(&candidate.episode_id);
        let weight = credit_weight(index, candidates.len(), candidate.score);
        let effective_reward = previous_q + weight * (target_reward - previous_q);
        let updated_q = store.update_q(&candidate.episode_id, effective_reward);
        let _ = store.record_feedback(
            &candidate.episode_id,
            matches!(outcome, RecallOutcome::Success),
        );
        updates.push(RecallCreditUpdate {
            episode_id: candidate.episode_id.clone(),
            score: candidate.score,
            weight,
            previous_q,
            effective_reward,
            updated_q,
        });
    }
    updates
}

fn credit_weight(rank: usize, total: usize, score: f32) -> f32 {
    let rank_weight = if total <= 1 {
        1.0
    } else {
        1.0 - (rank as f32 / (total.saturating_sub(1)) as f32)
    };
    let score_weight = normalize_score_weight(score);
    (0.20 + (rank_weight * 0.55) + (score_weight * 0.25)).clamp(0.15, 1.0)
}

fn normalize_score_weight(score: f32) -> f32 {
    if !score.is_finite() {
        return 0.0;
    }
    ((score.clamp(-1.0, 1.0) + 1.0) / 2.0).clamp(0.0, 1.0)
}

#[cfg(test)]
#[path = "../../../tests/agent/memory/recall_credit.rs"]
mod tests;
