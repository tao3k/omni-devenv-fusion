//! Application state management for TUI
//!
//! Provides:
//! - TaskItem: Individual task representation
//! - ExecutionState: Task graph and execution tracking
//! - LogWindow: Bounded rolling log (max 1000 lines)
//! - AppState: Main application state with mpsc event receiver

use crate::components::{FoldablePanel, TuiApp};
use crate::socket::{SocketEvent, SocketServer};
use ratatui::style::Color;
use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::sync::mpsc;
use std::sync::{Arc, Mutex};
use tokio::sync::broadcast;

/// Maximum number of log lines to keep in the rolling window
pub const MAX_LOG_LINES: usize = 1000;

/// Task status enum for visualization
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TaskStatus {
    #[serde(rename = "pending")]
    Pending,
    #[serde(rename = "running")]
    Running,
    #[serde(rename = "success")]
    Success,
    #[serde(rename = "failed")]
    Failed,
    #[serde(rename = "retry")]
    Retry,
}

/// Individual task item for the task list
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskItem {
    pub id: String,
    pub description: String,
    pub command: String,
    pub status: TaskStatus,
    pub duration_ms: Option<f64>,
    pub output_preview: Option<String>,
    pub retry_count: usize,
    pub error: Option<String>,
}

impl TaskItem {
    /// Create a new pending task
    pub fn new(id: String, description: String, command: String) -> Self {
        Self {
            id,
            description,
            command,
            status: TaskStatus::Pending,
            duration_ms: None,
            output_preview: None,
            retry_count: 0,
            error: None,
        }
    }

    /// Get status symbol for display
    pub fn status_symbol(&self) -> &'static str {
        match self.status {
            TaskStatus::Pending => "○",
            TaskStatus::Running => "◉",
            TaskStatus::Success => "✓",
            TaskStatus::Failed => "✗",
            TaskStatus::Retry => "↻",
        }
    }

    /// Get status color
    pub fn status_color(&self) -> Color {
        match self.status {
            TaskStatus::Pending => Color::DarkGray,
            TaskStatus::Running => Color::Yellow,
            TaskStatus::Success => Color::Green,
            TaskStatus::Failed => Color::Red,
            TaskStatus::Retry => Color::Magenta,
        }
    }
}

/// Execution state for tracking task graph execution
#[derive(Debug, Clone, Default)]
pub struct ExecutionState {
    /// All tasks in the execution
    pub tasks: Vec<TaskItem>,
    /// Map from task_id to index in tasks vector (O(1) lookup)
    pub task_index: std::collections::HashMap<String, usize>,
    /// Current execution ID
    pub execution_id: Option<String>,
    /// Total tasks count
    pub total_tasks: usize,
    /// Completed tasks count
    pub completed_tasks: usize,
    /// Failed tasks count
    pub failed_tasks: usize,
    /// Current executing group
    pub current_group: Option<String>,
    /// Execution start time
    pub start_time: Option<std::time::Instant>,
    /// Whether execution is complete
    pub is_complete: bool,
}

impl ExecutionState {
    /// Create new execution state
    pub fn new() -> Self {
        Self {
            tasks: Vec::new(),
            task_index: std::collections::HashMap::new(),
            execution_id: None,
            total_tasks: 0,
            completed_tasks: 0,
            failed_tasks: 0,
            current_group: None,
            start_time: None,
            is_complete: false,
        }
    }

    /// Clear all state for new execution
    pub fn clear(&mut self) {
        self.tasks.clear();
        self.task_index.clear();
        self.execution_id = None;
        self.total_tasks = 0;
        self.completed_tasks = 0;
        self.failed_tasks = 0;
        self.current_group = None;
        self.start_time = None;
        self.is_complete = false;
    }

    /// Initialize from cortex/start event payload
    pub fn init_from_payload(&mut self, payload: &serde_json::Value) {
        self.clear();

        if let Some(exec_id) = payload.get("execution_id").and_then(|v| v.as_str()) {
            self.execution_id = Some(exec_id.to_string());
        }
        if let Some(total) = payload.get("total_tasks").and_then(|v| v.as_u64()) {
            self.total_tasks = total as usize;
        }

        self.start_time = Some(std::time::Instant::now());

        // Log initialization
        log::info!("Execution started: {:?}", self.execution_id);
    }

    /// Add a task to the execution state
    pub fn add_task(&mut self, task: TaskItem) {
        let index = self.tasks.len();
        self.tasks.push(task.clone());
        self.task_index.insert(task.id.clone(), index);
    }

    /// Find task by ID and return mutable reference
    pub fn find_task_mut(&mut self, task_id: &str) -> Option<&mut TaskItem> {
        if let Some(&index) = self.task_index.get(task_id) {
            self.tasks.get_mut(index)
        } else {
            None
        }
    }

