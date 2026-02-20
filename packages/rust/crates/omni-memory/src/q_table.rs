//! Q-Table implementation for self-evolving memory.
//!
//! Implements Q-Learning algorithm: `Q_new = Q_old + α * (r - Q_old)`
//! where `α` is the learning rate and `r` is the reward.

use crate::persistence::atomic_write_text;
use dashmap::DashMap;
use std::collections::HashMap;
use std::path::Path;
use std::sync::{PoisonError, RwLock, RwLockReadGuard, RwLockWriteGuard};

/// Q-Learning table for episode utility tracking.
///
/// Uses a concurrent hash map for thread-safe updates.
pub struct QTable {
    /// Internal Q-table mapping `episode_id -> q_value`.
    table: RwLock<DashMap<String, f32>>,
    /// Learning rate (α) - typically 0.1-0.3
    learning_rate: f32,
    /// Discount factor (γ) - typically 0.9-0.99
    discount_factor: f32,
}

// Manual Clone implementation - creates a new empty table
impl Clone for QTable {
    fn clone(&self) -> Self {
        Self {
            table: RwLock::new(DashMap::new()),
            learning_rate: self.learning_rate,
            discount_factor: self.discount_factor,
        }
    }
}

impl QTable {
    /// Create a new Q-Table with default parameters.
    ///
    /// Default `learning_rate = 0.2`
    /// Default `discount_factor = 0.95`
    #[must_use]
    pub fn new() -> Self {
        Self::with_params(0.2, 0.95)
    }

    /// Create a new Q-Table with custom parameters.
    ///
    /// # Arguments
    /// * `learning_rate` - α in Q-learning, controls how much new info overrides old
    /// * `discount_factor` - γ in Q-learning, balances immediate vs future reward
    #[must_use]
    pub fn with_params(learning_rate: f32, discount_factor: f32) -> Self {
        Self {
            table: RwLock::new(DashMap::new()),
            learning_rate,
            discount_factor,
        }
    }

    fn read_table(&self) -> RwLockReadGuard<'_, DashMap<String, f32>> {
        self.table.read().unwrap_or_else(PoisonError::into_inner)
    }

    fn write_table(&self) -> RwLockWriteGuard<'_, DashMap<String, f32>> {
        self.table.write().unwrap_or_else(PoisonError::into_inner)
    }

    /// Update Q-value for an episode using Q-learning.
    ///
    /// `Q_new = Q_old + α * (reward - Q_old)`.
    ///
    /// # Arguments
    /// * `episode_id` - The episode identifier
    /// * `reward` - The reward signal (typically 0.0-1.0)
    ///
    /// # Returns
    /// The new Q-value after update.
    pub fn update(&self, episode_id: &str, reward: f32) -> f32 {
        let q_old = self.get_q(episode_id);
        let q_new = q_old + self.learning_rate * (reward - q_old);

        // Clamp Q-value to [0.0, 1.0] range
        let q_clamped = q_new.clamp(0.0, 1.0);

        self.read_table().insert(episode_id.to_string(), q_clamped);

        q_clamped
    }

    /// Get the Q-value for an episode.
    ///
    /// Returns default 0.5 if episode not found (initial Q-value).
    #[must_use]
    pub fn get_q(&self, episode_id: &str) -> f32 {
        self.read_table()
            .get(episode_id)
            .map_or(0.5, |v| *v.value())
    }

    /// Initialize Q-value for a new episode.
    pub fn init_episode(&self, episode_id: &str) {
        let table = self.read_table();
        if !table.contains_key(episode_id) {
            table.insert(episode_id.to_string(), 0.5);
        }
    }

    /// Get multiple Q-values at once.
    #[must_use]
    pub fn get_batch(&self, episode_ids: &[String]) -> Vec<(String, f32)> {
        let table = self.read_table();
        episode_ids
            .iter()
            .map(|id| {
                let q = table.get(id).map_or(0.5, |v| *v.value());
                (id.clone(), q)
            })
            .collect()
    }

    /// Batch update multiple Q-values.
    ///
    /// More efficient than individual updates.
    #[must_use]
    pub fn update_batch(&self, updates: &[(String, f32)]) -> Vec<(String, f32)> {
        let table = self.read_table();
        updates
            .iter()
            .map(|(episode_id, reward)| {
                let q_old = table.get(episode_id).map_or(0.5, |v| *v.value());
                let q_new = q_old + self.learning_rate * (reward - q_old);
                let q_clamped = q_new.clamp(0.0, 1.0);
                table.insert(episode_id.clone(), q_clamped);
                (episode_id.clone(), q_clamped)
            })
            .collect()
    }

    /// Get all episode IDs in the Q-table.
    #[must_use]
    pub fn get_all_ids(&self) -> Vec<String> {
        self.read_table().iter().map(|r| r.key().clone()).collect()
    }

    /// Snapshot all Q-values into a plain map.
    #[must_use]
    pub fn snapshot_map(&self) -> HashMap<String, f32> {
        self.read_table()
            .iter()
            .map(|entry| (entry.key().clone(), *entry.value()))
            .collect()
    }

    /// Replace all Q-values from a snapshot map.
    pub fn replace_map(&self, values: HashMap<String, f32>) {
        *self.write_table() = DashMap::from_iter(values);
    }

    /// Get the number of entries in the Q-table.
    #[must_use]
    pub fn len(&self) -> usize {
        self.read_table().len()
    }

    /// Check if the Q-table is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Remove an entry from the Q-table.
    pub fn remove(&self, episode_id: &str) {
        self.read_table().remove(episode_id);
    }

    /// Save Q-table to JSON file.
    ///
    /// # Errors
    ///
    /// Returns an error if the Q-table cannot be serialized or written to disk.
    pub fn save(&self, path: &str) -> Result<(), anyhow::Error> {
        let data: std::collections::HashMap<String, f32> = self
            .read_table()
            .iter()
            .map(|r| (r.key().clone(), *r.value()))
            .collect();
        let json = serde_json::to_string_pretty(&data)?;
        atomic_write_text(Path::new(path), &json)?;
        log::info!("Saved Q-table with {} entries to {}", data.len(), path);
        Ok(())
    }

    /// Load Q-table from JSON file.
    ///
    /// # Errors
    ///
    /// Returns an error if the file exists but cannot be read or parsed.
    pub fn load(&self, path: &str) -> Result<(), anyhow::Error> {
        if !std::path::Path::new(path).exists() {
            log::info!("No existing Q-table file at {path}");
            return Ok(());
        }
        let json = std::fs::read_to_string(path)?;
        let data: std::collections::HashMap<String, f32> = serde_json::from_str(&json)?;
        let count = data.len();
        *self.write_table() = DashMap::from_iter(data);
        log::info!("Loaded {count} Q-table entries from {path}");
        Ok(())
    }

    /// Get learning rate.
    #[must_use]
    pub fn learning_rate(&self) -> f32 {
        self.learning_rate
    }

    /// Get discount factor.
    #[must_use]
    pub fn discount_factor(&self) -> f32 {
        self.discount_factor
    }
}

impl Default for QTable {
    fn default() -> Self {
        Self::new()
    }
}
