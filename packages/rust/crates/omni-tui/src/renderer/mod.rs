//! TUI Renderer - Main rendering loop and terminal management

use crate::{
    components::{PanelState, TuiApp},
    event::{Event, EventHandler, EventHandlerConfig},
    state::AppState,
};
use crossterm::{
    execute,
    terminal::{Clear, ClearType, disable_raw_mode, enable_raw_mode},
};
use ratatui::{Terminal, backend::CrosstermBackend};
use std::io::stdout;

/// TUI Renderer using Crossterm backend
pub struct TuiRenderer {
    terminal: Terminal<CrosstermBackend<std::io::Stdout>>,
    event_handler: EventHandler,
}

impl TuiRenderer {
    /// Create a new TUI renderer
    pub fn new() -> Result<Self, anyhow::Error> {
        enable_raw_mode()?;

        let backend = CrosstermBackend::new(stdout());
        let terminal = Terminal::new(backend)?;

        let event_handler = EventHandler::new(EventHandlerConfig::default());

        Ok(Self {
            terminal,
            event_handler,
        })
    }

    /// Run the main event loop
    pub fn run(&mut self, state: &mut AppState) -> Result<(), anyhow::Error> {
        loop {
            // Render current state
            self.terminal.draw(|f| {
                Self::render_frame(f, state);
            })?;

            // Handle events
            match self.event_handler.next() {
                Ok(Event::Input(event)) => {
                    Self::handle_event(event, state);
                }
                Ok(Event::Tick) => {
                    // Handle periodic updates
                    state.on_tick();
                }
                Ok(Event::Error(_)) => {
                    // Ignore error events
                }
                Err(_) => {
                    // Channel closed, exit
                    break;
                }
            }

            // Check if we should quit
            if state.should_quit() {
                break;
            }
        }

        // Restore terminal
        Self::restore_terminal()?;

        Ok(())
    }

    /// Restore terminal to normal mode
    pub fn restore_terminal() -> Result<(), anyhow::Error> {
        disable_raw_mode()?;
        execute!(stdout(), Clear(ClearType::All))?;
        Ok(())
    }

    /// Render a single frame
    fn render_frame(f: &mut ratatui::Frame, state: &AppState) {
        // Get terminal size
        let area = f.area();

        // Render title bar
        let title_area = ratatui::layout::Rect {
            x: 0,
            y: 0,
            height: 1,
            width: area.width,
        };

        let title = ratatui::widgets::Paragraph::new(state.title()).style(
            ratatui::style::Style::default()
                .fg(ratatui::style::Color::Cyan)
                .add_modifier(ratatui::style::Modifier::BOLD),
        );

        f.render_widget(title, title_area);

        // Render main content area
        let content_area = ratatui::layout::Rect {
            x: 0,
            y: 1,
            height: area.height.saturating_sub(2),
            width: area.width,
        };

        // Render panels
        if let Some(app) = state.app() {
            match app.layout() {
                crate::components::AppLayout::VerticalStack => {
                    Self::render_panels(f, content_area, app);
                }
                crate::components::AppLayout::SplitView => app.render_split_view(f, content_area),
            }
        }

        // Render status bar
        let status_area = ratatui::layout::Rect {
            x: 0,
            y: area.height.saturating_sub(1),
            height: 1,
            width: area.width,
        };

        let status_text = state
            .status_message()
            .unwrap_or("[Ctrl-o: Toggle] [Tab: Next] [Ctrl-c: Quit]");

        let status = ratatui::widgets::Paragraph::new(status_text)
            .style(ratatui::style::Style::default().fg(ratatui::style::Color::DarkGray));

        f.render_widget(status, status_area);
    }

    /// Render panels
    fn render_panels(f: &mut ratatui::Frame, area: ratatui::layout::Rect, app: &TuiApp) {
        let panel_collection = app.panels();
        if panel_collection.is_empty() {
            let message = ratatui::widgets::Paragraph::new("No panels to display")
                .style(ratatui::style::Style::default().fg(ratatui::style::Color::DarkGray));
            f.render_widget(message, area);
            return;
        }

        // Create layout for panels
        let constraints: Vec<ratatui::layout::Constraint> = panel_collection
            .all_panels()
            .iter()
            .map(|p| {
                ratatui::layout::Constraint::Length(match *p.state() {
                    PanelState::Folded => 3,
                    PanelState::Expanded => u16::try_from(p.line_count().min(20))
                        .unwrap_or(20)
                        .saturating_add(2),
                })
            })
            .collect();

        let chunks = ratatui::layout::Layout::default()
            .direction(ratatui::layout::Direction::Vertical)
            .constraints(constraints)
            .split(area);

        for (i, panel) in panel_collection.all_panels().iter().enumerate() {
            let panel = panel.clone();

            // Highlight focused panel
            if i == panel_collection.focused_index() {
                // Add focus indicator
            }

            panel.render(f, chunks[i]);
        }
    }

    /// Handle TUI events
    fn handle_event(event: crate::TuiEvent, state: &mut AppState) {
        match event {
            crate::TuiEvent::Quit => {
                state.quit();
            }
            crate::TuiEvent::TogglePanel => {
                if let Some(app) = state.app_mut() {
                    app.panels_mut().toggle_focused();
                }
            }
            crate::TuiEvent::NextPanel => {
                if let Some(app) = state.app_mut() {
                    app.focus_next();
                }
            }
            crate::TuiEvent::PrevPanel => {
                if let Some(app) = state.app_mut() {
                    app.focus_prev();
                }
            }
            crate::TuiEvent::ScrollDown => {
                if let Some(app) = state.app_mut()
                    && let Some(panel) = app.panels_mut().focused_panel_mut()
                {
                    panel.scroll_down();
                }
            }
            crate::TuiEvent::ScrollUp => {
                if let Some(app) = state.app_mut()
                    && let Some(panel) = app.panels_mut().focused_panel_mut()
                {
                    panel.scroll_up();
                }
            }
            crate::TuiEvent::Char(c) => {
                if let Some(app) = state.app_mut() {
                    app.append_search(c);
                }
            }
            crate::TuiEvent::Backspace => {
                if let Some(app) = state.app_mut() {
                    app.backspace_search();
                }
            }
            crate::TuiEvent::Resize(_, _) => {
                // Terminal will auto-resize on next draw
            }
            crate::TuiEvent::Tick => {
                state.on_tick();
            }
            crate::TuiEvent::Custom(data) => {
                state.on_custom_event(data);
            }
        }
    }
}

impl Drop for TuiRenderer {
    fn drop(&mut self) {
        let _ = disable_raw_mode();
        let _ = execute!(stdout(), Clear(ClearType::All));
    }
}
