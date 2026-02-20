pub(crate) const EMBEDDING_SOURCE_EMBEDDING: &str = "embedding";
pub(crate) const EMBEDDING_SOURCE_EMBEDDING_REPAIRED: &str = "embedding_repaired";
pub(crate) const EMBEDDING_SOURCE_HASH: &str = "hash";

/// Resample an embedding vector to the target dimension.
///
/// This keeps semantic signal when the upstream embedding model dimension drifts
/// from configured memory dimension (for example 1024 -> 384).
pub(crate) fn repair_embedding_dimension(input: &[f32], target_dim: usize) -> Vec<f32> {
    if target_dim == 0 {
        return Vec::new();
    }
    if input.len() == target_dim {
        return input.to_vec();
    }
    if input.is_empty() {
        return vec![0.0; target_dim];
    }
    if input.len() == 1 {
        return vec![input[0]; target_dim];
    }
    if target_dim == 1 {
        let sum = input.iter().copied().sum::<f32>();
        let denom = input.len() as f32;
        return vec![sum / denom];
    }

    let source_max = (input.len() - 1) as f32;
    let target_max = (target_dim - 1) as f32;
    let mut repaired = Vec::with_capacity(target_dim);
    for idx in 0..target_dim {
        let position = (idx as f32 / target_max) * source_max;
        let left = position.floor() as usize;
        let right = position.ceil() as usize;
        if left == right {
            repaired.push(input[left]);
            continue;
        }
        let mix = position - (left as f32);
        let value = input[left] * (1.0 - mix) + input[right] * mix;
        repaired.push(value);
    }

    normalize(repaired)
}

fn normalize(mut values: Vec<f32>) -> Vec<f32> {
    let norm = values.iter().map(|value| value * value).sum::<f32>().sqrt();
    if norm <= f32::EPSILON {
        return values;
    }
    values.iter_mut().for_each(|value| *value /= norm);
    values
}

#[cfg(test)]
#[path = "../../tests/agent/embedding_dimension.rs"]
mod tests;
