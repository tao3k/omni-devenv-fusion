//! omni-tui - Rust-driven TUI engine for Omni Dev Fusion
//!
//! Provides terminal UI rendering with foldable panels and event-driven updates.
//! Integrates with omni-events for reactive state management.
#![allow(
    missing_docs,
    clippy::doc_markdown,
    clippy::must_use_candidate,
    clippy::missing_errors_doc,
    clippy::uninlined_format_args,
    clippy::redundant_closure_for_method_calls,
    clippy::needless_pass_by_value
)]

pub mod components;
pub mod event;
pub mod renderer;
pub mod socket;
pub mod state;

pub use components::{FoldablePanel, PanelState, TuiApp};
pub use event::{Event, EventHandler, TuiEvent};
pub use renderer::TuiRenderer;
pub use socket::{SocketClient, SocketEvent, SocketServer};
pub use state::{
    AppState, ExecutionState, LogWindow, MAX_LOG_LINES, PanelType, ReceivedEvent, TaskItem,
    TaskStatus,
};

use log::info;

/// Initialize the TUI subsystem with logging
pub fn init_logger() {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info"))
        .format_timestamp(None)
        .init();
}

/// Main entry point for running the TUI application
pub fn run_tui<F>(title: &str, app_creator: F) -> Result<(), anyhow::Error>
where
    F: FnOnce(&mut AppState) -> Result<(), anyhow::Error>,
{
    init_logger();

    let mut renderer = TuiRenderer::new()?;
    let mut state = AppState::new(title.to_string());

    // Create application state
    app_creator(&mut state)?;

    info!("Starting TUI application: {title}");

    // Run the main event loop
    renderer.run(&mut state)
}
