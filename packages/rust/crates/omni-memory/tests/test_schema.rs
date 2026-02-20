//! Schema validation tests for EpisodeMetadata.

use omni_memory::EpisodeMetadata;

#[test]
fn test_metadata_validation_valid() {
    let m = EpisodeMetadata::from_episode("exp", "ok", 0.5, 0, 0, 12345).unwrap();
    assert_eq!(m.q_value, 0.5);
    assert_eq!(m.experience, "exp");
}

#[test]
fn test_metadata_validation_q_out_of_range() {
    assert!(EpisodeMetadata::from_episode("a", "b", 1.5, 0, 0, 0).is_err());
    assert!(EpisodeMetadata::from_episode("a", "b", -0.1, 0, 0, 0).is_err());
}

#[test]
fn test_metadata_roundtrip() {
    let m = EpisodeMetadata::from_episode("exp", "out", 0.7, 1, 2, 999).unwrap();
    let json = m.to_json().unwrap();
    let m2 = EpisodeMetadata::from_json(&json).unwrap();
    assert_eq!(m.experience, m2.experience);
    assert_eq!(m.q_value, m2.q_value);
}

#[test]
fn test_metadata_empty_json_fails() {
    assert!(EpisodeMetadata::from_json("").is_err());
    assert!(EpisodeMetadata::from_json("   ").is_err());
}

#[test]
fn test_metadata_invalid_json_fails() {
    assert!(EpisodeMetadata::from_json("{invalid").is_err());
}

#[test]
fn test_metadata_missing_required_fields_fails() {
    assert!(EpisodeMetadata::from_json(r#"{"experience":"x","outcome":"y"}"#).is_err());
    assert!(EpisodeMetadata::from_json("{}").is_err());
}

#[test]
fn test_metadata_invalid_q_value_in_json_fails() {
    let json = r#"{"experience":"x","outcome":"y","q_value":1.5,"success_count":0,"failure_count":0,"created_at":0}"#;
    assert!(EpisodeMetadata::from_json(json).is_err());
}
