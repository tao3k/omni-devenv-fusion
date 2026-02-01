//! Application state management for TUI

use crate::components::{FoldablePanel, TuiApp};
use crate::socket::{SocketEvent, SocketServer};
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;

/// Type of panel for categorization
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanelType {
    /// Execution result panel
    Result,
    /// Log output panel
    Log,
    /// Progress indicator
    Progress,
    /// Error display
    Error,
    /// Custom panel
    Custom(&'static str),
}

/// Received event from socket
#[derive(Debug, Clone)]
pub struct ReceivedEvent {
    pub source: String,
    pub topic: String,
    pub payload: serde_json::Value,
    pub timestamp: String,
}

/// Main application state
#[derive(Debug, Clone)]
pub struct AppState {
    title: String,
    app: Option<TuiApp>,
    should_quit: bool,
    status_message: Option<String>,
    event_tx: Option<mpsc::Sender<String>>,
    event_bus: Option<broadcast::Sender<super::TuiEvent>>,
    socket_server: Option<SocketServer>,
    received_events: Arc<Mutex<Vec<ReceivedEvent>>>,
    processed_count: Arc<Mutex<usize>>,
}

impl AppState {
    /// Create a new application state
    pub fn new(title: String) -> Self {
        let title_clone = title.clone();
        Self {
            title,
            app: Some(TuiApp::new(title_clone)),
            should_quit: false,
            status_message: None,
            event_tx: None,
            event_bus: None,
            socket_server: None,
            received_events: Arc::new(Mutex::new(Vec::new())),
            processed_count: Arc::new(Mutex::new(0)),
        }
    }

    /// Create state without app (for testing)
    pub fn empty() -> Self {
        Self {
            title: "Omni TUI".to_string(),
            app: None,
            should_quit: false,
            status_message: None,
            event_tx: None,
            event_bus: None,
            socket_server: None,
            received_events: Arc::new(Mutex::new(Vec::new())),
            processed_count: Arc::new(Mutex::new(0)),
        }
    }

    /// Get title
    pub fn title(&self) -> &str {
        &self.title
    }

    /// Get status message
    pub fn status_message(&self) -> Option<&str> {
        self.status_message.as_deref()
    }

    /// Set status message
    pub fn set_status(&mut self, message: &str) {
        self.status_message = Some(message.to_string());
    }

    /// Get reference to app
    pub fn app(&self) -> Option<&TuiApp> {
        self.app.as_ref()
    }

    /// Get mutable reference to app
    pub fn app_mut(&mut self) -> Option<&mut TuiApp> {
        self.app.as_mut()
    }

    /// Set the app
    pub fn set_app(&mut self, app: TuiApp) {
        self.app = Some(app);
    }

    /// Check if should quit
    pub fn should_quit(&self) -> bool {
        self.should_quit
    }

    /// Request quit
    pub fn quit(&mut self) {
        self.should_quit = true;
    }

    /// Add a result panel
    pub fn add_result<S: Into<String>, C: Into<String>>(&mut self, title: S, content: C) {
        if let Some(app) = self.app.as_mut() {
            app.add_result(title, content);
        }
    }

    /// Add a panel with specific type
    pub fn add_panel(&mut self, panel: FoldablePanel, _panel_type: PanelType) {
        if let Some(app) = self.app.as_mut() {
            app.add_panel(panel);
        }
    }

    /// Handle tick event (called periodically)
    pub fn on_tick(&mut self) {
        let received = self.received_events.lock().unwrap();
        let processed = *self.processed_count.lock().unwrap();

        // Process only new events - clone them first to avoid borrow issues
        if processed < received.len() {
            let new_events: Vec<ReceivedEvent> = received.iter().skip(processed).cloned().collect();
            let new_count = received.len();
            drop(received); // Release lock before processing

            for event in new_events {
                self.on_socket_event(&event);
            }

            // Update processed count
            *self.processed_count.lock().unwrap() = new_count;
        }
    }

    /// Handle custom event from omni-events
    pub fn on_custom_event(&mut self, data: Vec<u8>) {
        // Parse and handle custom event data
        self.set_status(&format!("Received custom event: {} bytes", data.len()));
    }

    /// Connect to event bus for receiving omni-events
    pub fn connect_event_bus(&mut self, tx: broadcast::Sender<super::TuiEvent>) {
        self.event_bus = Some(tx);
    }

    /// Send event to UI
    pub fn send_event(&self, event: &str) {
        if let Some(tx) = &self.event_tx {
            let _ = tx.send(event.to_string());
        }
    }

    /// Start Unix socket server for receiving Python events
    pub fn start_socket_server(
        &mut self,
        socket_path: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let server = SocketServer::new(socket_path);
        let received_events = self.received_events.clone();

        server.set_event_callback(Box::new(move |event: SocketEvent| {
            let received = ReceivedEvent {
                source: event.source,
                topic: event.topic,
                payload: event.payload,
                timestamp: event.timestamp,
            };
            let mut events = received_events.lock().unwrap();
            events.push(received);
            // Keep only last 100 events
            if events.len() > 100 {
                events.remove(0);
            }
        }));

        server.start()?;
        self.socket_server = Some(server);
        self.set_status(&format!("Socket server listening on {}", socket_path));
        Ok(())
    }

    /// Stop the socket server
    pub fn stop_socket_server(&mut self) {
        if let Some(server) = self.socket_server.take() {
            server.stop();
            self.set_status("Socket server stopped");
        }
    }

    /// Get received events
    pub fn received_events(&self) -> Vec<ReceivedEvent> {
        let events = self.received_events.lock().unwrap();
        events.clone()
    }

    /// Check if socket server is running
    pub fn is_socket_running(&self) -> bool {
        self.socket_server
            .as_ref()
            .map_or(false, |s| s.is_running())
    }

    /// Handle socket event - update UI based on topic
    pub fn on_socket_event(&mut self, event: &ReceivedEvent) {
        // Update status message based on event topic
        let message = format!("[{}] {}", event.source, event.topic);
        self.set_status(&message);

        // Add result panel for mission events
        if event.topic.starts_with("omega/mission/") {
            let payload_str = serde_json::to_string_pretty(&event.payload).unwrap_or_default();
            self.add_result(format!("Mission: {}", event.topic), payload_str);
        }
    }
}

impl Default for AppState {
    fn default() -> Self {
        Self::new("Omni TUI".to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_app_state_creation() {
        let state = AppState::new("Test App".to_string());
        assert_eq!(state.title(), "Test App");
        assert!(!state.should_quit());
        assert!(state.app().is_some());
    }

    #[test]
    fn test_app_state_add_result() {
        let mut state = AppState::new("Test".to_string());
        state.add_result("Panel 1", "Content 1");

        let app = state.app().unwrap();
        assert_eq!(app.panels().len(), 1);
    }

    #[test]
    fn test_app_state_quit() {
        let mut state = AppState::new("Test".to_string());
        assert!(!state.should_quit());

        state.quit();
        assert!(state.should_quit());
    }
}
