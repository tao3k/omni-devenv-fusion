//! Comprehensive tests for omni-tui state management

use std::io::Write;
use std::os::unix::net::UnixStream;
use std::time::Duration;
use tempfile::TempDir;

use omni_tui::socket::SocketEvent;
use omni_tui::state::{AppState, PanelType, ReceivedEvent};

/// Test: Basic state creation
#[test]
fn test_state_creation() {
    let state = AppState::new("Test App".to_string());
    assert_eq!(state.title(), "Test App");
    assert!(!state.should_quit());
    assert!(state.app().is_some());
    assert!(!state.is_socket_running());
}

/// Test: Empty state creation
#[test]
fn test_empty_state() {
    let state = AppState::empty();
    assert_eq!(state.title(), "Omni TUI");
    assert!(state.app().is_none());
    assert!(!state.should_quit());
}

/// Test: Status message operations
#[test]
fn test_status_message() {
    let mut state = AppState::new("Test".to_string());
    assert_eq!(state.status_message(), None);

    state.set_status("Test message");
    assert_eq!(state.status_message(), Some("Test message"));
}

/// Test: Quit functionality
#[test]
fn test_quit() {
    let mut state = AppState::new("Test".to_string());
    assert!(!state.should_quit());

    state.quit();
    assert!(state.should_quit());
}

/// Test: Panel addition
#[test]
fn test_panel_addition() {
    let mut state = AppState::new("Test".to_string());
    assert_eq!(state.app().unwrap().panels().len(), 0);

    state.add_result("Test Panel", "Test Content");
    assert_eq!(state.app().unwrap().panels().len(), 1);
}

/// Test: App state cloning
#[test]
fn test_state_clone() {
    let state = AppState::new("Test".to_string());
    let cloned = state.clone();
    assert_eq!(cloned.title(), state.title());
}

/// Test: Socket server integration
#[test]
fn test_socket_server_integration() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("integration.sock");
    let socket_str = socket_path.to_str().unwrap();

    let mut state = AppState::new("Test".to_string());
    assert!(!state.is_socket_running());

    state
        .start_socket_server(socket_str)
        .expect("Failed to start");
    assert!(state.is_socket_running());
    assert!(socket_path.exists());

    state.stop_socket_server();
    assert!(!state.is_socket_running());
}

/// Test: Received events storage
#[test]
fn test_received_events_storage() {
    let state = AppState::new("Test".to_string());
    assert!(state.received_events().is_empty());
}

/// Test: Socket event handling
#[test]
fn test_socket_event_handling() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("events.sock");
    let socket_str = socket_path.to_str().unwrap();

    let mut state = AppState::new("Test".to_string());
    state
        .start_socket_server(socket_str)
        .expect("Failed to start");

    let event = SocketEvent {
        source: "omega".to_string(),
        topic: "omega/mission/start".to_string(),
        payload: serde_json::json!({"goal": "test goal"}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };

    let mut stream = UnixStream::connect(&socket_path).expect("Connect failed");
    let json = serde_json::to_string(&event).expect("Serialize failed");
    stream.write_all(json.as_bytes()).expect("Write failed");
    stream.write_all(b"\n").expect("Write newline failed");

    std::thread::sleep(Duration::from_millis(100));

    state.stop_socket_server();

    let events = state.received_events();
    assert!(events.len() >= 1);
}

/// Test: Multiple mission events
#[test]
fn test_mission_events() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("missions.sock");
    let socket_str = socket_path.to_str().unwrap();

    let mut state = AppState::new("Test".to_string());
    state
        .start_socket_server(socket_str)
        .expect("Failed to start");

    for (i, &(source, topic, _)) in [
        ("omega", "omega/mission/start", "Mission 1"),
        ("omega", "omega/semantic/scan", "Scanning..."),
        ("omega", "omega/mission/complete", "Done"),
    ]
    .iter()
    .enumerate()
    {
        let event = SocketEvent {
            source: source.to_string(),
            topic: topic.to_string(),
            payload: serde_json::json!({"index": i}),
            timestamp: "2026-01-31T12:00:00Z".to_string(),
        };

        let mut stream = UnixStream::connect(&socket_path).expect("Connect failed");
        let json = serde_json::to_string(&event).expect("Serialize failed");
        stream.write_all(json.as_bytes()).expect("Write failed");
        stream.write_all(b"\n").expect("Write newline failed");

        std::thread::sleep(Duration::from_millis(20));
    }

    std::thread::sleep(Duration::from_millis(200));

    state.stop_socket_server();

    let received = state.received_events();
    assert!(received.len() >= 3);
}

