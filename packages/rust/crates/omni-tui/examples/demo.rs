//! Simple TUI demo binary for testing omni-tui with ratatui

use std::error::Error;
use std::thread;
use std::time::Duration;

use clap::Parser;
use omni_tui::{AppState, TuiRenderer, init_logger};

/// Simple TUI demo for testing omni-tui
#[derive(clap::Parser, Debug)]
#[command(name = "omni-tui-demo")]
#[command(author = "Omni Dev Fusion")]
#[command(version = "0.1.0")]
#[command(about = "Demo TUI for testing omni-tui", long_about = None)]
struct Args {
    /// Unix socket path for receiving events
    #[arg(short, long, default_value = "/tmp/omni-tui.sock")]
    socket: String,

    /// Run in demo mode (auto-generate events)
    #[arg(short, long, action = clap::ArgAction::SetTrue)]
    demo: bool,
}

fn main() -> Result<(), Box<dyn Error>> {
    init_logger();
    let args = Args::parse();

    println!("=== Omni TUI Demo ===");
    println!("Socket: {}", args.socket);
    println!("Demo mode: {}", args.demo);
    println!();

    let mut state = AppState::new("Omni TUI Demo".to_string());

    // Add initial panels
    state.add_result("Welcome", "Welcome to Omni TUI Demo!\n\nEvents will appear here in real-time.\n\nControls:\n  - Tab: Next panel\n  - Ctrl-o: Toggle panel\n  - Ctrl-c: Quit");
    state.add_result("Status", "Waiting for events...");

    // Start socket server for receiving events from Python
    println!("[*] Starting socket server on {}...", args.socket);
    state.start_socket_server(&args.socket)?;

    if args.demo {
        run_demo_mode(&mut state);
    }

    println!("[*] Starting TUI (press Ctrl-c to exit)...");

    // Run the actual ratatui TUI
    let mut renderer = TuiRenderer::new()?;
    renderer.run(&mut state)?;

    state.stop_socket_server();
    println!("\n[*] Demo completed.");

    Ok(())
}

fn run_demo_mode(state: &mut AppState) {
    println!("[*] Running in demo mode...");

    let events = [
        (
            "omega",
            "omega/mission/start",
            "Starting mission: Build neural interface",
        ),
        ("cortex", "cortex/task/start", "Task: Initialize kernel"),
        (
            "homeostasis",
            "homeostasis/status",
            "Branch isolation active",
        ),
        ("cerebellum", "cerebellum/scan", "Scanning codebase..."),
        ("cortex", "cortex/task/complete", "Kernel initialized"),
        ("omega", "omega/semantic/scan", "Semantic analysis complete"),
        (
            "homeostasis",
            "homeostasis/merge",
            "Branch merged: feature/new-ui",
        ),
        ("omega", "omega/mission/complete", "Mission completed"),
    ];

    for (i, (source, topic, message)) in events.iter().enumerate() {
        println!("[Demo] {} -> {}: {}", source, topic, message);

        // Add panel for mission events
        if topic.starts_with("omega/mission") {
            state.add_result(
                format!("Mission Event {}", i + 1),
                format!("Source: {}\nTopic: {}\n\n{}", source, topic, message),
            );
        } else {
            state.set_status(&format!("[{}] {}", source, topic));
        }

        thread::sleep(Duration::from_millis(500));
    }

    println!();
    println!("[Demo] All demo events generated!");
    println!("[Demo] Switch to the TUI window to see the rendered UI.");
    println!();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_args_parsing() {
        let args = Args::parse_from(&["omni-tui-demo", "--socket", "/test.sock"]);
        assert_eq!(args.socket, "/test.sock");
        assert!(!args.demo);
    }
}
