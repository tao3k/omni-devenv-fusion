//! Episode data structures for self-evolving memory.
//!
//! An Episode represents a single interaction experience in the memory system,
//! storing intent, experience, outcome, and Q-learning metadata.

use chrono::Utc;
use serde::{Deserialize, Serialize};

/// Default scope for legacy/global episodes.
pub const GLOBAL_EPISODE_SCOPE: &str = "__global__";

fn default_episode_scope() -> String {
    GLOBAL_EPISODE_SCOPE.to_string()
}

/// A single experience episode in the memory system.
///
/// Each episode represents a stored interaction with:
/// - Intent (what the user wanted)
/// - Experience (the actual experience/response)
/// - Outcome (success/failure result)
/// - Q-value (learned utility from Q-learning)
/// - Usage statistics (success/failure counts)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Episode {
    /// Unique identifier for this episode
    pub id: String,
    /// The user's intent (query/goal)
    pub intent: String,
    /// Semantic embedding of the intent
    pub intent_embedding: Vec<f32>,
    /// The actual experience (response/action taken)
    pub experience: String,
    /// The outcome (success indicator, error message, etc.)
    pub outcome: String,
    /// Current Q-value (learned utility, initialized to 0.5)
    pub q_value: f32,
    /// Number of successful retrievals
    pub success_count: u32,
    /// Number of failed retrievals
    pub failure_count: u32,
    /// Creation timestamp (Unix milliseconds)
    pub created_at: i64,
    /// Logical memory scope (for example, `session_id`) used for isolation.
    #[serde(default = "default_episode_scope")]
    pub scope: String,
}

impl Episode {
    /// Normalize an episode scope key.
    #[must_use]
    pub fn normalize_scope(scope: &str) -> String {
        let normalized = scope.trim();
        if normalized.is_empty() {
            GLOBAL_EPISODE_SCOPE.to_string()
        } else {
            normalized.to_string()
        }
    }

    /// Return scope key with legacy fallback when field is empty.
    #[must_use]
    pub fn scope_key(&self) -> &str {
        let scope = self.scope.trim();
        if scope.is_empty() {
            GLOBAL_EPISODE_SCOPE
        } else {
            self.scope.as_str()
        }
    }

    /// Create a new episode with default Q-value (0.5).
    #[must_use]
    pub fn new(
        id: String,
        intent: String,
        intent_embedding: Vec<f32>,
        experience: String,
        outcome: String,
    ) -> Self {
        Self::new_scoped(
            id,
            intent,
            intent_embedding,
            experience,
            outcome,
            GLOBAL_EPISODE_SCOPE.to_string(),
        )
    }

    /// Create a new episode bound to a logical scope.
    #[must_use]
    pub fn new_scoped(
        id: String,
        intent: String,
        intent_embedding: Vec<f32>,
        experience: String,
        outcome: String,
        scope: String,
    ) -> Self {
        Self {
            id,
            intent,
            intent_embedding,
            experience,
            outcome,
            q_value: 0.5, // Initial Q-value (neutral)
            success_count: 0,
            failure_count: 0,
            created_at: Utc::now().timestamp_millis(),
            scope: Self::normalize_scope(&scope),
        }
    }

    /// Calculate the utility of this episode.
    ///
    /// Utility is computed as: `success_rate * q_value`
    /// - `success_rate = success / (success + failure + 1)` to avoid division by zero
    /// - This gives higher weight to episodes with more successes
    #[must_use]
    #[allow(clippy::cast_precision_loss)]
    pub fn utility(&self) -> f32 {
        let total = (self.success_count + self.failure_count) as f32 + 1.0;
        let success_rate = (self.success_count as f32 + 1.0) / total;
        success_rate * self.q_value
    }

    /// Update success count and recalculate Q-value.
    pub fn mark_success(&mut self) {
        self.success_count += 1;
    }

    /// Update failure count and recalculate Q-value.
    pub fn mark_failure(&mut self) {
        self.failure_count += 1;
    }

    /// Get the total number of uses.
    #[must_use]
    pub fn total_uses(&self) -> u32 {
        self.success_count + self.failure_count
    }

    /// Check if this episode has been validated (used at least once).
    #[must_use]
    pub fn is_validated(&self) -> bool {
        self.total_uses() > 0
    }

    /// Apply time-based decay to the Q-value.
    ///
    /// `Q_decay = Q * decay_factor^(age_hours)`.
    ///
    /// Args:
    /// - `decay_factor`: Decay per hour (e.g., 0.95 means 5% decay per hour)
    /// - `current_time`: Current timestamp in milliseconds
    ///
    /// Returns:
    /// - Decayed Q-value (moves towards 0.5 over time)
    #[allow(clippy::cast_precision_loss)]
    pub fn apply_time_decay(&mut self, decay_factor: f32, current_time: i64) {
        let age_hours = (current_time - self.created_at) as f32 / (1000.0 * 60.0 * 60.0);
        if age_hours > 0.0 {
            let decay = decay_factor.powf(age_hours);
            // Decay towards 0.5 (neutral value)
            self.q_value = 0.5 + (self.q_value - 0.5) * decay;
        }
    }

    /// Get the age of this episode in hours.
    #[must_use]
    #[allow(clippy::cast_precision_loss)]
    pub fn age_hours(&self, current_time: i64) -> f32 {
        (current_time - self.created_at) as f32 / (1000.0 * 60.0 * 60.0)
    }
}