/// Test: AppState Default implementation
#[test]
fn test_state_default() {
    let state = AppState::default();
    assert_eq!(state.title(), "Omni TUI");
    assert!(!state.should_quit());
}

/// Test: Panel type enum
#[test]
fn test_panel_types() {
    assert_eq!(PanelType::Result, PanelType::Result);
    assert_eq!(PanelType::Log, PanelType::Log);
    assert_eq!(PanelType::Error, PanelType::Error);
}

/// Test: ReceivedEvent clone and debug
#[test]
fn test_received_event_traits() {
    let event = ReceivedEvent {
        source: "test".to_string(),
        topic: "test/topic".to_string(),
        payload: serde_json::json!({"key": "value"}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };

    let cloned = event.clone();
    assert_eq!(cloned.source, event.source);

    let debug_str = format!("{:?}", event);
    assert!(debug_str.contains("test"));
}

/// Test: Event processing with tick
#[test]
fn test_event_processing_tick() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("tick.sock");
    let socket_str = socket_path.to_str().unwrap();

    let mut state = AppState::new("Test".to_string());
    state
        .start_socket_server(socket_str)
        .expect("Failed to start");

    let event = SocketEvent {
        source: "test".to_string(),
        topic: "test/event".to_string(),
        payload: serde_json::json!({"test": true}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };

    let mut stream = UnixStream::connect(&socket_path).expect("Connect failed");
    let json = serde_json::to_string(&event).expect("Serialize failed");
    stream.write_all(json.as_bytes()).expect("Write failed");
    stream.write_all(b"\n").expect("Write newline failed");

    std::thread::sleep(Duration::from_millis(100));

    state.on_tick();
    state.stop_socket_server();
}

/// Test: Large number of events
#[test]
fn test_many_events() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("many.sock");
    let socket_str = socket_path.to_str().unwrap();

    let mut state = AppState::new("Test".to_string());
    state
        .start_socket_server(socket_str)
        .expect("Failed to start");

    for i in 0..20 {
        let event = SocketEvent {
            source: "test".to_string(),
            topic: format!("test/event/{}", i),
            payload: serde_json::json!({"index": i}),
            timestamp: format!("2026-01-31T12:00:{:02}Z", i),
        };

        let mut stream = UnixStream::connect(&socket_path).expect("Connect failed");
        let json = serde_json::to_string(&event).expect("Serialize failed");
        stream.write_all(json.as_bytes()).expect("Write failed");
        stream.write_all(b"\n").expect("Write newline failed");
    }

    std::thread::sleep(Duration::from_millis(300));

    state.stop_socket_server();

    let events = state.received_events();
    assert!(
        events.len() >= 19,
        "Expected ~20 events, got {}",
        events.len()
    );
}

/// Test: Stop server when not running
#[test]
fn test_stop_when_not_running() {
    let mut state = AppState::new("Test".to_string());
    state.stop_socket_server();
    assert!(!state.is_socket_running());
}

/// Test: Event with special characters
#[test]
fn test_special_characters() {
    let temp_dir = TempDir::new().unwrap();
    let socket_path = temp_dir.path().join("special.sock");
    let socket_str = socket_path.to_str().unwrap();

    let mut state = AppState::new("Test".to_string());
    state
        .start_socket_server(socket_str)
        .expect("Failed to start");

    let event = SocketEvent {
        source: "test".to_string(),
        topic: "test/special".to_string(),
        payload: serde_json::json!({"text": "Hello 世界 🌍"}),
        timestamp: "2026-01-31T12:00:00Z".to_string(),
    };

    let mut stream = UnixStream::connect(&socket_path).expect("Connect failed");
    let json = serde_json::to_string(&event).expect("Serialize failed");
    stream.write_all(json.as_bytes()).expect("Write failed");
    stream.write_all(b"\n").expect("Write newline failed");

    std::thread::sleep(Duration::from_millis(100));

    state.stop_socket_server();

    let events = state.received_events();
    assert_eq!(events.len(), 1);
    assert!(events[0].payload["text"].as_str().unwrap().contains("世界"));
}
