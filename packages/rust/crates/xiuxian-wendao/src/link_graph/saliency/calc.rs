use super::{DEFAULT_DECAY_RATE, DEFAULT_SALIENCY_BASE, LinkGraphSaliencyPolicy};

fn clamp_finite(value: f64, minimum: f64, maximum: f64) -> f64 {
    if !value.is_finite() {
        return minimum;
    }
    value.clamp(minimum, maximum)
}

/// Compute the next saliency score:
/// `S = clamp(S_base * exp(-lambda * delta_t_days) + alpha * ln(1 + activations), [min, max])`
#[must_use]
pub fn compute_link_graph_saliency(
    saliency_base: f64,
    decay_rate: f64,
    activation_count: u64,
    delta_t_days: f64,
    policy: LinkGraphSaliencyPolicy,
) -> f64 {
    let normalized = policy.normalized();
    let safe_base = if saliency_base.is_finite() {
        saliency_base.max(0.0)
    } else {
        DEFAULT_SALIENCY_BASE
    };
    let safe_decay = if decay_rate.is_finite() {
        decay_rate.max(0.0)
    } else {
        DEFAULT_DECAY_RATE
    };
    let safe_days = if delta_t_days.is_finite() {
        delta_t_days.max(0.0)
    } else {
        0.0
    };

    let decay = safe_base * (-safe_decay * safe_days).exp();
    let activation_boost = normalized.alpha * (1.0 + activation_count as f64).ln();
    clamp_finite(
        decay + activation_boost,
        normalized.minimum,
        normalized.maximum,
    )
}
