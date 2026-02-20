//! IntentEncoder tests.

use omni_memory::IntentEncoder;

#[test]
fn test_encoder_creation() {
    let encoder = IntentEncoder::new(128);
    assert_eq!(encoder.dimension(), 128);
}

#[test]
fn test_encoding_deterministic() {
    let encoder = IntentEncoder::new(128);

    let embedding1 = encoder.encode("debug network error");
    let embedding2 = encoder.encode("debug network error");

    assert_eq!(embedding1, embedding2);
}

#[test]
fn test_encoding_different_intents() {
    let encoder = IntentEncoder::new(128);

    let embedding1 = encoder.encode("debug network error");
    let embedding2 = encoder.encode("fix memory leak");

    assert_ne!(embedding1, embedding2);
}

#[test]
fn test_cosine_similarity() {
    let encoder = IntentEncoder::new(128);

    let a = vec![1.0, 0.0, 0.0, 0.0];
    let b = vec![1.0, 0.0, 0.0, 0.0];
    let c = vec![0.0, 1.0, 0.0, 0.0];

    assert!((encoder.cosine_similarity(&a, &b) - 1.0).abs() < 0.001);
    assert!(encoder.cosine_similarity(&a, &c).abs() < 0.001);
}

#[test]
fn test_encoding_normalized() {
    let encoder = IntentEncoder::new(128);

    let embedding = encoder.encode("test intent");

    let norm: f32 = embedding.iter().map(|x| x * x).sum::<f32>().sqrt();
    assert!((norm - 1.0).abs() < 0.001);
}