    /// Find task by ID (immutable)
    pub fn find_task(&self, task_id: &str) -> Option<&TaskItem> {
        if let Some(&index) = self.task_index.get(task_id) {
            self.tasks.get(index)
        } else {
            None
        }
    }

    /// Update task status by ID
    pub fn update_task_status(&mut self, task_id: &str, status: TaskStatus) {
        if let Some(task) = self.find_task_mut(task_id) {
            task.status = status.clone();
            log::info!("Task {} status: {:?}", task_id, status);
        }
    }

    /// Mark task as complete
    pub fn complete_task(&mut self, task_id: &str, payload: &serde_json::Value) {
        if let Some(task) = self.find_task_mut(task_id) {
            task.status = TaskStatus::Success;
            if let Some(duration) = payload.get("duration_ms").and_then(|v| v.as_f64()) {
                task.duration_ms = Some(duration);
            }
            if let Some(output) = payload.get("output_preview").and_then(|v| v.as_str()) {
                task.output_preview = Some(output.to_string());
            }
            self.completed_tasks += 1;
            log::info!("Task {} completed", task_id);
        }
    }

    /// Mark task as failed
    pub fn fail_task(&mut self, task_id: &str, payload: &serde_json::Value) {
        if let Some(task) = self.find_task_mut(task_id) {
            task.status = TaskStatus::Failed;
            if let Some(error) = payload.get("error").and_then(|v| v.as_str()) {
                task.error = Some(error.to_string());
            }
            if let Some(retry) = payload.get("retry_count").and_then(|v| v.as_u64()) {
                task.retry_count = retry as usize;
            }
            self.failed_tasks += 1;
            log::info!("Task {} failed", task_id);
        }
    }

    /// Get progress percentage
    pub fn progress(&self) -> f64 {
        if self.total_tasks == 0 {
            0.0
        } else {
            (self.completed_tasks + self.failed_tasks) as f64 / self.total_tasks as f64
        }
    }

    /// Get execution duration so far
    pub fn duration_ms(&self) -> Option<f64> {
        self.start_time.map(|start| {
            let elapsed = start.elapsed();
            elapsed.as_secs_f64() * 1000.0
        })
    }
}

/// Bounded rolling log window
#[derive(Debug, Clone, Default)]
pub struct LogWindow {
    /// Bounded deque of log lines
    lines: VecDeque<String>,
    /// Maximum lines to keep
    max_lines: usize,
    /// Current log level filter (None = all)
    level_filter: Option<String>,
}

impl LogWindow {
    /// Create new log window with max lines
    pub fn new(max_lines: usize) -> Self {
        Self {
            lines: VecDeque::with_capacity(max_lines),
            max_lines,
            level_filter: None,
        }
    }

    /// Add a log line
    pub fn add_line(&mut self, level: &str, message: &str, timestamp: &str) {
        // Apply filter if set
        if let Some(ref filter) = self.level_filter {
            if level != filter {
                return;
            }
        }

        let line = format!("[{}] [{}] {}", timestamp, level.to_uppercase(), message);
        self.lines.push_back(line);

        // Maintain bounded size
        while self.lines.len() > self.max_lines {
            self.lines.pop_front();
        }
    }

    /// Add a log line from payload
    pub fn add_from_payload(&mut self, payload: &serde_json::Value) {
        let level = payload
            .get("level")
            .and_then(|v| v.as_str())
            .unwrap_or("info");
        let message = payload
            .get("message")
            .and_then(|v| v.as_str())
            .unwrap_or("");
        let timestamp = payload
            .get("timestamp")
            .and_then(|v| v.as_str())
            .unwrap_or("");

        self.add_line(level, message, timestamp);
    }

    /// Get all lines as Vec
    pub fn get_lines(&self) -> Vec<&str> {
        self.lines.iter().map(|s| s.as_str()).collect()
    }

    /// Get all lines as Strings
    pub fn get_lines_owned(&self) -> Vec<String> {
        self.lines.iter().cloned().collect()
    }

    /// Get line count
    pub fn len(&self) -> usize {
        self.lines.len()
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        self.lines.is_empty()
    }

    /// Set level filter
    pub fn set_level_filter(&mut self, level: Option<String>) {
        self.level_filter = level;
    }

    /// Clear all lines
    pub fn clear(&mut self) {
        self.lines.clear();
    }
}

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

/// Received event from socket (legacy, for backward compat)
#[derive(Debug, Clone)]
pub struct ReceivedEvent {
    pub source: String,
    pub topic: String,
    pub payload: serde_json::Value,
    pub timestamp: String,
}

