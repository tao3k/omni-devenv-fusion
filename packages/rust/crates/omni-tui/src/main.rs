//! main.rs - Production binary entry point for omni-tui
//!
//! Acts as a headless-compatible renderer that visualizes state from Python.
//! Supports two connection modes:
//! - server (legacy): Binds socket and waits for Python to connect
//! - client (reverse): Connects to Python's socket (recommended)
//!
//! Usage:
//!   Server mode: omni-tui --socket /path/to/sock --role server
//!   Client mode: omni-tui --socket /path/to/sock --role client --pid <parent_pid>
//!
//! Can also run in headless mode (no TUI rendering) for testing or CI:
//!   omni-tui --socket /path/to/sock --headless

use anyhow::{Context, Result};
use clap::Parser;
use crossterm::event::{self, Event as CEvent, KeyCode};
use log::{info, warn};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

use omni_tui::{
    TuiRenderer,
    socket::{SocketClient, SocketEvent, SocketServer},
    state::{AppState, ExecutionState},
};

/// Omni TUI - Headless-compatible renderer for Python Agent events
#[derive(clap::Parser, Debug)]
#[command(name = "omni-tui")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Unix socket path for IPC
    #[arg(short, long)]
    socket: String,

    /// Connection role: "server" (binds socket) or "client" (connects to Python)
    #[arg(long, default_value = "client")]
    role: String,

    /// Parent process PID (for cleanup on parent death)
    #[arg(short, long)]
    pid: Option<i32>,

    /// Run in headless mode (no TUI rendering, just process events)
    #[arg(long, default_value = "false")]
    headless: bool,
}

/// Run the event processing loop (with or without TUI)
fn run_event_loop(state: &mut AppState, server_handle: thread::JoinHandle<()>, headless: bool) {
    let tick_rate = Duration::from_millis(100);
    let mut last_tick = Instant::now();

    loop {
        // Only handle input if not headless
        if !headless {
            let timeout = tick_rate.saturating_sub(last_tick.elapsed());

            if event::poll(timeout).unwrap_or(false) {
                if let Ok(CEvent::Key(key)) = event::read() {
                    match key.code {
                        KeyCode::Char('q') | KeyCode::Esc => {
                            info!("User pressed quit");
                            break;
                        }
                        _ => {}
                    }
                }
            }
        }

        // Process IPC events (non-blocking drain)
        state.process_ipc_events();

        // Update tick
        if last_tick.elapsed() >= tick_rate {
            last_tick = Instant::now();
        }
    }

    let _ = server_handle.join();
}

fn main() -> Result<()> {
    // Initialize logging
    omni_tui::init_logger();

    let args = Args::parse();

    info!("Starting omni-tui renderer");
    info!("Socket path: {}", args.socket);
    info!("Role: {}", args.role);
    info!("Headless: {}", args.headless);
    if let Some(pid) = args.pid {
        info!("Parent PID: {}", pid);
    }

    // Create mpsc channel for IPC bridge
    let (event_tx, event_rx) = mpsc::channel::<SocketEvent>();

    // Start socket connection based on role
    let server_handle = if args.role == "client" {
        // Reverse mode: Connect to Python's socket
        info!("Connecting to Python socket as client...");
        SocketClient::connect(&args.socket, event_tx.clone())?
    } else {
        // Legacy mode: Bind and listen
        info!("Binding socket as server...");
        let server = SocketServer::new(&args.socket);
        let tx_clone = event_tx.clone();
        server.set_event_callback(Box::new(move |event: SocketEvent| {
            let _ = tx_clone.send(event);
        }));
        server.start().context("Failed to start socket server")?
    };

    info!("Socket connection established");

    // Create app state with execution state
    let mut state = AppState::new("Omni Agent".to_string());
    state.set_execution_state(ExecutionState::new());
    state.set_event_receiver(event_rx);

    // Try to initialize TUI if not headless
    let renderer = if args.headless {
        info!("Running in headless mode (--headless flag set)");
        None
    } else {
        match TuiRenderer::new() {
            Ok(r) => {
                info!("TUI renderer initialized successfully");
                Some(r)
            }
            Err(e) => {
                warn!("TUI init failed: {}. Switching to headless mode.", e);
                None
            }
        }
    };

    // Log the mode we're running in
    if renderer.is_some() {
        info!("Starting TUI rendering loop");
    } else {
        info!("Starting headless event processing loop");
    }

    // Run the event loop
    run_event_loop(
        &mut state,
        server_handle,
        args.headless || renderer.is_none(),
    );

    // Cleanup
    info!("Cleaning up...");

    info!("omni-tui shutdown complete");
    Ok(())
}

#[cfg(test)]
mod demo_tests {
    use super::*;

    #[test]
    fn test_args_parsing_server() {
        let args = Args::parse_from(&["omni-tui", "--socket", "/test.sock", "--role", "server"]);
        assert_eq!(args.socket, "/test.sock");
        assert_eq!(args.role, "server");
    }

    #[test]
    fn test_args_parsing_client() {
        let args = Args::parse_from(&[
            "omni-tui",
            "--socket",
            "/test.sock",
            "--role",
            "client",
            "--pid",
            "1234",
        ]);
        assert_eq!(args.socket, "/test.sock");
        assert_eq!(args.role, "client");
        assert_eq!(args.pid, Some(1234));
    }

    #[test]
    fn test_args_parsing_headless() {
        let args = Args::parse_from(&["omni-tui", "--socket", "/test.sock", "--headless"]);
        assert_eq!(args.socket, "/test.sock");
        assert!(args.headless);
    }
}
