//! High-Performance Event Bus for Agentic OS
//!
//! Provides a pub/sub event system backed by tokio's broadcast channel.
//! Used to decouple components: Watcher -> Cortex -> Kernel -> Agent.
//!
//! # Architecture
//!
//! ```text
//! Event (source, topic, payload)
//!      ↓
//! EventBus.publish() → broadcast::Sender
//!      ↓
//! Fan-out to multiple Subscribers
//!      ↓
//! Each component receives events asynchronously
//! ```

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;
use tokio::sync::broadcast;
use uuid::Uuid;

/// Core event model
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OmniEvent {
    /// Unique event identifier
    pub id: String,
    /// Event source (e.g., "watcher", "mcp:filesystem", "kernel")
    pub source: String,
    /// Event topic/category (e.g., "file/changed", "agent/thought")
    pub topic: String,
    /// Flexible JSON payload
    pub payload: Value,
    /// Event timestamp
    pub timestamp: DateTime<Utc>,
}

impl OmniEvent {
    /// Create a new event
    pub fn new(source: impl Into<String>, topic: impl Into<String>, payload: Value) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            source: source.into(),
            topic: topic.into(),
            payload,
            timestamp: Utc::now(),
        }
    }

    /// Create a simple string payload event
    pub fn with_string(source: &str, topic: &str, message: &str) -> Self {
        Self::new(source, topic, json!({ "message": message }))
    }

    /// Create a file-related event
    pub fn file_event(source: &str, topic: &str, path: &str, is_dir: bool) -> Self {
        Self::new(source, topic, json!({ "path": path, "is_dir": is_dir }))
    }
}

impl std::fmt::Display for OmniEvent {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "[{}] {} -> {}: {}",
            self.timestamp.format("%H:%M:%S"),
            self.source,
            self.topic,
            self.payload
        )
    }
}

/// High-performance async event bus
///
/// Uses `tokio::sync::broadcast` channel for:
/// - Thread-safe 1-to-Many fan-out
/// - Non-blocking publish
/// - Automatic cleanup on receiver drop
#[derive(Clone)]
pub struct EventBus {
    /// Broadcast sender (clonable for multiple publishers)
    tx: broadcast::Sender<OmniEvent>,
    /// Bus capacity for backpressure handling
    capacity: usize,
}

impl EventBus {
    /// Create a new event bus with specified capacity
    pub fn new(capacity: usize) -> Self {
        let (tx, _) = broadcast::channel(capacity);
        Self { tx, capacity }
    }

    /// Get the bus capacity
    pub fn capacity(&self) -> usize {
        self.capacity
    }

    /// Publish an event to all subscribers
    ///
    /// Returns the number of subscribers who received the event.
    /// Returns 0 if there are no subscribers (not an error).
    pub fn publish(&self, event: OmniEvent) -> usize {
        self.tx.send(event).unwrap_or(0)
    }

    /// Publish an event with topic and payload convenience
    pub fn emit(&self, source: &str, topic: &str, payload: Value) -> usize {
        self.publish(OmniEvent::new(source, topic, payload))
    }

    /// Subscribe to the event bus
    ///
    /// Returns a receiver that will receive all future events.
    /// Dropping the receiver automatically unsubscribes.
    pub fn subscribe(&self) -> broadcast::Receiver<OmniEvent> {
        self.tx.subscribe()
    }

    /// Get current subscriber count
    pub fn subscriber_count(&self) -> usize {
        self.tx.receiver_count()
    }
}

lazy_static::lazy_static! {
    /// Global event bus singleton
    pub static ref GLOBAL_BUS: Arc<EventBus> = Arc::new(EventBus::new(2048));
}

/// Convenience function to publish to the global bus
pub fn publish(source: &str, topic: &str, payload: Value) {
    let event = OmniEvent::new(source, topic, payload);
    let _ = GLOBAL_BUS.publish(event);
}

/// Convenience function to emit to the global bus
pub fn emit(source: &str, topic: &str, payload: Value) {
    GLOBAL_BUS.emit(source, topic, payload);
}

/// Get a subscriber for the global bus
pub fn subscribe() -> broadcast::Receiver<OmniEvent> {
    GLOBAL_BUS.subscribe()
}

/// Event topic constants for type-safe routing
pub mod topics {
    /// File changed event
    pub const FILE_CHANGED: &str = "file/changed";
    /// File created event
    pub const FILE_CREATED: &str = "file/created";
    /// File deleted event
    pub const FILE_DELETED: &str = "file/deleted";
    /// File renamed event
    pub const FILE_RENAMED: &str = "file/renamed";

    /// Agent think event
    pub const AGENT_THINK: &str = "agent/think";
    /// Agent action event
    pub const AGENT_ACTION: &str = "agent/action";
    /// Agent result event
    pub const AGENT_RESULT: &str = "agent/result";

    /// MCP request event
    pub const MCP_REQUEST: &str = "mcp/request";
    /// MCP response event
    pub const MCP_RESPONSE: &str = "mcp/response";

    /// System shutdown event
    pub const SYSTEM_SHUTDOWN: &str = "system/shutdown";
    /// System ready event
    pub const SYSTEM_READY: &str = "system/ready";

    /// Cortex index updated event
    pub const CORTEX_INDEX_UPDATED: &str = "cortex/index_updated";
    /// Cortex query event
    pub const CORTEX_QUERY: &str = "cortex/query";
}

/// Event source constants
pub mod sources {
    /// File watcher source
    pub const WATCHER: &str = "watcher";
    /// Kernel source
    pub const KERNEL: &str = "kernel";
    /// MCP server source
    pub const MCP_SERVER: &str = "mcp:server";
    /// Cortex source
    pub const CORTEX: &str = "cortex";
    /// Agent source
    pub const AGENT: &str = "agent";
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_event_creation() {
        let event = OmniEvent::new("test", "test/topic", json!({"key": "value"}));
        assert_eq!(event.source, "test");
        assert_eq!(event.topic, "test/topic");
        assert!(!event.id.is_empty());
        assert!(event.timestamp <= Utc::now());
    }

    #[test]
    fn test_file_event() {
        let event = OmniEvent::file_event("watcher", "file/changed", "/path/to/file.py", false);
        assert_eq!(event.source, "watcher");
        assert_eq!(event.topic, "file/changed");
        assert_eq!(event.payload["path"], "/path/to/file.py");
        assert_eq!(event.payload["is_dir"], false);
    }

    #[tokio::test]
    async fn test_event_bus_publish() {
        let bus = EventBus::new(10);
        let mut rx = bus.subscribe();

        bus.publish(OmniEvent::new("test", "topic", json!({"data": 42})));

        let received = rx.recv().await.unwrap();
        assert_eq!(received.source, "test");
        assert_eq!(received.topic, "topic");
    }

    #[tokio::test]
    async fn test_multiple_subscribers() {
        let bus = EventBus::new(10);
        let mut rx1 = bus.subscribe();
        let mut rx2 = bus.subscribe();

        bus.publish(OmniEvent::new("test", "topic", json!({"msg": "hello"})));

        let received1 = rx1.recv().await.unwrap();
        let received2 = rx2.recv().await.unwrap();

        assert_eq!(received1.payload, received2.payload);
    }

    #[tokio::test]
    async fn test_subscriber_count() {
        let bus = EventBus::new(10);
        assert_eq!(bus.subscriber_count(), 0);

        let _rx = bus.subscribe();
        assert_eq!(bus.subscriber_count(), 1);

        let _rx2 = bus.subscribe();
        assert_eq!(bus.subscriber_count(), 2);
    }
}
