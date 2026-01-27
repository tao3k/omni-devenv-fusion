//! Python bindings for Rust File Watcher (notify feature)
//!
//! Provides async file watching with EventBus integration.
//! Replaces watchdog for hot reload functionality.

use pyo3::prelude::*;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use tokio::sync::mpsc;

/// File event from the watcher
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyFileEvent {
    #[pyo3(get)]
    pub event_type: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub is_directory: bool,
}

impl From<omni_io::FileEvent> for PyFileEvent {
    fn from(e: omni_io::FileEvent) -> Self {
        match e {
            omni_io::FileEvent::Created { path, is_dir } => PyFileEvent {
                event_type: "created".to_string(),
                path,
                is_directory: is_dir,
            },
            omni_io::FileEvent::Modified { path } => PyFileEvent {
                event_type: "modified".to_string(),
                path,
                is_directory: false,
            },
            omni_io::FileEvent::Deleted { path, is_dir } => PyFileEvent {
                event_type: "deleted".to_string(),
                path,
                is_directory: is_dir,
            },
            omni_io::FileEvent::Error { path, error: _ } => PyFileEvent {
                event_type: "error".to_string(),
                path,
                is_directory: false,
            },
        }
    }
}

/// Configuration for file watcher
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyWatcherConfig {
    #[pyo3(get, set)]
    pub paths: Vec<String>,
    #[pyo3(get, set)]
    pub recursive: bool,
    #[pyo3(get, set)]
    pub debounce_ms: u64,
    #[pyo3(get, set)]
    pub patterns: Vec<String>,
    #[pyo3(get, set)]
    pub exclude: Vec<String>,
}

#[pymethods]
impl PyWatcherConfig {
    #[new]
    #[pyo3(signature = (paths=None))]
    fn new(paths: Option<Vec<String>>) -> Self {
        PyWatcherConfig {
            paths: paths.unwrap_or_default(),
            recursive: true,
            debounce_ms: 500,
            patterns: vec!["**/*".to_string()],
            exclude: vec![
                "**/*.pyc".to_string(),
                "**/__pycache__/**".to_string(),
                "**/.git/**".to_string(),
                "**/target/**".to_string(),
            ],
        }
    }

    /// Add a path to watch
    fn add_path(&mut self, path: String) {
        self.paths.push(path);
    }

    /// Add a glob pattern
    fn add_pattern(&mut self, pattern: String) {
        self.patterns.push(pattern);
    }

    /// Add an exclude pattern
    fn add_exclude(&mut self, pattern: String) {
        self.exclude.push(pattern);
    }
}

impl Default for PyWatcherConfig {
    fn default() -> Self {
        Self::new(None)
    }
}

/// State shared between the Python handle and the watcher thread
struct WatcherState {
    _is_running: Arc<AtomicBool>, // Renamed to avoid conflict with PyFileWatcherHandle.is_running property
    stop_tx: Arc<mpsc::Sender<()>>,
    /// Keep the FileWatcherHandle alive in the thread
    _watcher_handle: Arc<Mutex<Option<omni_io::FileWatcherHandle>>>,
}

/// Handle to control the file watcher
#[pyclass]
#[derive(Clone)]
pub struct PyFileWatcherHandle {
    /// Shared state for controlling the watcher
    state: Arc<WatcherState>,
}

impl PyFileWatcherHandle {
    fn new(state: Arc<WatcherState>) -> Self {
        Self { state }
    }
}

#[pymethods]
impl PyFileWatcherHandle {
    /// Check if watcher is currently running
    #[getter]
    fn is_running(&self) -> bool {
        self.state._is_running.load(Ordering::SeqCst)
    }

    /// Stop the watcher
    fn stop(&mut self) {
        self.state._is_running.store(false, Ordering::SeqCst);
    }
}

/// Receiver for file events from the global EventBus
///
/// Maintains a persistent subscription to receive events continuously.
/// This replaces creating a new receiver each time, which would miss
/// events published before the receiver was created.
#[pyclass]
#[derive(Clone)]
pub struct PyFileEventReceiver {
    /// The receiver wrapped in Arc and Mutex for sharing
    receiver: Arc<Mutex<Option<tokio::sync::broadcast::Receiver<omni_events::OmniEvent>>>>,
}

#[pymethods]
impl PyFileEventReceiver {
    /// Create a new file event receiver
    #[new]
    fn new() -> Self {
        Self {
            receiver: Arc::new(Mutex::new(Some(omni_events::GLOBAL_BUS.subscribe()))),
        }
    }

    /// Try to receive pending file events
    ///
    /// Returns a list of (event_type, path) tuples for file-related events.
    /// Non-blocking - returns immediately with available events.
    fn try_recv(&mut self) -> Vec<(String, String)> {
        let mut events = Vec::new();

        if let Ok(mut guard) = self.receiver.lock() {
            if let Some(ref mut rx) = *guard {
                // Try to receive up to 10 events
                for _ in 0..10 {
                    match rx.try_recv() {
                        Ok(event) if event.topic.starts_with("file/") => {
                            let payload = &event.payload;
                            if let Some(path) = payload.get("path").and_then(|p| p.as_str()) {
                                let event_type = event.topic.replace("file/", "");
                                events.push((event_type, path.to_string()));
                            }
                        }
                        Ok(_) => { /* non-file event, skip */ }
                        Err(tokio::sync::broadcast::error::TryRecvError::Empty) => break,
                        Err(tokio::sync::broadcast::error::TryRecvError::Closed) => {
                            // Channel closed, break
                            break;
                        }
                        Err(tokio::sync::broadcast::error::TryRecvError::Lagged(_)) => break,
                    }
                }
            }
        }

        events
    }
}

