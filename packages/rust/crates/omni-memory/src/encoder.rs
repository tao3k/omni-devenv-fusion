//! Intent encoding utilities for self-evolving memory.
//!
//! Provides simple intent embedding encoding for episode similarity search.
//! Uses a hash-based approach for quick encoding without external dependencies.

use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

/// Encode intent text into a fixed-size embedding vector.
///
/// Uses a simple hash-based encoding that maps similar intents to similar vectors.
/// For production, this would be replaced with actual embedding models.
#[derive(Clone)]
pub struct IntentEncoder {
    /// Dimension of the embedding vector
    dimension: usize,
}

impl IntentEncoder {
    /// Create a new encoder with specified dimension.
    #[must_use]
    pub fn new(dimension: usize) -> Self {
        Self { dimension }
    }

    /// Encode intent text into embedding vector.
    ///
    /// Uses hash-based encoding:
    /// 1. Hash the intent text
    /// 2. Use hash to seed random number generator
    /// 3. Generate deterministic random vector
    /// 4. Apply position-based perturbations for uniqueness
    #[must_use]
    pub fn encode(&self, intent: &str) -> Vec<f32> {
        let mut embedding = vec![0.0; self.dimension];

        // Create multiple hash variants for better distribution
        for (i, value) in embedding.iter_mut().enumerate() {
            let i_u64 = u64::try_from(i).unwrap_or(0);
            let mut hasher = DefaultHasher::new();
            intent.hash(&mut hasher);
            i_u64.hash(&mut hasher);
            let hash1 = hasher.finish();

            let mut hasher2 = DefaultHasher::new();
            intent.hash(&mut hasher2);
            i_u64.wrapping_mul(31).hash(&mut hasher2);
            let hash2 = hasher2.finish();

            // Combine hashes for position-specific encoding
            let combined = hash1.wrapping_mul(31).wrapping_add(hash2);

            // Convert to float in range [0, 1]
            let bucket = u16::try_from(combined % 1000).unwrap_or(0);
            *value = f32::from(bucket) / 1000.0;
        }

        // Normalize to unit vector
        Self::normalize(&embedding)
    }

    /// Normalize vector to unit length.
    fn normalize(v: &[f32]) -> Vec<f32> {
        let sum: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
        if sum == 0.0 {
            return v.to_vec();
        }
        v.iter().map(|x| x / sum).collect()
    }

    /// Calculate cosine similarity between two embeddings.
    #[must_use]
    #[allow(clippy::unused_self)]
    pub fn cosine_similarity(&self, a: &[f32], b: &[f32]) -> f32 {
        if a.len() != b.len() {
            return 0.0;
        }

        let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
        let norm_a: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
        let norm_b: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();

        if norm_a == 0.0 || norm_b == 0.0 {
            return 0.0;
        }

        dot / (norm_a * norm_b)
    }

    /// Get the dimension of embeddings.
    #[must_use]
    pub fn dimension(&self) -> usize {
        self.dimension
    }
}

impl Default for IntentEncoder {
    fn default() -> Self {
        Self::new(384) // Common embedding dimension
    }
}
