//! Event handling for TUI - Keyboard input and timing events

use crossterm::{
    event::{self, Event as CrosstermEvent, KeyEvent, KeyEventKind, KeyModifiers},
    execute,
    terminal::{Clear, ClearType, disable_raw_mode},
};
use std::{
    io::stdout,
    sync::mpsc,
    thread,
    time::{Duration, Instant},
};
use tokio::sync::broadcast;

/// TUI-specific event types
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TuiEvent {
    /// Ctrl-o pressed - toggle panel
    TogglePanel,
    /// Ctrl-c pressed - exit
    Quit,
    /// Tab pressed - next panel
    NextPanel,
    /// Shift-Tab pressed - previous panel
    PrevPanel,
    /// Arrow down pressed
    ScrollDown,
    /// Arrow up pressed
    ScrollUp,
    /// Window resize
    Resize(u16, u16),
    /// Character input
    Char(char),
    /// Backspace
    Backspace,
    /// Tick event (periodic)
    Tick,
    /// Custom event from omni-events
    Custom(Vec<u8>),
}

impl TuiEvent {
    /// Check if this is a quit event
    pub fn is_quit(&self) -> bool {
        self == &TuiEvent::Quit
    }
}

/// Event from the input system
#[derive(Debug, Clone)]
pub enum Event {
    /// Input event (keyboard, mouse)
    Input(TuiEvent),
    /// Periodic tick
    Tick,
    /// Error occurred
    Error(String),
}

/// Convert Crossterm event to TuiEvent
fn map_crossterm_event(event: CrosstermEvent) -> Option<TuiEvent> {
    match event {
        CrosstermEvent::Key(KeyEvent {
            code,
            modifiers,
            kind: KeyEventKind::Press,
            ..
        }) => {
            // Ctrl-o: Toggle panel
            if modifiers.contains(KeyModifiers::CONTROL) && code == event::KeyCode::Char('o') {
                return Some(TuiEvent::TogglePanel);
            }
            // Ctrl-c: Quit
            if modifiers.contains(KeyModifiers::CONTROL) && code == event::KeyCode::Char('c') {
                return Some(TuiEvent::Quit);
            }
            // Tab: Next panel
            if code == event::KeyCode::Tab {
                return Some(TuiEvent::NextPanel);
            }
            // BackTab: Previous panel (Shift+Tab)
            if modifiers.contains(KeyModifiers::SHIFT) && code == event::KeyCode::BackTab {
                return Some(TuiEvent::PrevPanel);
            }
            // Arrow keys for scrolling
            match code {
                event::KeyCode::Down | event::KeyCode::Char('j') => Some(TuiEvent::ScrollDown),
                event::KeyCode::Up | event::KeyCode::Char('k') => Some(TuiEvent::ScrollUp),
                event::KeyCode::Backspace => Some(TuiEvent::Backspace),
                event::KeyCode::Char(c) => Some(TuiEvent::Char(c)),
                _ => None,
            }
        }
        CrosstermEvent::Resize(width, height) => Some(TuiEvent::Resize(width, height)),
        _ => None,
    }
}

/// Event handler configuration
#[derive(Debug, Clone)]
pub struct EventHandlerConfig {
    /// Tick rate in milliseconds
    pub tick_rate: Duration,
    /// Whether to enable mouse events
    pub enable_mouse: bool,
    /// Whether to focus on Ctrl-click
    pub focus_on_ctrl: bool,
}

impl Default for EventHandlerConfig {
    fn default() -> Self {
        Self {
            tick_rate: Duration::from_millis(250),
            enable_mouse: false,
            focus_on_ctrl: true,
        }
    }
}

/// Event handler for TUI
pub struct EventHandler {
    receiver: mpsc::Receiver<Event>,
    // config: EventHandlerConfig, // Reserved for future use
}