/// Main application state
#[derive(Debug)]
pub struct AppState {
    title: String,
    app: Option<TuiApp>,
    should_quit: bool,
    status_message: Option<String>,
    event_tx: Option<mpsc::Sender<String>>,
    event_bus: Option<broadcast::Sender<super::TuiEvent>>,
    socket_server: Option<SocketServer>,
    received_events: Arc<Mutex<Vec<ReceivedEvent>>>,

    /// Execution state for task tracking
    execution_state: Option<ExecutionState>,
    /// Rolling log window
    log_window: LogWindow,
    /// Event receiver for mpsc channel (new IPC bridge)
    event_receiver: Option<mpsc::Receiver<SocketEvent>>,
    /// Processed count for legacy event processing
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
            execution_state: None,
            log_window: LogWindow::new(MAX_LOG_LINES),
            event_receiver: None,
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
            execution_state: None,
            log_window: LogWindow::new(MAX_LOG_LINES),
            event_receiver: None,
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

    /// Set execution state
    pub fn set_execution_state(&mut self, state: ExecutionState) {
        self.execution_state = Some(state);
    }

    /// Get execution state reference
    pub fn execution_state(&self) -> Option<&ExecutionState> {
        self.execution_state.as_ref()
    }

    /// Get execution state mutable reference
    pub fn execution_state_mut(&mut self) -> Option<&mut ExecutionState> {
        self.execution_state.as_mut()
    }

    /// Set event receiver for mpsc channel
    pub fn set_event_receiver(&mut self, receiver: mpsc::Receiver<SocketEvent>) {
        self.event_receiver = Some(receiver);
    }

    /// Get log window reference
    pub fn log_window(&self) -> &LogWindow {
        &self.log_window
    }

    /// Get log window mutable reference
    pub fn log_window_mut(&mut self) -> &mut LogWindow {
        &mut self.log_window
    }

    /// Process events from mpsc channel (non-blocking)
    pub fn process_ipc_events(&mut self) {
        // Take the receiver out to avoid borrow issues, then put it back
        let receiver = match self.event_receiver.take() {
            Some(r) => r,
            None => return,
        };

        // Non-blocking try_iter to drain the queue every frame
        for event in receiver.try_iter() {
            self.reduce(&event);
        }

        // Put the receiver back
        self.event_receiver = Some(receiver);
    }