/// Internal watcher runner that runs in a dedicated thread
fn run_watcher_thread(
    paths: Vec<String>,
    recursive: bool,
    debounce_ms: u64,
    patterns: Vec<String>,
    exclude: Vec<String>,
    _is_running: Arc<AtomicBool>,
    mut stop_rx: mpsc::Receiver<()>,
    watcher_handle: Arc<Mutex<Option<omni_io::FileWatcherHandle>>>,
) {
    // Create a new runtime for this thread
    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();

    rt.block_on(async {
        let omni_config = omni_io::WatcherConfig {
            paths,
            recursive,
            debounce_ms,
            patterns,
            exclude,
        };

        type WatcherCallback = fn(
            (
                omni_io::FileEvent,
                std::option::Option<omni_events::OmniEvent>,
            ),
        );

        // Start the watcher and store the handle
        match omni_io::start_file_watcher::<WatcherCallback>(omni_config, None).await {
            Ok(handle) => {
                // Store the handle to keep it alive
                if let Ok(mut guard) = watcher_handle.lock() {
                    *guard = Some(handle);
                }
            }
            Err(e) => {
                eprintln!("Failed to start file watcher: {}", e);
                return;
            }
        }

        // Wait for stop signal
        let _ = stop_rx.recv().await;

        // Stop the watcher when signal received
        if let Ok(mut guard) = watcher_handle.lock() {
            if let Some(h) = guard.take() {
                h.stop().await;
            }
        }
    });
}

/// Start watching a single path (simple API)
///
/// Args:
///     path: Path to watch
///
/// Returns:
///     PyFileWatcherHandle
#[pyfunction]
#[pyo3(signature = (path))]
pub fn py_watch_path(path: String) -> PyResult<PyFileWatcherHandle> {
    let (stop_tx, stop_rx) = mpsc::channel(1);
    let is_running = Arc::new(AtomicBool::new(true));
    let watcher_handle = Arc::new(Mutex::new(None));
    let watcher_handle_for_thread = watcher_handle.clone();

    // Create shared state first (both state and thread use same is_running Arc)
    let state = Arc::new(WatcherState {
        _is_running: is_running.clone(),
        stop_tx: Arc::new(stop_tx),
        _watcher_handle: watcher_handle,
    });

    // Spawn the watcher in a dedicated thread with its own runtime
    let _keeper = thread::spawn(move || {
        run_watcher_thread(
            vec![path],
            true,
            500,
            vec!["**/*".to_string()],
            vec![
                "**/*.pyc".to_string(),
                "**/__pycache__/**".to_string(),
                "**/.git/**".to_string(),
                "**/target/**".to_string(),
            ],
            is_running,
            stop_rx,
            watcher_handle_for_thread,
        );
    });

    // Give the watcher time to start
    thread::sleep(std::time::Duration::from_millis(100));

    Ok(PyFileWatcherHandle::new(state))
}

/// Start a file watcher with custom configuration
///
/// Args:
///     config: PyWatcherConfig with paths, patterns, etc.
///
/// Returns:
///     PyFileWatcherHandle
#[pyfunction]
#[pyo3(signature = (config))]
pub fn py_start_file_watcher(config: PyWatcherConfig) -> PyResult<PyFileWatcherHandle> {
    let (stop_tx, stop_rx) = mpsc::channel(1);
    let is_running = Arc::new(AtomicBool::new(true));
    let watcher_handle = Arc::new(Mutex::new(None));
    let watcher_handle_for_thread = watcher_handle.clone();

    // Create shared state first (both state and thread use same is_running Arc)
    let state = Arc::new(WatcherState {
        _is_running: is_running.clone(),
        stop_tx: Arc::new(stop_tx),
        _watcher_handle: watcher_handle,
    });

    // Spawn the watcher in a dedicated thread with its own runtime
    let _keeper = thread::spawn(move || {
        run_watcher_thread(
            config.paths,
            config.recursive,
            config.debounce_ms,
            config.patterns,
            config.exclude,
            is_running,
            stop_rx,
            watcher_handle_for_thread,
        );
    });

    // Give the watcher time to start
    thread::sleep(std::time::Duration::from_millis(100));

    Ok(PyFileWatcherHandle::new(state))
}

/// Subscribe to file change events from the global EventBus
///
/// Returns a list of recent file events as [(event_type, path), ...]
#[pyfunction]
#[pyo3(signature = ())]
pub fn py_subscribe_file_events() -> Vec<(String, String)> {
    use omni_events::GLOBAL_BUS;

    // Create a receiver
    let mut rx = GLOBAL_BUS.subscribe();
    let mut events = Vec::new();

    // Collect recent events (non-blocking)
    for _ in 0..10 {
        match rx.try_recv() {
            Ok(event) if event.topic.starts_with("file/") => {
                let payload = &event.payload;
                if let Some(path) = payload.get("path").and_then(|p| p.as_str()) {
                    let event_type = event.topic.replace("file/", "");
                    events.push((event_type, path.to_string()));
                }
            }
            Ok(_) => {}
            Err(tokio::sync::broadcast::error::TryRecvError::Empty) => break,
            Err(tokio::sync::broadcast::error::TryRecvError::Closed) => break,
            Err(tokio::sync::broadcast::error::TryRecvError::Lagged(_)) => break,
        }
    }

    events
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn test_watch_path() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().to_string_lossy().to_string();

        // Start watching
        let mut handle = py_watch_path(path).unwrap();

        // Stop watching
        handle.stop();
    }
}
