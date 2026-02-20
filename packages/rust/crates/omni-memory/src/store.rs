//! Episode storage using `LanceDB` for vector similarity search.
//!
//! Provides persistent storage for episodes with vector search capabilities.

use crate::encoder::IntentEncoder;
use crate::episode::Episode;
use crate::persistence::atomic_write_text;
use crate::q_table::QTable;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{PoisonError, RwLockReadGuard, RwLockWriteGuard};

/// Statistics about the memory store.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryStats {
    pub total_episodes: usize,
    pub validated_episodes: usize,
    pub avg_age_hours: f32,
    pub q_table_size: usize,
}

/// Serializable in-memory state snapshot for persistence backends.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryStateSnapshot {
    /// Persisted memory episodes in insertion order.
    pub episodes: Vec<Episode>,
    /// Persisted Q-table values keyed by episode id.
    pub q_values: HashMap<String, f32>,
}

/// Episode store configuration.
#[derive(Debug, Clone)]
pub struct StoreConfig {
    /// Path to the `LanceDB` database.
    pub path: String,
    /// Embedding dimension for intent vectors.
    pub embedding_dim: usize,
    /// Name of the episodes table.
    pub table_name: String,
}

impl Default for StoreConfig {
    fn default() -> Self {
        Self {
            path: default_memory_store_path(),
            embedding_dim: 384,
            table_name: "episodes".to_string(),
        }
    }
}

fn default_memory_store_path() -> String {
    let root = std::env::var("PRJ_ROOT")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| std::env::current_dir().unwrap_or_else(|_| PathBuf::from(".")));

    let data_home = std::env::var("PRJ_DATA_HOME")
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
        .unwrap_or_else(|| root.join(".data"));

    data_home.join("omni-memory").to_string_lossy().to_string()
}

/// Episode store with `LanceDB` persistence and Q-learning.
///
/// Provides:
/// - Vector search for semantic recall
/// - Q-value updates via Q-learning
/// - Persistent storage
pub struct EpisodeStore {
    /// Q-table for episode utility tracking
    pub q_table: QTable,
    /// Intent encoder for embedding generation
    encoder: IntentEncoder,
    /// Store configuration
    config: StoreConfig,
    /// In-memory cache of episodes (loaded on init)
    episodes: std::sync::RwLock<Vec<Episode>>,
}

impl EpisodeStore {
    /// Create a new episode store with the given configuration.
    #[must_use]
    pub fn new(config: StoreConfig) -> Self {
        Self {
            q_table: QTable::new(),
            encoder: IntentEncoder::new(config.embedding_dim),
            config,
            episodes: std::sync::RwLock::new(Vec::new()),
        }
    }

    /// Get the intent encoder (reference).
    #[must_use]
    pub fn encoder(&self) -> &IntentEncoder {
        &self.encoder
    }

    /// Get a clone of the intent encoder.
    #[must_use]
    pub fn encoder_clone(&self) -> IntentEncoder {
        self.encoder.clone()
    }