    /// Reducer: Process SocketEvent and update state
    /// This is the core algorithm for state transitions
    fn reduce(&mut self, event: &SocketEvent) {
        log::debug!("Reducing event: {} -> {}", event.source, event.topic);

        match event.topic.as_str() {
            // System events
            "system/init" => {
                self.set_status("Connected to omni-agent");
                if let Some(version) = event.payload.get("version") {
                    log::info!("Agent version: {}", version);
                }
            }
            "system/ready" => {
                self.set_status("TUI ready");
            }

            // Cortex execution events
            "cortex/start" => {
                if let Some(state) = self.execution_state_mut() {
                    state.init_from_payload(&event.payload);
                }
                self.set_status("Execution started");
                self.add_result(
                    "Execution Started",
                    format!(
                        "ID: {:?}\nTotal Tasks: {}",
                        self.execution_state().and_then(|s| s.execution_id.as_ref()),
                        self.execution_state().map(|s| s.total_tasks).unwrap_or(0)
                    ),
                );
            }
            "cortex/group/start" => {
                let group_name = event
                    .payload
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("?");
                let task_count = event
                    .payload
                    .get("task_count")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                if let Some(state) = self.execution_state_mut() {
                    state.current_group = Some(group_name.to_string());
                }
                self.set_status(&format!("Group: {} ({} tasks)", group_name, task_count));
            }
            "cortex/group/complete" => {
                let group_name = event
                    .payload
                    .get("name")
                    .and_then(|v| v.as_str())
                    .unwrap_or("?");
                let completed = event
                    .payload
                    .get("completed")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                let failed = event
                    .payload
                    .get("failed")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(0);
                self.set_status(&format!(
                    "Group {} complete: {} done, {} failed",
                    group_name, completed, failed
                ));
            }
            "cortex/complete" => {
                let success = event
                    .payload
                    .get("success")
                    .and_then(|v| v.as_bool())
                    .unwrap_or(false);
                let duration_ms = event
                    .payload
                    .get("duration_ms")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                if let Some(state) = self.execution_state_mut() {
                    state.is_complete = true;
                }
                self.set_status(&format!(
                    "Execution {} in {:.0}ms",
                    if success { "succeeded" } else { "failed" },
                    duration_ms
                ));
            }
            "cortex/error" => {
                let error = event
                    .payload
                    .get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Unknown");
                self.add_result("Execution Error", format!("Error: {}", error));
                self.set_status("Execution error occurred");
            }

            // Task events
            "task/start" => {
                let task_id = event
                    .payload
                    .get("task_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("?");
                let description = event
                    .payload
                    .get("description")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");
                let command = event
                    .payload
                    .get("command")
                    .and_then(|v| v.as_str())
                    .unwrap_or("");

                if let Some(state) = self.execution_state_mut() {
                    state.add_task(TaskItem::new(
                        task_id.to_string(),
                        description.to_string(),
                        command.to_string(),
                    ));
                    state.update_task_status(task_id, TaskStatus::Running);
                }

                self.set_status(&format!("Task: {}", description));
            }
            "task/complete" => {
                let task_id = event
                    .payload
                    .get("task_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("?");
                if let Some(state) = self.execution_state_mut() {
                    state.complete_task(task_id, &event.payload);
                }
            }
            "task/retry" => {
                let task_id = event
                    .payload
                    .get("task_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("?");
                let attempt = event
                    .payload
                    .get("attempt")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(1);
                if let Some(state) = self.execution_state_mut() {
                    if let Some(task) = state.find_task_mut(task_id) {
                        task.status = TaskStatus::Retry;
                        task.retry_count = attempt as usize;
                    }
                }
                self.set_status(&format!("Retry task {} (attempt {})", task_id, attempt));
            }
            "task/fail" => {
                let task_id = event
                    .payload
                    .get("task_id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("?");
                let error = event
                    .payload
                    .get("error")
                    .and_then(|v| v.as_str())
                    .unwrap_or("Unknown");
                if let Some(state) = self.execution_state_mut() {
                    state.fail_task(task_id, &event.payload);
                }
                self.add_result(
                    format!("Task {} Failed", task_id),
                    format!("Error: {}", error),
                );
            }

            // Log events
            "log" | "system/log" => {
                self.log_window.add_from_payload(&event.payload);
            }

            // Unknown events
            _ => {
                // Log unknown events
                log::debug!("Unknown event topic: {}", event.topic);
            }
        }
    }

    /// Handle tick event (called periodically)
    pub fn on_tick(&mut self) {
        // Process new IPC events
        self.process_ipc_events();

        // Also process legacy events (for backward compatibility)
        let received = self.received_events.lock().unwrap();
        let processed = *self.processed_count.lock().unwrap();

        if processed < received.len() {
            let new_events: Vec<ReceivedEvent> = received.iter().skip(processed).cloned().collect();
            let new_count = received.len();
            drop(received);

            for event in new_events {
                self.on_socket_event(&event);
            }

            *self.processed_count.lock().unwrap() = new_count;
        }
    }

    /// Handle custom event from omni-events
    pub fn on_custom_event(&mut self, data: Vec<u8>) {
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
        let message = format!("[{}] {}", event.source, event.topic);
        self.set_status(&message);

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
    fn test_task_item_creation() {
        let task = TaskItem::new(
            "t1".to_string(),
            "Test task".to_string(),
            "echo test".to_string(),
        );
        assert_eq!(task.id, "t1");
        assert_eq!(task.status, TaskStatus::Pending);
        assert_eq!(task.status_symbol(), "○");
    }

    #[test]
    fn test_task_status_colors() {
        let mut pending = TaskItem::new("t1".to_string(), "Test".to_string(), "cmd".to_string());
        let mut running = TaskItem::new("t2".to_string(), "Test".to_string(), "cmd".to_string());
        let mut success = TaskItem::new("t3".to_string(), "Test".to_string(), "cmd".to_string());

        // Set different statuses
        pending.status = TaskStatus::Pending;
        running.status = TaskStatus::Running;
        success.status = TaskStatus::Success;

        assert_ne!(pending.status_color(), running.status_color());
        assert_ne!(running.status_color(), success.status_color());
    }

    #[test]
    fn test_execution_state() {
        let mut state = ExecutionState::new();
        assert!(state.tasks.is_empty());

        state.add_task(TaskItem::new(
            "t1".to_string(),
            "Task 1".to_string(),
            "cmd1".to_string(),
        ));
        state.add_task(TaskItem::new(
            "t2".to_string(),
            "Task 2".to_string(),
            "cmd2".to_string(),
        ));

        assert_eq!(state.tasks.len(), 2);
        assert!(state.find_task("t1").is_some());
        assert!(state.find_task("unknown").is_none());

        state.update_task_status("t1", TaskStatus::Running);
        let t1 = state.find_task("t1").unwrap();
        assert_eq!(t1.status, TaskStatus::Running);
    }

    #[test]
    fn test_log_window_bounded() {
        let mut window = LogWindow::new(5);
        for i in 0..10 {
            window.add_line("info", &format!("Line {}", i), "");
        }
        assert_eq!(window.len(), 5);
        // First line should be "Line 5" (lines 0-4 were discarded)
        assert!(window.get_lines_owned()[0].contains("Line 5"));
    }

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
