//! TwoPhaseSearch tests.

use omni_memory::{Episode, IntentEncoder, QTable, TwoPhaseSearch};
use std::sync::Arc;

fn create_test_episodes() -> Vec<Episode> {
    let encoder = IntentEncoder::new(128);
    vec![
        Episode::new(
            "ep-0".to_string(),
            "debug network timeout".to_string(),
            encoder.encode("debug network timeout"),
            "Checked DNS settings".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-1".to_string(),
            "fix memory leak".to_string(),
            encoder.encode("fix memory leak"),
            "Found unbounded cache".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-2".to_string(),
            "handle async error".to_string(),
            encoder.encode("handle async error"),
            "Added error boundary".to_string(),
            "success".to_string(),
        ),
        Episode::new(
            "ep-3".to_string(),
            "optimize database query".to_string(),
            encoder.encode("optimize database query"),
            "Added index".to_string(),
            "failure".to_string(),
        ),
        Episode::new(
            "ep-4".to_string(),
            "debug network connection".to_string(),
            encoder.encode("debug network connection"),
            "Checked firewall".to_string(),
            "success".to_string(),
        ),
    ]
}

#[test]
fn test_two_phase_search() {
    let episodes = create_test_episodes();
    let q_table = Arc::new(QTable::new());
    let encoder = Arc::new(IntentEncoder::new(128));
    let search = TwoPhaseSearch::with_defaults(q_table.clone(), encoder);

    q_table.update("ep-0", 1.0);
    q_table.update("ep-1", 0.5);
    q_table.update("ep-2", 0.2);

    let results = search.search(&episodes, "debug network", None, None, Some(0.3));

    assert!(!results.is_empty());
}

#[test]
fn test_semantic_only() {
    let episodes = create_test_episodes();
    let q_table = Arc::new(QTable::new());
    let encoder = Arc::new(IntentEncoder::new(128));
    let search = TwoPhaseSearch::with_defaults(q_table.clone(), encoder);

    let results = search.search(&episodes, "debug network", None, None, Some(0.0));

    assert!(!results.is_empty());
}

#[test]
fn test_q_only() {
    let episodes = create_test_episodes();
    let q_table = Arc::new(QTable::new());
    let encoder = Arc::new(IntentEncoder::new(128));
    let search = TwoPhaseSearch::with_defaults(q_table.clone(), encoder);

    q_table.update("ep-2", 1.0);

    let results = search.search(&episodes, "random query", None, None, Some(1.0));

    assert!(!results.is_empty());
}

#[test]
fn test_calculate_score() {
    let score = omni_memory::calculate_score(0.8, 0.5, 0.5);
    assert!((score - 0.65).abs() < 0.001);
}
