//! Episode tests.

use omni_memory::Episode;

#[test]
fn test_episode_creation() {
    let episode = Episode::new(
        "ep-001".to_string(),
        "debug network error".to_string(),
        vec![0.1, 0.2, 0.3],
        "Checked firewall rules".to_string(),
        "success".to_string(),
    );

    assert_eq!(episode.id, "ep-001");
    assert_eq!(episode.q_value, 0.5);
    assert_eq!(episode.success_count, 0);
    assert_eq!(episode.failure_count, 0);
}

#[test]
fn test_utility_calculation() {
    let mut episode = Episode::new(
        "ep-001".to_string(),
        "test intent".to_string(),
        vec![0.1, 0.2],
        "test experience".to_string(),
        "success".to_string(),
    );

    let initial_util = episode.utility();
    assert!(initial_util > 0.0);

    episode.mark_success();
    assert_eq!(episode.success_count, 1);

    episode.mark_failure();
    assert_eq!(episode.failure_count, 1);
}
