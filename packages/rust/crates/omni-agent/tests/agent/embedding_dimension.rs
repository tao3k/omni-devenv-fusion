use super::repair_embedding_dimension;

#[test]
fn repair_embedding_dimension_preserves_exact_dimension() {
    let input = vec![0.2_f32, 0.4, 0.6, 0.8];
    let repaired = repair_embedding_dimension(&input, input.len());
    assert_eq!(repaired, input);
}

#[test]
fn repair_embedding_dimension_downsamples_and_normalizes() {
    let input: Vec<f32> = (0..1024).map(|idx| (idx as f32) / 1024.0).collect();
    let repaired = repair_embedding_dimension(&input, 384);
    assert_eq!(repaired.len(), 384);
    let norm = repaired
        .iter()
        .map(|value| value * value)
        .sum::<f32>()
        .sqrt();
    assert!((norm - 1.0).abs() < 1e-4);
}

#[test]
fn repair_embedding_dimension_upsamples_single_value() {
    let repaired = repair_embedding_dimension(&[0.5], 8);
    assert_eq!(repaired, vec![0.5; 8]);
}

#[test]
fn repair_embedding_dimension_handles_zero_target() {
    let repaired = repair_embedding_dimension(&[0.1, 0.2, 0.3], 0);
    assert!(repaired.is_empty());
}
