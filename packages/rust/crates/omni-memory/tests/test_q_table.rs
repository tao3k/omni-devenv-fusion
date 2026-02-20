//! QTable tests.

use omni_memory::QTable;

#[test]
fn test_q_table_basic_update() {
    let q_table = QTable::new();

    assert_eq!(q_table.get_q("ep-001"), 0.5);

    let q_new = q_table.update("ep-001", 1.0);
    assert_eq!(q_new, 0.6);

    assert_eq!(q_table.get_q("ep-001"), 0.6);
}

#[test]
fn test_q_table_negative_reward() {
    let q_table = QTable::new();

    let q_new = q_table.update("ep-001", 0.0);
    assert_eq!(q_new, 0.4);
}

#[test]
fn test_q_table_clamping() {
    let q_table = QTable::with_params(0.5, 0.95);

    for _ in 0..10 {
        q_table.update("ep-001", 1.0);
    }

    assert!((q_table.get_q("ep-001") - 1.0).abs() < 0.01);

    for _ in 0..10 {
        q_table.update("ep-002", 0.0);
    }

    assert!((q_table.get_q("ep-002") - 0.0).abs() < 0.01);
}

#[test]
fn test_batch_update() {
    let q_table = QTable::new();

    let updates = vec![
        ("ep-001".to_string(), 1.0),
        ("ep-002".to_string(), 0.0),
        ("ep-003".to_string(), 0.5),
    ];

    let results = q_table.update_batch(&updates);

    assert_eq!(results.len(), 3);
    assert_eq!(q_table.get_q("ep-001"), 0.6);
    assert_eq!(q_table.get_q("ep-002"), 0.4);
    assert_eq!(q_table.get_q("ep-003"), 0.5);
}
