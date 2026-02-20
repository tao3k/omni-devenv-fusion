//! Two-Phase Search implementation for self-evolving memory.
//!
//! Implements the CORE algorithm from `MemRL` paper:
//! Phase 1: Semantic recall (vector similarity search)
//! Phase 2: Q-value reranking (utility-based selection)

use crate::encoder::IntentEncoder;
use crate::episode::Episode;
use crate::q_table::QTable;
use std::sync::Arc;

/// Two-phase search configuration.
#[derive(Debug, Clone)]
pub struct TwoPhaseConfig {
    /// Number of candidates to retrieve in phase 1
    pub k1: usize,
    /// Number of final results after phase 2
    pub k2: usize,
    /// Lambda weight for Q-value in phase 2 (0.0 = semantic only, 1.0 = Q only)
    pub lambda: f32,
}

impl Default for TwoPhaseConfig {
    fn default() -> Self {
        Self {
            k1: 20,
            k2: 5,
            lambda: 0.3, // 30% weight on Q-value, 70% on semantic similarity
        }
    }
}

/// Two-phase search engine for memory recall.
///
/// Combines semantic similarity with Q-value utility for optimal recall.
pub struct TwoPhaseSearch {
    /// Q-table for episode utilities
    q_table: Arc<QTable>,
    /// Intent encoder
    encoder: Arc<IntentEncoder>,
    /// Search configuration
    config: TwoPhaseConfig,
}

impl TwoPhaseSearch {
    /// Create a new two-phase search engine.
    pub fn new(q_table: Arc<QTable>, encoder: Arc<IntentEncoder>, config: TwoPhaseConfig) -> Self {
        Self {
            q_table,
            encoder,
            config,
        }
    }

    /// Create with default configuration.
    pub fn with_defaults(q_table: Arc<QTable>, encoder: Arc<IntentEncoder>) -> Self {
        Self::new(q_table, encoder, TwoPhaseConfig::default())
    }

    /// Execute two-phase search.
    ///
    /// # Arguments
    /// * `episodes` - All available episodes to search from
    /// * `intent` - Query intent
    /// * `k1` - Override for phase 1 candidate count
    /// * `k2` - Override for phase 2 result count
    /// * `lambda` - Override for Q-value weight
    ///
    /// # Returns
    /// Vector of (episode, score) tuples sorted by score
    #[must_use]
    pub fn search(
        &self,
        episodes: &[Episode],
        intent: &str,
        k1: Option<usize>,
        k2: Option<usize>,
        lambda: Option<f32>,
    ) -> Vec<(Episode, f32)> {
        let k1 = k1.unwrap_or(self.config.k1);
        let k2 = k2.unwrap_or(self.config.k2);
        let lambda = lambda.unwrap_or(self.config.lambda);

        // Phase 1: Semantic recall
        let embedding = self.encoder.encode(intent);
        let mut candidates: Vec<(Episode, f32)> = episodes
            .iter()
            .map(|ep| {
                let similarity = self
                    .encoder
                    .cosine_similarity(&embedding, &ep.intent_embedding);
                (ep.clone(), similarity)
            })
            .collect();

        // Sort by semantic similarity and take top k1
        candidates.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        candidates.truncate(k1);

        // Phase 2: Q-value reranking
        let mut reranked: Vec<(Episode, f32)> = candidates
            .into_iter()
            .map(|(ep, sim)| {
                let q_value = self.q_table.get_q(&ep.id);
                // Combined score: (1-lambda) * similarity + lambda * q_value
                let score = (1.0 - lambda) * sim + lambda * q_value;
                (ep, score)
            })
            .collect();

        // Sort by combined score
        reranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        reranked.truncate(k2);

        reranked
    }

    /// Quick search with default parameters.
    #[must_use]
    pub fn quick_search(&self, episodes: &[Episode], intent: &str) -> Vec<(Episode, f32)> {
        self.search(episodes, intent, None, None, None)
    }

    /// Get the configuration.
    #[must_use]
    pub fn config(&self) -> &TwoPhaseConfig {
        &self.config
    }

    /// Update configuration.
    pub fn set_config(&mut self, config: TwoPhaseConfig) {
        self.config = config;
    }
}

/// Calculate combined score for an episode.
#[must_use]
pub fn calculate_score(similarity: f32, q_value: f32, lambda: f32) -> f32 {
    (1.0 - lambda) * similarity + lambda * q_value
}