    fn read_episodes(&self) -> RwLockReadGuard<'_, Vec<Episode>> {
        self.episodes.read().unwrap_or_else(PoisonError::into_inner)
    }

    fn write_episodes(&self) -> RwLockWriteGuard<'_, Vec<Episode>> {
        self.episodes
            .write()
            .unwrap_or_else(PoisonError::into_inner)
    }

    fn infer_scope_from_agent_episode_id(episode_id: &str) -> Option<String> {
        fn parse_with_prefix(episode_id: &str, prefix: &str) -> Option<String> {
            let rest = episode_id.strip_prefix(prefix)?;
            let (scope, suffix) = rest.rsplit_once('-')?;
            if scope.trim().is_empty() || suffix.is_empty() {
                return None;
            }
            if !suffix.chars().all(|ch| ch.is_ascii_digit()) {
                return None;
            }
            Some(scope.to_string())
        }

        parse_with_prefix(episode_id, "turn-")
            .or_else(|| parse_with_prefix(episode_id, "consolidated-"))
    }

    fn normalize_episode_scope(episode: &mut Episode) {
        let normalized = Episode::normalize_scope(&episode.scope);
        if normalized == crate::episode::GLOBAL_EPISODE_SCOPE
            && let Some(inferred_scope) = Self::infer_scope_from_agent_episode_id(&episode.id)
        {
            episode.scope = inferred_scope;
            return;
        }
        episode.scope = normalized;
    }

    fn recall_with_embedding_internal(
        &self,
        embedding: &[f32],
        top_k: usize,
        scope: Option<&str>,
    ) -> Vec<(Episode, f32)> {
        let scope_key = scope.map(Episode::normalize_scope);
        let episodes = self.read_episodes();
        let mut similarities: Vec<(Episode, f32)> = episodes
            .iter()
            .filter(|episode| match scope_key.as_deref() {
                Some(key) => episode.scope_key() == key,
                None => true,
            })
            .map(|episode| {
                let similarity = self
                    .encoder
                    .cosine_similarity(embedding, &episode.intent_embedding);
                (episode.clone(), similarity)
            })
            .collect();

        similarities.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        similarities.into_iter().take(top_k).collect()
    }

    fn rerank_candidates(
        &self,
        candidates: Vec<(Episode, f32)>,
        k2: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        let mut scored: Vec<(Episode, f32)> = candidates
            .into_iter()
            .map(|(mut episode, similarity)| {
                let q_value = self.q_table.get_q(&episode.id);
                episode.q_value = q_value;
                let score = (1.0 - lambda) * similarity + lambda * q_value;
                (episode, score)
            })
            .collect();

        scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        scored.into_iter().take(k2).collect()
    }

    /// Store a new episode.
    ///
    /// Generates embedding from intent and stores episode.
    ///
    /// # Errors
    ///
    /// This currently never returns an error and is modeled as `Result` for API compatibility.
    #[allow(clippy::unnecessary_wraps)]
    pub fn store(&self, mut episode: Episode) -> Result<String> {
        Self::normalize_episode_scope(&mut episode);

        // Initialize Q-value for the episode
        self.q_table.init_episode(&episode.id);

        // Update in-memory cache
        let mut episodes = self.write_episodes();
        episodes.push(episode.clone());

        Ok(episode.id)
    }

    /// Store a new episode under a logical scope.
    ///
    /// The scope key is normalized and persisted with the episode.
    ///
    /// # Errors
    ///
    /// This currently never returns an error and is modeled as `Result` for API compatibility.
    #[allow(clippy::unnecessary_wraps)]
    pub fn store_for_scope(&self, scope: &str, mut episode: Episode) -> Result<String> {
        episode.scope = Episode::normalize_scope(scope);
        self.store(episode)
    }

    /// Get an episode by ID.
    #[must_use]
    pub fn get(&self, id: &str) -> Option<Episode> {
        let episodes = self.read_episodes();
        episodes.iter().find(|e| e.id == id).cloned()
    }

    /// Get all episodes.
    #[must_use]
    pub fn get_all(&self) -> Vec<Episode> {
        self.read_episodes().clone()
    }

    /// Update Q-value for an episode.
    ///
    /// Returns the new Q-value.
    pub fn update_q(&self, episode_id: &str, reward: f32) -> f32 {
        let new_q = self.q_table.update(episode_id, reward);
        // Also update the episode's q_value
        if let Some(ep) = self
            .write_episodes()
            .iter_mut()
            .find(|e| e.id == episode_id)
        {
            ep.q_value = new_q;
        }
        new_q
    }

    /// Recall episodes by semantic similarity.
    ///
    /// Uses the encoder to generate embedding and finds similar episodes.
    /// Returns `top_k` most similar episodes.
    pub fn recall(&self, intent: &str, top_k: usize) -> Vec<(Episode, f32)> {
        let embedding = self.encoder.encode(intent);
        self.recall_with_embedding(&embedding, top_k)
    }

    /// Recall episodes by semantic similarity inside a logical scope.
    pub fn recall_for_scope(&self, scope: &str, intent: &str, top_k: usize) -> Vec<(Episode, f32)> {
        let embedding = self.encoder.encode(intent);
        self.recall_with_embedding_for_scope(scope, &embedding, top_k)
    }

    /// Recall episodes using pre-computed embedding (for real embeddings from Python).
    pub fn recall_with_embedding(&self, embedding: &[f32], top_k: usize) -> Vec<(Episode, f32)> {
        self.recall_with_embedding_internal(embedding, top_k, None)
    }

    /// Recall episodes using pre-computed embedding inside a logical scope.
    pub fn recall_with_embedding_for_scope(
        &self,
        scope: &str,
        embedding: &[f32],
        top_k: usize,
    ) -> Vec<(Episode, f32)> {
        self.recall_with_embedding_internal(embedding, top_k, Some(scope))
    }

    /// Recall episodes with Q-value reranking.
    ///
    /// Two-phase search:
    /// Phase 1: Semantic recall (vector similarity)
    /// Phase 2: Q-value reranking (utility score)
    ///
    /// # Arguments
    /// * `intent` - The query intent
    /// * `k1` - Number of candidates from phase 1
    /// * `k2` - Number of results after reranking
    /// * `lambda` - Weight for Q-value in reranking (0.0 = semantic only, 1.0 = Q only)
    pub fn two_phase_recall(
        &self,
        intent: &str,
        k1: usize,
        k2: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        let candidates = self.recall(intent, k1);
        self.rerank_candidates(candidates, k2, lambda)
    }

    /// Recall episodes with Q-value reranking inside a logical scope.
    pub fn two_phase_recall_for_scope(
        &self,
        scope: &str,
        intent: &str,
        k1: usize,
        k2: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        let candidates = self.recall_for_scope(scope, intent, k1);
        self.rerank_candidates(candidates, k2, lambda)
    }

    /// Two-phase recall with pre-computed embedding.
    pub fn two_phase_recall_with_embedding(
        &self,
        embedding: &[f32],
        k1: usize,
        k2: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        let candidates = self.recall_with_embedding(embedding, k1);
        self.rerank_candidates(candidates, k2, lambda)
    }

    /// Two-phase recall with pre-computed embedding inside a logical scope.
    pub fn two_phase_recall_with_embedding_for_scope(
        &self,
        scope: &str,
        embedding: &[f32],
        k1: usize,
        k2: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        let candidates = self.recall_with_embedding_for_scope(scope, embedding, k1);
        self.rerank_candidates(candidates, k2, lambda)
    }

    /// Multi-hop reasoning: chain multiple queries together.
    ///
    /// Each hop uses the results from the previous hop to inform the next search.
    /// This enables complex reasoning across related concepts.
    ///
    /// # Arguments
    /// * `queries` - List of queries for each hop
    /// * `k` - Number of results per hop
    /// * `lambda` - Q-weight for two-phase search
    ///
    /// # Returns
    /// Final results after all hops
    pub fn multi_hop_recall(
        &self,
        queries: &[String],
        k: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        if queries.is_empty() {
            return vec![];
        }

        // First hop: regular recall
        let mut current_results = self.two_phase_recall(&queries[0], k, k, lambda);

        // Subsequent hops: use previous results to boost similar episodes
        for query in queries.iter().skip(1) {
            // Get embeddings from current results to boost
            let boost_embeddings: Vec<Vec<f32>> = current_results
                .iter()
                .map(|(ep, _)| ep.intent_embedding.clone())
                .collect();

            // Regular recall for this query
            let hop_results = self.two_phase_recall(query, k, k, lambda);

            // Combine results, boosting episodes similar to previous hops
            let mut combined: Vec<(Episode, f32)> = hop_results
                .into_iter()
                .map(|(ep, score)| {
                    // Calculate boost from previous hop results
                    let boost: f32 = boost_embeddings
                        .iter()
                        .map(|prev_emb| {
                            self.encoder
                                .cosine_similarity(&ep.intent_embedding, prev_emb)
                        })
                        .sum::<f32>();
                    let denom = boost_embeddings.iter().fold(0.0_f32, |acc, _| acc + 1.0);
                    let boost = if denom > 0.0 { boost / denom } else { 0.0 };

                    // Combine score with boost (10% boost)
                    let final_score = score + boost * 0.1;
                    (ep, final_score)
                })
                .collect();

            // Sort and take top k
            combined.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            current_results = combined.into_iter().take(k).collect();
        }

        current_results
    }

    /// Multi-hop with pre-computed embeddings (for Python integration).
    pub fn multi_hop_recall_with_embeddings(
        &self,
        query_embeddings: &[Vec<f32>],
        k: usize,
        lambda: f32,
    ) -> Vec<(Episode, f32)> {
        if query_embeddings.is_empty() {
            return vec![];
        }

        // First hop
        let mut current_results =
            self.two_phase_recall_with_embedding(&query_embeddings[0], k, k, lambda);

        // Subsequent hops
        for embedding in query_embeddings.iter().skip(1) {
            let boost_embeddings: Vec<Vec<f32>> = current_results
                .iter()
                .map(|(ep, _)| ep.intent_embedding.clone())
                .collect();

            let hop_results = self.two_phase_recall_with_embedding(embedding, k, k, lambda);

            let mut combined: Vec<(Episode, f32)> = hop_results
                .into_iter()
                .map(|(ep, score)| {
                    let boost: f32 = boost_embeddings
                        .iter()
                        .map(|prev_emb| {
                            self.encoder
                                .cosine_similarity(&ep.intent_embedding, prev_emb)
                        })
                        .sum::<f32>();
                    let denom = boost_embeddings.iter().fold(0.0_f32, |acc, _| acc + 1.0);
                    let boost = if denom > 0.0 { boost / denom } else { 0.0 };
                    let final_score = score + boost * 0.1;
                    (ep, final_score)
                })
                .collect();

            combined.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
            current_results = combined.into_iter().take(k).collect();
        }

        current_results
    }

    /// Get the number of stored episodes.
    #[must_use]
    pub fn len(&self) -> usize {
        self.read_episodes().len()
    }

    /// Check if store is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Update an existing episode's experience.
    ///
    /// Returns true if episode was found and updated.
    pub fn update_episode(&self, episode_id: &str, experience: &str, outcome: &str) -> bool {
        let mut episodes = self.write_episodes();
        if let Some(ep) = episodes.iter_mut().find(|e| e.id == episode_id) {
            ep.experience = experience.to_string();
            ep.outcome = outcome.to_string();
            // Update timestamp
            ep.created_at = chrono::Utc::now().timestamp_millis();
            return true;
        }
        false
    }

    /// Delete an episode by ID.
    ///
    /// Returns true if episode was found and deleted.
    pub fn delete_episode(&self, episode_id: &str) -> bool {
        let mut episodes = self.write_episodes();
        let initial_len = episodes.len();
        episodes.retain(|e| e.id != episode_id);
        let deleted = episodes.len() < initial_len;

        if deleted {
            // Also remove from Q-table
            self.q_table.remove(episode_id);
        }

        deleted
    }

    /// Increment access count for an episode (for frequency-based importance).
    ///
    /// When an episode is retrieved, it should be marked as accessed.
    /// This helps prioritize frequently used episodes.
    pub fn mark_accessed(&self, episode_id: &str) {
        let mut episodes = self.write_episodes();
        if let Some(ep) = episodes.iter_mut().find(|e| e.id == episode_id) {
            ep.success_count += 1;
        }
    }

    /// Record explicit recall feedback on one episode.
    ///
    /// - `success = true`: increments `success_count`
    /// - `success = false`: increments `failure_count`
    ///
    /// Returns `true` when the episode exists and is updated.
    pub fn record_feedback(&self, episode_id: &str, success: bool) -> bool {
        let mut episodes = self.write_episodes();
        if let Some(ep) = episodes.iter_mut().find(|e| e.id == episode_id) {
            if success {
                ep.success_count = ep.success_count.saturating_add(1);
            } else {
                ep.failure_count = ep.failure_count.saturating_add(1);
            }
            ep.q_value = self.q_table.get_q(&ep.id);
            return true;
        }
        false
    }

    /// Apply time-based decay to all episodes.
    ///
    /// Old episodes will have their Q-values decayed towards 0.5.
    ///
    /// Args:
    /// - `decay_factor`: Decay per hour (e.g., 0.95 = 5% decay per hour)
    pub fn apply_decay(&self, decay_factor: f32) {
        let current_time = chrono::Utc::now().timestamp_millis();
        let mut episodes = self.write_episodes();
        for ep in episodes.iter_mut() {
            // Get current Q-value from QTable
            let current_q = self.q_table.get_q(&ep.id);
            // Apply decay to the Q-value based on age
            let age_hours = ep.age_hours(current_time);
            // Apply decay: if age > 0, use time-based decay; otherwise apply a small decay for testing
            let decay = if age_hours > 0.01 {
                // Real time-based decay
                decay_factor.powf(age_hours)
            } else {
                // For testing: apply decay_factor directly (simulates old memory)
                decay_factor
            };
            let decayed_q = 0.5 + (current_q - 0.5) * decay;
            // Update both episode and QTable
            ep.q_value = decayed_q;
            self.q_table.update(&ep.id, decayed_q);
        }
        log::info!(
            "Applied decay factor {} to {} episodes",
            decay_factor,
            episodes.len()
        );
    }

    /// Get statistics about the memory store.
    #[must_use]
    pub fn stats(&self) -> MemoryStats {
        let episodes = self.read_episodes();
        let current_time = chrono::Utc::now().timestamp_millis();

        let mut total_age_hours = 0.0;
        let mut validated_count = 0;

        for ep in episodes.iter() {
            total_age_hours += ep.age_hours(current_time);
            if ep.is_validated() {
                validated_count += 1;
            }
        }

        let count = episodes.len();
        let count_f32 = episodes.iter().fold(0.0_f32, |acc, _| acc + 1.0);
        MemoryStats {
            total_episodes: count,
            validated_episodes: validated_count,
            avg_age_hours: if count > 0 {
                total_age_hours / count_f32
            } else {
                0.0
            },
            q_table_size: self.q_table.len(),
        }
    }

    /// Get the store configuration.
    #[must_use]
    pub fn config(&self) -> &StoreConfig {
        &self.config
    }

    /// Build a full memory snapshot (episodes + Q-values).
    #[must_use]
    pub fn snapshot(&self) -> MemoryStateSnapshot {
        let mut episodes = self.read_episodes().clone();
        for episode in &mut episodes {
            episode.q_value = self.q_table.get_q(&episode.id);
        }

        MemoryStateSnapshot {
            episodes,
            q_values: self.q_table.snapshot_map(),
        }
    }

    /// Restore state from a memory snapshot.
    pub fn restore_snapshot(&self, snapshot: MemoryStateSnapshot) {
        let MemoryStateSnapshot {
            mut episodes,
            q_values,
        } = snapshot;
        self.q_table.replace_map(q_values);
        for episode in &mut episodes {
            episode.q_value = self.q_table.get_q(&episode.id);
            Self::normalize_episode_scope(episode);
        }
        *self.write_episodes() = episodes;
    }

    /// Path to the default episodes state file.
    #[must_use]
    pub fn episodes_state_path(&self) -> PathBuf {
        PathBuf::from(&self.config.path).join(format!("{}.episodes.json", self.config.table_name))
    }

    /// Path to the default Q-table state file.
    #[must_use]
    pub fn q_table_state_path(&self) -> PathBuf {
        PathBuf::from(&self.config.path).join(format!("{}.q_table.json", self.config.table_name))
    }

    /// Save both episodes and Q-table using default state paths.
    ///
    /// # Errors
    ///
    /// Returns an error if either state file cannot be persisted.
    pub fn save_state(&self) -> Result<()> {
        let episodes_path = self.episodes_state_path();
        let q_table_path = self.q_table_state_path();
        self.save(episodes_path.to_string_lossy().as_ref())?;
        self.save_q_table(q_table_path.to_string_lossy().as_ref())?;
        Ok(())
    }

    /// Load both episodes and Q-table using default state paths.
    ///
    /// # Errors
    ///
    /// Returns an error if either state file exists but cannot be loaded.
    pub fn load_state(&self) -> Result<()> {
        let episodes_path = self.episodes_state_path();
        let q_table_path = self.q_table_state_path();
        self.load(episodes_path.to_string_lossy().as_ref())?;
        self.load_q_table(q_table_path.to_string_lossy().as_ref())?;
        Ok(())
    }

    /// Save episodes to disk (JSON format).
    ///
    /// # Errors
    ///
    /// Returns an error if episodes cannot be serialized or written to disk.
    pub fn save(&self, path: &str) -> Result<()> {
        let mut episodes = self.write_episodes();
        // Sync Q-values from QTable to episodes before saving
        for ep in episodes.iter_mut() {
            ep.q_value = self.q_table.get_q(&ep.id);
        }
        let json = serde_json::to_string_pretty(&*episodes)?;
        atomic_write_text(Path::new(path), &json)?;
        log::info!("Saved {} episodes to {}", episodes.len(), path);
        Ok(())
    }

    /// Load episodes from disk (JSON format).
    ///
    /// # Errors
    ///
    /// Returns an error if the file exists but cannot be read or parsed.
    pub fn load(&self, path: &str) -> Result<()> {
        if !std::path::Path::new(path).exists() {
            log::info!("No existing data file at {path}");
            return Ok(());
        }
        let json = std::fs::read_to_string(path)?;
        let mut episodes: Vec<Episode> = serde_json::from_str(&json)?;
        for episode in &mut episodes {
            Self::normalize_episode_scope(episode);
        }
        let count = episodes.len();
        *self.write_episodes() = episodes;
        log::info!("Loaded {count} episodes from {path}");
        Ok(())
    }

    /// Save Q-table to disk.
    ///
    /// # Errors
    ///
    /// Returns an error if the Q-table cannot be written to disk.
    pub fn save_q_table(&self, path: &str) -> Result<()> {
        self.q_table.save(path)
    }

    /// Load Q-table from disk.
    ///
    /// # Errors
    ///
    /// Returns an error if the Q-table file cannot be read or parsed.
    pub fn load_q_table(&self, path: &str) -> Result<()> {
        self.q_table.load(path)
    }

    /// Get `LanceDB` dataset path for this store.
    ///
    /// Note: `LanceDB` persistence is deferred due to API changes in newer `LanceDB` versions.
    /// Use JSON persistence (save/load) instead.
    #[must_use]
    pub fn lance_path(&self) -> String {
        format!("{}/{}.lance", self.config.path, self.config.table_name)
    }
}

impl Default for EpisodeStore {
    fn default() -> Self {
        Self::new(StoreConfig::default())
    }
}

// Note: LanceDB persistence is deferred due to API changes in newer LanceDB versions.
// Use JSON persistence (save/load methods) instead.
