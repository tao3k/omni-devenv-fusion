use super::{sanitize_decay_factor, should_apply_decay};

#[test]
fn should_apply_decay_respects_interval() {
    assert!(!should_apply_decay(true, 4, 3));
    assert!(should_apply_decay(true, 4, 4));
    assert!(should_apply_decay(true, 4, 8));
}

#[test]
fn should_apply_decay_can_be_disabled() {
    assert!(!should_apply_decay(false, 1, 1));
}

#[test]
fn sanitize_decay_factor_clamps_range() {
    assert_eq!(sanitize_decay_factor(1.2), 0.9999);
    assert_eq!(sanitize_decay_factor(0.1), 0.5);
    assert_eq!(sanitize_decay_factor(f32::NAN), 0.985);
}
