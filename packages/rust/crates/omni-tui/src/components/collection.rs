use super::panel::{FOLDED_HEIGHT, FoldablePanel, MAX_EXPANDED_HEIGHT, PanelState};
use ratatui::{
    Frame,
    layout::{Constraint, Direction, Layout, Rect},
};

/// A collection of panels with layout management
#[derive(Debug, Clone)]
pub struct PanelCollection {
    panels: Vec<FoldablePanel>,
    focused_index: usize,
    // layout: PanelLayout, // Reserved for future use
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PanelLayout {
    Vertical,
    Horizontal,
}

impl PanelCollection {
    /// Create a new empty collection
    pub fn new() -> Self {
        Self {
            panels: Vec::new(),
            focused_index: 0,
            // layout: PanelLayout::Vertical, // Reserved for future use
        }
    }

    /// Add a panel
    pub fn add_panel(&mut self, panel: FoldablePanel) {
        self.panels.push(panel);
    }

    /// Create and add a panel
    pub fn add<S: Into<String>>(&mut self, title: S, content: &str) {
        self.panels.push(FoldablePanel::new(title, content));
    }

    /// Create and add a panel with String content
    pub fn add_string<S: Into<String>, C: Into<String>>(&mut self, title: S, content: C) {
        self.panels
            .push(FoldablePanel::new(title, content.into().as_str()));
    }

    /// Get the number of panels
    pub fn len(&self) -> usize {
        self.panels.len()
    }

    /// Check if empty
    pub fn is_empty(&self) -> bool {
        self.panels.is_empty()
    }

    /// Focus next panel
    pub fn focus_next(&mut self) {
        if !self.panels.is_empty() {
            self.focused_index = (self.focused_index + 1) % self.panels.len();
        }
    }

    /// Focus previous panel
    pub fn focus_prev(&mut self) {
        if !self.panels.is_empty() {
            self.focused_index = if self.focused_index == 0 {
                self.panels.len().saturating_sub(1)
            } else {
                self.focused_index - 1
            };
        }
    }

    /// Toggle the focused panel
    pub fn toggle_focused(&mut self) {
        if let Some(panel) = self.panels.get_mut(self.focused_index) {
            panel.toggle();
        }
    }

    /// Get a reference to the focused panel
    pub fn focused_panel(&self) -> Option<&FoldablePanel> {
        self.panels.get(self.focused_index)
    }

    /// Get a mutable reference to the focused panel
    pub fn focused_panel_mut(&mut self) -> Option<&mut FoldablePanel> {
        self.panels.get_mut(self.focused_index)
    }

    /// Get all panels (reference)
    pub fn all_panels(&self) -> &Vec<FoldablePanel> {
        &self.panels
    }

    /// Get focused index
    pub fn focused_index(&self) -> usize {
        self.focused_index
    }

    /// Set focused index
    pub fn set_focused_index(&mut self, index: usize) {
        if index < self.panels.len() {
            self.focused_index = index;
        }
    }

    /// Render all panels
    pub fn render(&self, f: &mut Frame, area: Rect) {
        if self.panels.is_empty() {
            return;
        }

        // Calculate heights for each panel
        let _total_fixed_height: u16 = self.panels.iter().map(|_| 2).sum(); // Borders
        let constraints: Vec<Constraint> = self
            .panels
            .iter()
            .map(|p| {
                let expanded_lines = p.line_count().min(MAX_EXPANDED_HEIGHT as usize) as u16;
                Constraint::Length(match *p.state() {
                    PanelState::Folded => FOLDED_HEIGHT,
                    PanelState::Expanded => expanded_lines.saturating_add(2),
                })
            })
            .collect();

        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints(constraints)
            .split(area);

        for (i, panel) in self.panels.iter().enumerate() {
            let panel = panel.clone();

            // Highlight focused panel
            if i == self.focused_index {
                // Render with focus indicator
            }

            panel.render(f, chunks[i]);
        }
    }
}

impl Default for PanelCollection {
    fn default() -> Self {
        Self::new()
    }
}
