//! Comprehensive tests for omni-tui socket server
//!
//! Tests cover:
//! - Server lifecycle (start/stop)
//! - Event parsing and serialization
//! - Error conditions and edge cases

use std::sync::{Arc, Mutex};
use std::time::Duration;
use tempfile::TempDir;

use omni_tui::socket::{SocketEvent, SocketServer, send_event};

/// Test: Server creation and initial state
#[test]
fn test_server_creation() {
    let server = SocketServer::new("/tmp/test.sock");
    assert!(!server.is_running());
}

/// Test: Server start and stop
#[test]
fn test_server_start_stop() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("test.sock");

    let server = SocketServer::new(socket_path.to_str().unwrap());
    assert!(!server.is_running());

    let _handle = server.start().expect("Failed to start server");
    assert!(server.is_running());

    server.stop();
    assert!(!server.is_running());
}

/// Test: Server can be started multiple times (after stop)
#[test]
fn test_server_restart() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("restart_test.sock");

    let server = SocketServer::new(socket_path.to_str().unwrap());

    // First start
    let _handle = server.start().expect("First start failed");
    assert!(server.is_running());
    server.stop();
    assert!(!server.is_running());

    // Second start
    let _handle2 = server.start().expect("Second start failed");
    assert!(server.is_running());
    server.stop();
    assert!(!server.is_running());
}

/// Test: Event serialization and deserialization
#[test]
fn test_event_serde() {
    let event = SocketEvent {
        source: "omega".to_string(),
        topic: "omega/mission/start".to_string(),
        payload: serde_json::json!({"goal": "test mission"}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };

    let json = serde_json::to_string(&event).expect("Serialization failed");
    assert!(json.contains("\"source\":\"omega\""));
    assert!(json.contains("\"topic\":\"omega/mission/start\""));

    let parsed: SocketEvent = serde_json::from_str(&json).expect("Deserialization failed");
    assert_eq!(parsed.source, event.source);
    assert_eq!(parsed.topic, event.topic);
}

/// Test: Send and receive single event
#[test]
fn test_single_event_roundtrip() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("single.sock");
    let socket_str = socket_path.to_str().unwrap();

    let received = Arc::new(Mutex::new(Vec::new()));
    let received_clone = received.clone();

    let server = SocketServer::new(socket_str);
    server.set_event_callback(Box::new(move |event| {
        received_clone.lock().unwrap().push(event);
    }));

    let _handle = server.start().expect("Failed to start");
    std::thread::sleep(Duration::from_millis(50));

    let event = SocketEvent {
        source: "cortex".to_string(),
        topic: "cortex/task/start".to_string(),
        payload: serde_json::json!({"task_id": "task-123"}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };
    send_event(socket_str, &event).expect("Send failed");
    std::thread::sleep(Duration::from_millis(100));

    server.stop();

    let r = received.lock().unwrap();
    assert_eq!(r.len(), 1);
    assert_eq!(r[0].source, "cortex");
    assert_eq!(r[0].topic, "cortex/task/start");
}

/// Test: Send and receive multiple events
#[test]
fn test_multiple_events_roundtrip() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("multiple.sock");
    let socket_str = socket_path.to_str().unwrap();

    let received = Arc::new(Mutex::new(Vec::new()));
    let received_clone = received.clone();

    let server = SocketServer::new(socket_str);
    server.set_event_callback(Box::new(move |event| {
        received_clone.lock().unwrap().push(event);
    }));

    let _handle = server.start().expect("Failed to start");
    std::thread::sleep(Duration::from_millis(50));

    for i in 0..5 {
        let event = SocketEvent {
            source: "test".to_string(),
            topic: format!("test/event/{}", i),
            payload: serde_json::json!({"index": i}),
            timestamp: format!("2026-01-31T12:00:0{}Z", i),
        };
        send_event(socket_str, &event).expect("Send failed");
        std::thread::sleep(Duration::from_millis(10));
    }

    std::thread::sleep(Duration::from_millis(200));
    server.stop();

    let r = received.lock().unwrap();
    assert_eq!(r.len(), 5);
}

/// Test: Complex payload handling
#[test]
fn test_complex_payload() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("complex.sock");
    let socket_str = socket_path.to_str().unwrap();

    let received = Arc::new(Mutex::new(Vec::new()));
    let received_clone = received.clone();

    let server = SocketServer::new(socket_str);
    server.set_event_callback(Box::new(move |event| {
        received_clone.lock().unwrap().push(event);
    }));

    let _handle = server.start().expect("Failed to start");
    std::thread::sleep(Duration::from_millis(50));

    let event = SocketEvent {
        source: "omega".to_string(),
        topic: "omega/mission/complete".to_string(),
        payload: serde_json::json!({
            "result": {"success": true, "tasks_completed": 10},
            "metadata": {"duration_ms": 1500.5, "tags": ["a", "b", "c"]}
        }),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };
    send_event(socket_str, &event).expect("Send failed");
    std::thread::sleep(Duration::from_millis(100));

    server.stop();

    let r = received.lock().unwrap();
    assert_eq!(r.len(), 1);
    let payload = &r[0].payload;
    assert_eq!(payload["result"]["success"], true);
    assert_eq!(payload["metadata"]["tags"].as_array().unwrap().len(), 3);
}

/// Test: Large payload handling
#[test]
fn test_large_payload() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("large.sock");
    let socket_str = socket_path.to_str().unwrap();

    let received = Arc::new(Mutex::new(Vec::new()));
    let received_clone = received.clone();

    let server = SocketServer::new(socket_str);
    server.set_event_callback(Box::new(move |event| {
        received_clone.lock().unwrap().push(event);
    }));

    let _handle = server.start().expect("Failed to start");
    std::thread::sleep(Duration::from_millis(50));

    let large_data: Vec<String> = (0..1000).map(|i| format!("item_{}", i)).collect();
    let event = SocketEvent {
        source: "test".to_string(),
        topic: "test/large".to_string(),
        payload: serde_json::json!({"data": large_data, "items": 1000}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };
    send_event(socket_str, &event).expect("Send failed");
    std::thread::sleep(Duration::from_millis(100));

    server.stop();

    let r = received.lock().unwrap();
    assert_eq!(r.len(), 1);
    assert_eq!(r[0].payload["items"], 1000);
}

/// Test: Socket cleanup on drop
#[test]
fn test_socket_file_cleanup() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("cleanup.sock");
    let socket_str = socket_path.to_str().unwrap();

    {
        let server = SocketServer::new(socket_str);
        let _handle = server.start().expect("Failed to start");
        assert!(socket_path.exists());
    }

    let server = SocketServer::new(socket_str);
    let _handle = server.start().expect("Failed to start");
    server.stop();

    std::thread::sleep(Duration::from_millis(50));
    assert!(!socket_path.exists() || std::fs::remove_file(&socket_path).is_err());
}