impl EventHandler {
    /// Create a new event handler
    pub fn new(config: EventHandlerConfig) -> Self {
        let (sender, receiver) = mpsc::channel();

        // Spawn input thread
        let tick_rate = config.tick_rate;
        thread::spawn(move || {
            let mut last_tick = Instant::now();

            loop {
                // Calculate time until next tick
                let timeout = tick_rate.saturating_sub(last_tick.elapsed());

                // Poll for events with timeout
                match event::poll(timeout) {
                    Ok(true) => {
                        if let Ok(CrosstermEvent::Key(key)) = event::read() {
                            // Handle Ctrl-c specially to exit
                            if key.modifiers.contains(KeyModifiers::CONTROL)
                                && key.code == event::KeyCode::Char('c')
                            {
                                let _ = sender.send(Event::Input(TuiEvent::Quit));
                                break;
                            }

                            if let Some(tui_event) = map_crossterm_event(CrosstermEvent::Key(key)) {
                                let _ = sender.send(Event::Input(tui_event));
                            }
                        }
                    }
                    Ok(false) => {}
                    Err(err) => {
                        let _ = sender.send(Event::Error(format!("Failed to poll events: {err}")));
                        break;
                    }
                }

                // Check if tick should fire
                if last_tick.elapsed() >= tick_rate {
                    let _ = sender.send(Event::Tick);
                    last_tick = Instant::now();
                }
            }
        });

        Self {
            receiver,
            // config, // Reserved for future use
        }
    }

    /// Receive the next event (blocking)
    pub fn next(&self) -> Result<Event, mpsc::RecvError> {
        self.receiver.recv()
    }

    /// Try to receive an event (non-blocking)
    pub fn try_next(&self) -> Result<Option<Event>, mpsc::TryRecvError> {
        self.receiver.try_recv().map(Some)
    }
}

/// Broadcast-based event handler for async integration
pub struct BroadcastEventHandler {
    rx: mpsc::Receiver<Event>,
    _tx: mpsc::Sender<Event>,
}

impl BroadcastEventHandler {
    /// Create a new broadcast handler
    pub fn new() -> (Self, mpsc::Sender<Event>) {
        let (tx, rx) = mpsc::channel();
        (
            Self {
                rx,
                _tx: tx.clone(),
            },
            tx,
        )
    }

    /// Receive next event
    pub fn recv(&mut self) -> Result<Event, mpsc::RecvError> {
        self.rx.recv()
    }
}

/// Subscribe to omni-events for custom TuiEvents
pub struct EventSubscriber {
    rx: broadcast::Receiver<omni_events::OmniEvent>,
}

impl EventSubscriber {
    /// Create a new subscriber
    pub fn new(rx: broadcast::Receiver<omni_events::OmniEvent>) -> Self {
        Self { rx }
    }

    /// Receive the next omni-event (blocking)
    pub fn recv(&mut self) -> Result<omni_events::OmniEvent, broadcast::error::RecvError> {
        // Use blocking receive for sync TUI
        loop {
            match self.rx.try_recv() {
                Ok(event) => return Ok(event),
                Err(broadcast::error::TryRecvError::Empty) => {
                    // Sleep briefly and retry
                    std::thread::sleep(std::time::Duration::from_millis(10));
                }
                Err(broadcast::error::TryRecvError::Closed) => {
                    return Err(broadcast::error::RecvError::Closed);
                }
                Err(broadcast::error::TryRecvError::Lagged(n)) => {
                    return Err(broadcast::error::RecvError::Lagged(n));
                }
            }
        }
    }
}

/// Disable raw mode and restore terminal
pub fn disable_raw_mode_safe() {
    let _ = disable_raw_mode();
    let _ = execute!(stdout(), Clear(ClearType::All));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tui_event_quit() {
        assert!(TuiEvent::Quit.is_quit());
        assert!(!TuiEvent::TogglePanel.is_quit());
    }

    #[test]
    fn test_event_handler_config() {
        let config = EventHandlerConfig::default();
        assert_eq!(config.tick_rate, Duration::from_millis(250));
        assert!(!config.enable_mouse);
    }
}
