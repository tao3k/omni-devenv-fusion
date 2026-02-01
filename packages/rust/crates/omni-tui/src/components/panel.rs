use ratatui::{
    Frame,
    layout::Rect,
    style::{Color, Style},
    widgets::{Block, Borders, Paragraph, Wrap},
};
use std::cmp::min;

/// Height of a folded panel
pub const FOLDED_HEIGHT: u16 = 3;

/// Maximum expanded height for a panel
pub const MAX_EXPANDED_HEIGHT: u16 = 20;

/// State of a foldable panel
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PanelState {
    Expanded,
    Folded,
}

/// A foldable panel component that can show/hide content with Ctrl-o
#[derive(Debug, Clone)]
pub struct FoldablePanel {
    title: String,
    pub(crate) content: Vec<String>,
    state: PanelState,
    scroll_offset: u16,
    max_lines: usize,
}

impl FoldablePanel {
    /// Create a new foldable panel
    pub fn new<S: Into<String>>(title: S, content: &str) -> Self {
        Self {
            title: title.into(),
            content: content.lines().map(|s| s.to_string()).collect(),
            state: PanelState::Folded,
            scroll_offset: 0,
            max_lines: 100,
        }
    }

    /// Create a panel with pre-split content lines
    pub fn with_lines<S: Into<String>>(title: S, lines: Vec<String>) -> Self {
        Self {
            title: title.into(),
            content: lines,
            state: PanelState::Folded,
            scroll_offset: 0,
            max_lines: 100,
        }
    }

    /// Toggle the fold state
    pub fn toggle(&mut self) {
        self.state = match self.state {
            PanelState::Expanded => PanelState::Folded,
            PanelState::Folded => PanelState::Expanded,
        };
    }

    /// Check if the panel is expanded
    pub fn is_expanded(&self) -> bool {
        self.state == PanelState::Expanded
    }

    /// Get panel state
    pub fn state(&self) -> &PanelState {
        &self.state
    }

    /// Set the fold state explicitly
    pub fn set_state(&mut self, state: PanelState) {
        self.state = state;
    }

    /// Get the title
    pub fn title(&self) -> &str {
        &self.title
    }

    /// Update the content
    pub fn set_content(&mut self, content: &str) {
        self.content = content.lines().map(|s| s.to_string()).collect();
    }

    /// Append content
    pub fn append_content(&mut self, line: &str) {
        if self.content.len() < self.max_lines {
            self.content.push(line.to_string());
        }
    }

    /// Scroll down
    pub fn scroll_down(&mut self) {
        if self.scroll_offset < self.content.len().saturating_sub(1) as u16 {
            self.scroll_offset += 1;
        }
    }

    /// Scroll up
    pub fn scroll_up(&mut self) {
        if self.scroll_offset > 0 {
            self.scroll_offset -= 1;
        }
    }

    /// Get the number of content lines
    pub fn line_count(&self) -> usize {
        self.content.len()
    }

    /// Calculate the required height
    pub fn required_height(&self) -> u16 {
        match self.state {
            PanelState::Folded => FOLDED_HEIGHT,
            PanelState::Expanded => {
                let max_visible = (MAX_EXPANDED_HEIGHT as usize).min(self.content.len());
                (max_visible as u16).saturating_add(2) // +2 for borders
            }
        }
    }

    /// Render the panel
    pub fn render(&self, f: &mut Frame, area: Rect) {
        let height = self.required_height();
        let panel_area = Rect {
            height: min(height, area.height),
            ..area
        };

        // Determine styles based on state
        let border_style = match self.state {
            PanelState::Expanded => Style::default().fg(Color::Cyan),
            PanelState::Folded => Style::default().fg(Color::DarkGray),
        };

        let toggle_hint = if self.state == PanelState::Expanded {
            " (Ctrl-o to fold) "
        } else {
            " (Ctrl-o to expand) "
        };

        let block = Block::default()
            .borders(Borders::ALL)
            .title(format!("{}{}", self.title, toggle_hint))
            .border_style(border_style);

        let content = match self.state {
            PanelState::Folded => {
                let line_count = self.content.len();
                format!(" [{} lines hidden] ", line_count)
            }
            PanelState::Expanded => {
                let visible_content: Vec<&str> = self
                    .content
                    .iter()
                    .skip(self.scroll_offset as usize)
                    .take(MAX_EXPANDED_HEIGHT as usize - 2)
                    .map(|s| s.as_str())
                    .collect();

                if visible_content.is_empty() {
                    " (No content) ".to_string()
                } else {
                    visible_content.join("\n")
                }
            }
        };

        let paragraph = Paragraph::new(content)
            .block(block)
            .wrap(Wrap { trim: true })
            .scroll((self.scroll_offset, 0));

        f.render_widget(paragraph, panel_area);
    }
}
