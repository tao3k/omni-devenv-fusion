//! Compute kernels for fusion: RRF term (scalar + batch) and distance→score.
//!
//! Single swap-in points for the formulas; SIMD or Arrow compute can replace these later.

/// RRF term: `1 / (k + rank + 1)`.
///
/// Used by basic RRF, weighted RRF, adaptive RRF, and entity-aware fusion.
#[inline]
#[must_use]
pub fn rrf_term(k: f32, rank: usize) -> f32 {
    let rank_f32 = f32::from(u16::try_from(rank).unwrap_or(u16::MAX));
    1.0 / (k + rank_f32 + 1.0)
}

/// Batch RRF kernel: compute RRF term for each rank. Array-in, array-out.
///
/// `rrf_scores[i] = 1 / (k + ranks[i] + 1)`. Enables single-pass score computation
/// when ranks are already collected (e.g. from fusion map iteration).
#[inline]
#[must_use]
pub fn rrf_term_batch(ranks: &[usize], k: f32) -> Vec<f32> {
    ranks.iter().map(|&r| rrf_term(k, r)).collect()
}

/// Distance to normalized score: `1 / (1 + distance)`.
///
/// Used when exposing a 0–1 score from Lance distance (e.g. JSON output).
#[inline]
#[must_use]
pub fn distance_to_score(distance: f64) -> f64 {
    1.0 / (1.0 + distance.max(0.0))
}

#[cfg(test)]
mod tests {
    use super::{distance_to_score, rrf_term, rrf_term_batch};

    #[test]
    fn test_rrf_term() {
        assert!((rrf_term(10.0, 0) - (1.0 / 11.0)).abs() < 1e-6);
        assert!((rrf_term(10.0, 1) - (1.0 / 12.0)).abs() < 1e-6);
    }

    #[test]
    fn test_rrf_term_batch() {
        let ranks = [0_usize, 1, 2];
        let scores = rrf_term_batch(&ranks, 10.0);
        assert_eq!(scores.len(), 3);
        assert!((scores[0] - (1.0 / 11.0)).abs() < 1e-6);
        assert!((scores[1] - (1.0 / 12.0)).abs() < 1e-6);
        assert!((scores[2] - (1.0 / 13.0)).abs() < 1e-6);
    }

    #[test]
    fn test_distance_to_score() {
        assert!((distance_to_score(0.0) - 1.0).abs() < 1e-6);
        assert!((distance_to_score(1.0) - 0.5).abs() < 1e-6);
        assert!(distance_to_score(-0.5) <= 1.0);
    }
}
