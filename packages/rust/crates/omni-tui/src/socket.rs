//! Unix Domain Socket server for receiving events from Python Agent
//!
//! Listens on /tmp/omni-omega.sock for JSON events in omni-events format:
//! {"source": "omega", "topic": "omega/mission/start", "payload": {...}, "timestamp": "..."}

use log::{error, info, warn};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fmt;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

/// Received event from Python
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct SocketEvent {
    pub source: String,
    pub topic: String,
    pub payload: Value,
    pub timestamp: String,
}

/// Event callback for received events
pub type EventCallback = Box<dyn Fn(SocketEvent) + Send + 'static>;

/// Unix Domain Socket server for receiving Python events
#[derive(Clone)]
pub struct SocketServer {
    socket_path: String,
    running: Arc<AtomicBool>,
    event_callback: Arc<Mutex<Option<EventCallback>>>,
}

impl fmt::Debug for SocketServer {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("SocketServer")
            .field("socket_path", &self.socket_path)
            .field("running", &self.running.load(Ordering::SeqCst))
            .finish()
    }
}

impl SocketServer {
    /// Create a new socket server
    pub fn new(socket_path: &str) -> Self {
        Self {
            socket_path: socket_path.to_string(),
            running: Arc::new(AtomicBool::new(false)),
            event_callback: Arc::new(Mutex::new(None)),
        }
    }

    /// Set callback for received events
    pub fn set_event_callback(&self, callback: EventCallback) {
        let mut cb = self.event_callback.lock().unwrap();
        *cb = Some(callback);
    }

    /// Start the server in a background thread
    pub fn start(&self) -> Result<thread::JoinHandle<()>, Box<dyn std::error::Error>> {
        let socket_path = Path::new(&self.socket_path);

        // Remove existing socket file
        if socket_path.exists() {
            std::fs::remove_file(socket_path)?;
        }

        // Create listener
        let listener = UnixListener::bind(socket_path)?;
        let listener_clone = listener.try_clone()?;
        listener.set_nonblocking(true)?;

        self.running.store(true, Ordering::SeqCst);

        let running = self.running.clone();
        let callback = self.event_callback.clone();

        // Start background thread
        let handle = thread::spawn(move || {
            Self::run_loop(listener_clone, running, callback);
        });

        info!("Socket server started on {}", self.socket_path);
        Ok(handle)
    }

    /// Main server loop
    fn run_loop(
        listener: UnixListener,
        running: Arc<AtomicBool>,
        callback: Arc<Mutex<Option<EventCallback>>>,
    ) {
        let mut connections = Vec::new();

        while running.load(Ordering::SeqCst) {
            // Check for new connections
            match listener.accept() {
                Ok((stream, _addr)) => {
                    stream.set_nonblocking(false).ok();
                    connections.push(BufReader::new(stream));
                    info!("New connection from Python agent");
                }
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    // No pending connections, continue
                }
                Err(e) => {
                    error!("Accept error: {}", e);
                }
            }

            // Process existing connections
            let mut dead_connections = Vec::new();
            for (i, conn) in connections.iter_mut().enumerate() {
                let mut line = String::new();
                match conn.read_line(&mut line) {
                    Ok(0) => {
                        // Connection closed
                        dead_connections.push(i);
                    }
                    Ok(_) => {
                        // Parse event
                        let line = line.trim();
                        if !line.is_empty() {
                            if let Ok(event) = serde_json::from_str::<SocketEvent>(line) {
                                info!("Received event: {} from {}", event.topic, event.source);
                                let cb = callback.lock().unwrap();
                                if let Some(ref callback) = *cb {
                                    callback(event.clone());
                                }
                            } else {
                                warn!("Failed to parse event: {}", line);
                            }
                        }
                    }
                    Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                        // No data available
                    }
                    Err(e) => {
                        error!("Read error: {}", e);
                        dead_connections.push(i);
                    }
                }
            }

            // Remove dead connections
            for i in dead_connections.into_iter().rev() {
                connections.swap_remove(i);
            }

            // Sleep briefly to avoid busy loop
            thread::sleep(Duration::from_millis(10));
        }

        info!("Socket server stopped");
    }

    /// Stop the server
    pub fn stop(&self) {
        self.running.store(false, Ordering::SeqCst);

        // Clean up socket file
        let socket_path = Path::new(&self.socket_path);
        if socket_path.exists() {
            std::fs::remove_file(socket_path).ok();
        }

        info!("Socket server stopped and cleaned up");
    }

    /// Check if running
    pub fn is_running(&self) -> bool {
        self.running.load(Ordering::SeqCst)
    }
}

/// Send an event through Unix socket (for testing)
pub fn send_event(
    socket_path: &str,
    event: &SocketEvent,
) -> Result<(), Box<dyn std::error::Error>> {
    let mut stream = UnixStream::connect(socket_path)?;

    let json = serde_json::to_string(event)?;
    stream.write_all(json.as_bytes())?;
    stream.write_all(b"\n")?;

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    use tempfile::TempDir;

    #[test]
    fn test_socket_server_start_stop() {
        let temp_dir = TempDir::new().unwrap();
        let socket_path = temp_dir.path().join("test.sock");

        let server = SocketServer::new(socket_path.to_str().unwrap());
        server.start().unwrap();

        assert!(server.is_running());
        assert!(Path::new(&socket_path).exists());

        server.stop();
        assert!(!server.is_running());
    }

    #[test]
    fn test_send_and_receive_event() {
        let temp_dir = TempDir::new().unwrap();
        let socket_path = temp_dir.path().join("test.sock");

        let received = Arc::new(Mutex::new(Vec::new()));
        let received_clone = received.clone();

        let server = SocketServer::new(socket_path.to_str().unwrap());
        server.set_event_callback(Box::new(move |event| {
            let mut r = received_clone.lock().unwrap();
            r.push(event);
        }));

        server.start().unwrap();

        // Give server time to start
        std::thread::sleep(Duration::from_millis(100));

        // Send event
        let event = SocketEvent {
            source: "test".to_string(),
            topic: "test/event".to_string(),
            payload: serde_json::json!({"message": "hello"}),
            timestamp: "2026-01-31T00:00:00".to_string(),
        };
        send_event(socket_path.to_str().unwrap(), &event).unwrap();

        // Give time for event to be processed
        std::thread::sleep(Duration::from_millis(200));

        server.stop();

        let r = received.lock().unwrap();
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].source, "test");
        assert_eq!(r[0].topic, "test/event");
    }
}
