//! Tests for Timeline functionality in CheckpointStore

use crate::checkpoint::{CheckpointRecord, CheckpointStore, TimelineRecord};
use tempfile::TempDir;

#[tokio::test]
async fn test_timeline_record_creation() {
    let record = TimelineRecord {
        checkpoint_id: "test-checkpoint-123".to_string(),
        thread_id: "test-thread".to_string(),
        step: 0,
        timestamp: 1699000000.0,
        preview: "Test content preview...".to_string(),
        parent_checkpoint_id: Some("parent-123".to_string()),
        reason: Some("AutoFix".to_string()),
    };

    assert_eq!(record.checkpoint_id, "test-checkpoint-123");
    assert_eq!(record.thread_id, "test-thread");
    assert_eq!(record.step, 0);
    assert_eq!(record.timestamp, 1699000000.0);
    assert!(record.preview.contains("preview"));
    assert_eq!(record.parent_checkpoint_id, Some("parent-123".to_string()));
    assert_eq!(record.reason, Some("AutoFix".to_string()));
}

#[tokio::test]
async fn test_get_timeline_records_empty() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path().to_str().unwrap();

    let store: CheckpointStore = CheckpointStore::new(path, Some(768)).await.unwrap();
    let timeline: Vec<TimelineRecord> = store
        .get_timeline_records("test_table", "nonexistent_thread", 10)
        .await
        .unwrap();

    assert!(timeline.is_empty());
}

#[tokio::test]
async fn test_get_timeline_records_with_data() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path().to_str().unwrap();

    let store: CheckpointStore = CheckpointStore::new(path, Some(768)).await.unwrap();
    let table_name = "test_timeline_table";

    // Create test checkpoints
    let test_records: Vec<CheckpointRecord> = vec![
        CheckpointRecord {
            checkpoint_id: "checkpoint-1".to_string(),
            thread_id: "test-thread".to_string(),
            parent_id: None,
            timestamp: 1699000000.0,
            content: r#"{"step": 1, "data": "first"}"#.to_string(),
            embedding: None,
            metadata: Some(r#"{"reason": "initial"}"#.to_string()),
        },
        CheckpointRecord {
            checkpoint_id: "checkpoint-2".to_string(),
            thread_id: "test-thread".to_string(),
            parent_id: Some("checkpoint-1".to_string()),
            timestamp: 1699000001.0,
            content: r#"{"step": 2, "data": "second"}"#.to_string(),
            embedding: None,
            metadata: Some(r#"{"reason": "update"}"#.to_string()),
        },
        CheckpointRecord {
            checkpoint_id: "checkpoint-3".to_string(),
            thread_id: "test-thread".to_string(),
            parent_id: Some("checkpoint-2".to_string()),
            timestamp: 1699000002.0,
            content: r#"{"step": 3, "data": "third and longer content for preview truncation"}"#
                .to_string(),
            embedding: None,
            metadata: Some(r#"{"reason": "final"}"#.to_string()),
        },
    ];

    for record in &test_records {
        store.save_checkpoint(table_name, record).await.unwrap();
    }

    // Get timeline
    let timeline: Vec<TimelineRecord> = store
        .get_timeline_records(table_name, "test-thread", 10)
        .await
        .unwrap();

    assert_eq!(timeline.len(), 3);

    // Verify ordering (newest first)
    assert_eq!(timeline[0].checkpoint_id, "checkpoint-3");
    assert_eq!(timeline[0].step, 0);
    assert_eq!(timeline[1].checkpoint_id, "checkpoint-2");
    assert_eq!(timeline[1].step, 1);
    assert_eq!(timeline[2].checkpoint_id, "checkpoint-1");
    assert_eq!(timeline[2].step, 2);

    // Verify parent_checkpoint_id tracking
    assert_eq!(
        timeline[0].parent_checkpoint_id,
        Some("checkpoint-2".to_string())
    );
    assert_eq!(
        timeline[1].parent_checkpoint_id,
        Some("checkpoint-1".to_string())
    );
    assert_eq!(timeline[2].parent_checkpoint_id, None);

    // Verify reason parsing
    assert_eq!(timeline[0].reason, Some("final".to_string()));
    assert_eq!(timeline[1].reason, Some("update".to_string()));
    assert_eq!(timeline[2].reason, Some("initial".to_string()));

    // Verify preview truncation
    assert!(timeline[2].preview.len() <= 200);
    assert!(timeline[2].preview.ends_with("...") || timeline[2].preview.len() < 200);
}

#[tokio::test]
async fn test_get_timeline_records_limit() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path().to_str().unwrap();

    let store: CheckpointStore = CheckpointStore::new(path, Some(768)).await.unwrap();
    let table_name = "test_limit_table";

    // Create 5 checkpoints
    for i in 1..=5 {
        let record = CheckpointRecord {
            checkpoint_id: format!("checkpoint-{}", i),
            thread_id: "limited-thread".to_string(),
            parent_id: if i > 1 {
                Some(format!("checkpoint-{}", i - 1))
            } else {
                None
            },
            timestamp: 1699000000.0 + (i as f64),
            content: format!(r#"{{"step": {}}}"#, i),
            embedding: None,
            metadata: Some(r#"{}"#.to_string()),
        };
        store.save_checkpoint(table_name, &record).await.unwrap();
    }

    // Get with limit of 3
    let timeline: Vec<TimelineRecord> = store
        .get_timeline_records(table_name, "limited-thread", 3)
        .await
        .unwrap();

    assert_eq!(timeline.len(), 3);
    assert_eq!(timeline[0].checkpoint_id, "checkpoint-5");
    assert_eq!(timeline[2].checkpoint_id, "checkpoint-3");
}

#[tokio::test]
async fn test_get_timeline_records_thread_isolation() {
    let temp_dir = TempDir::new().unwrap();
    let path = temp_dir.path().to_str().unwrap();

    let store: CheckpointStore = CheckpointStore::new(path, Some(768)).await.unwrap();
    let table_name = "test_isolation_table";

    // Create checkpoints for two different threads
    for thread in ["thread-a", "thread-b"] {
        for i in 1..=3 {
            let record = CheckpointRecord {
                checkpoint_id: format!("{}-checkpoint-{}", thread, i),
                thread_id: thread.to_string(),
                parent_id: None,
                timestamp: 1699000000.0 + (i as f64),
                content: format!(r#"{{"thread": "{}"}}"#, thread),
                embedding: None,
                metadata: Some(r#"{}"#.to_string()),
            };
            store.save_checkpoint(table_name, &record).await.unwrap();
        }
    }

    // Get timeline for thread-a only
    let timeline_a: Vec<TimelineRecord> = store
        .get_timeline_records(table_name, "thread-a", 10)
        .await
        .unwrap();
    assert_eq!(timeline_a.len(), 3);
    assert!(timeline_a.iter().all(|e| e.thread_id == "thread-a"));

    // Get timeline for thread-b only
    let timeline_b: Vec<TimelineRecord> = store
        .get_timeline_records(table_name, "thread-b", 10)
        .await
        .unwrap();
    assert_eq!(timeline_b.len(), 3);
    assert!(timeline_b.iter().all(|e| e.thread_id == "thread-b"));
}
