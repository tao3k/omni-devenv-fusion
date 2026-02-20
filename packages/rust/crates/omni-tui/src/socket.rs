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
use std::sync::mpsc::Sender;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

/// Unix Domain Socket client for connecting to Python's socket server
///
/// In reverse connection mode, Rust connects to Python's socket as a client.
/// Used when Python is the server (binds and listens).
pub struct SocketClient;

impl SocketClient {
    /// Connect to a Unix Domain Socket and start reading events
    ///
    /// # Arguments
    /// * `socket_path` - Path to the Unix socket created by Python
    /// * `tx` - Sender channel to push received events to the main thread
    ///
    /// # Returns
    /// JoinHandle for the reader thread
    pub fn connect(socket_path: &str, tx: Sender<SocketEvent>) -> thread::JoinHandle<()> {
        let path = socket_path.to_string();

        thread::spawn(move || {
            // Try to connect with retries
            let max_retries = 50;
            let retry_delay = Duration::from_millis(100);

            for i in 0..max_retries {
                match UnixStream::connect(&path) {
                    Ok(stream) => {
                        let tx_clone = tx.clone();

                        info!("Connected to Python socket at {}", path);

                        // Spawn reader thread
                        thread::spawn(move || {
                            let reader = BufReader::new(stream);
                            for line in reader.lines() {
                                match line {
                                    Ok(l) if !l.is_empty() => {
                                        match serde_json::from_str::<SocketEvent>(&l) {
                                            Ok(event) => {
                                                info!("Received event: {}", event.topic);
                                                if tx_clone.send(event).is_err() {
                                                    break; // Receiver dropped
                                                }
                                            }
                                            Err(e) => {
                                                warn!("Failed to parse event: {}", e);
                                            }
                                        }
                                    }
                                    Ok(_) => {}
                                    Err(_) => break,
                                }
                            }
                            info!("Socket reader thread stopped");
                        });

                        // Keep stream alive
                        loop {
                            std::thread::sleep(Duration::from_secs(1));
                        }
                    }
                    Err(_) if i < max_retries - 1 => {
                        // Not ready yet, retry
                        std::thread::sleep(retry_delay);
                    }
                    Err(e) => {
                        error!("Failed to connect to socket {}: {}", path, e);
                        break;
                    }
                }
            }
        })
    }
}

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
            .finish_non_exhaustive()
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
        match self.event_callback.lock() {
            Ok(mut cb) => {
                *cb = Some(callback);
            }
            Err(err) => {
                error!("Failed to set event callback due to poisoned lock: {}", err);
            }
        }
    }

    /// Start the server in a background thread
    pub fn start(&self) -> Result<thread::JoinHandle<()>, anyhow::Error> {
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
                                match callback.lock() {
                                    Ok(cb) => {
                                        if let Some(ref callback) = *cb {
                                            callback(event.clone());
                                        }
                                    }
                                    Err(err) => {
                                        error!("Failed to acquire event callback lock: {}", err);
                                    }
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
pub fn send_event(socket_path: &str, event: &SocketEvent) -> Result<(), anyhow::Error> {
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
