//! Python bindings for Rust Event Bus
//!
//! Provides synchronous and asynchronous interfaces for consuming events
//! from the Rust tokio broadcast channel.

use omni_events::{EventBus, GLOBAL_BUS, OmniEvent};
use pyo3::prelude::*;
use serde_json::json;
use std::sync::Arc;

/// Python representation of an event
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyOmniEvent {
    /// Unique event identifier
    #[pyo3(get)]
    pub id: String,
    /// Event source (e.g., "watcher", "kernel")
    #[pyo3(get)]
    pub source: String,
    /// Event topic (e.g., "file/changed")
    #[pyo3(get)]
    pub topic: String,
    /// Event payload as JSON string
    #[pyo3(get)]
    pub payload: String,
    /// Unix timestamp in seconds
    #[pyo3(get)]
    pub timestamp: f64,
}

impl From<OmniEvent> for PyOmniEvent {
    fn from(e: OmniEvent) -> Self {
        PyOmniEvent {
            id: e.id,
            source: e.source,
            topic: e.topic,
            payload: e.payload.to_string(),
            timestamp: e.timestamp.timestamp_millis() as f64 / 1000.0,
        }
    }
}

#[pymethods]
impl PyOmniEvent {
    /// Parse payload as JSON dict
    fn get_payload(&self) -> PyResult<String> {
        // Return JSON string, let Python parse it
        Ok(self.payload.clone())
    }
}

/// Event Bus wrapper for Python (instance-based)
#[pyclass]
pub struct PyEventBus {
    bus: Arc<EventBus>,
}

#[pymethods]
impl PyEventBus {
    #[new]
    #[pyo3(signature = (capacity=None))]
    fn new(capacity: Option<usize>) -> Self {
        let cap = capacity.unwrap_or(2048);
        Self {
            bus: Arc::new(EventBus::new(cap)),
        }
    }

    /// Publish an event
    #[pyo3(signature = (source, topic, payload_json))]
    fn publish(&self, source: String, topic: String, payload_json: String) -> PyResult<usize> {
        let payload: serde_json::Value = serde_json::from_str(&payload_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {}", e)))?;

        let count = self.bus.publish(OmniEvent::new(&source, &topic, payload));
        Ok(count)
    }

    /// Emit a simple event with string message
    #[pyo3(signature = (source, topic, message))]
    fn emit(&self, source: String, topic: String, message: String) -> PyResult<usize> {
        let payload = json!({ "message": message });
        let count = self.bus.publish(OmniEvent::new(&source, &topic, payload));
        Ok(count)
    }

    /// Get current subscriber count
    fn subscriber_count(&self) -> usize {
        self.bus.subscriber_count()
    }

    /// Get bus capacity
    fn capacity(&self) -> usize {
        self.bus.capacity()
    }
}

/// Global event bus (singleton)
#[pyclass]
pub struct PyGlobalEventBus;

#[pymethods]
impl PyGlobalEventBus {
    /// Publish to the global bus
    #[staticmethod]
    #[pyo3(signature = (source, topic, payload_json))]
    fn publish(source: String, topic: String, payload_json: String) -> PyResult<usize> {
        let payload: serde_json::Value = serde_json::from_str(&payload_json)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {}", e)))?;

        let count = GLOBAL_BUS.publish(OmniEvent::new(&source, &topic, payload));
        Ok(count)
    }

    /// Emit a simple string event
    #[staticmethod]
    #[pyo3(signature = (source, topic, message))]
    fn emit(source: String, topic: String, message: String) -> PyResult<usize> {
        let payload = json!({ "message": message });
        let count = GLOBAL_BUS.publish(OmniEvent::new(&source, &topic, payload));
        Ok(count)
    }

    /// Get global bus subscriber count
    #[staticmethod]
    fn subscriber_count() -> usize {
        GLOBAL_BUS.subscriber_count()
    }
}

use std::str::FromStr;

/// Helper function to create an event JSON string from Python dict
#[pyfunction]
#[pyo3(signature = (source, topic, payload_json))]
pub fn create_event(source: String, topic: String, payload_json: String) -> PyResult<String> {
    let payload = serde_json::Value::from_str(&payload_json)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))?;

    let event = OmniEvent::new(&source, &topic, payload);
    serde_json::to_string(&event)
        .map_err(|err| pyo3::exceptions::PyValueError::new_err(err.to_string()))
}

/// Module-level convenience functions
#[pyfunction]
#[pyo3(signature = (source, topic, payload_json))]
pub fn publish_event(source: String, topic: String, payload_json: String) -> PyResult<()> {
    let payload: serde_json::Value = serde_json::from_str(&payload_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid JSON: {}", e)))?;

    GLOBAL_BUS.publish(OmniEvent::new(&source, &topic, payload));
    Ok(())
}

/// Event topic constants
#[pyfunction]
/// Returns "file/changed" topic string
pub fn topic_file_changed() -> String {
    omni_events::topics::FILE_CHANGED.to_string()
}

/// Returns "file/created" topic string
#[pyfunction]
pub fn topic_file_created() -> String {
    omni_events::topics::FILE_CREATED.to_string()
}

/// Returns "file/deleted" topic string
#[pyfunction]
pub fn topic_file_deleted() -> String {
    omni_events::topics::FILE_DELETED.to_string()
}

/// Returns "agent/think" topic string
#[pyfunction]
pub fn topic_agent_think() -> String {
    omni_events::topics::AGENT_THINK.to_string()
}

/// Returns "agent/action" topic string
#[pyfunction]
pub fn topic_agent_action() -> String {
    omni_events::topics::AGENT_ACTION.to_string()
}

/// Returns "agent/result" topic string
#[pyfunction]
pub fn topic_agent_result() -> String {
    omni_events::topics::AGENT_RESULT.to_string()
}

/// Returns "system/ready" topic string
#[pyfunction]
pub fn topic_system_ready() -> String {
    omni_events::topics::SYSTEM_READY.to_string()
}
