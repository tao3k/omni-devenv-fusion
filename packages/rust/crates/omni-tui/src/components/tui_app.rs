use super::collection::PanelCollection;
use super::layout::AppLayout;
use super::panel::FoldablePanel;
use ratatui::{
    Frame,
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    widgets::{Block, Borders, List, ListItem, Paragraph, Wrap},
};

/// Main TUI Application container
#[derive(Debug, Clone)]
pub struct TuiApp {
    title: String,
    panels: PanelCollection,
    status_message: Option<String>,
    layout: AppLayout,
    search_query: String,
    filtered_indices: Vec<usize>,
}

impl TuiApp {
    /// Create a new TUI app
    pub fn new<S: Into<String>>(title: S) -> Self {
        Self {
            title: title.into(),
            panels: PanelCollection::new(),
            status_message: None,
            layout: AppLayout::SplitView,
            search_query: String::new(),
            filtered_indices: Vec::new(),
        }
    }

    /// Set layout mode
    pub fn set_layout(&mut self, layout: AppLayout) {
        self.layout = layout;
        if layout == AppLayout::SplitView {
            self.update_filter();
        }
    }

    /// Get current layout
    pub fn layout(&self) -> AppLayout {
        self.layout
    }

    /// Update search query
    pub fn update_search(&mut self, query: String) {
        self.search_query = query;
        self.update_filter();
    }

    /// Append to search query
    pub fn append_search(&mut self, c: char) {
        self.search_query.push(c);
        self.update_filter();
    }

    /// Backspace search query
    pub fn backspace_search(&mut self) {
        self.search_query.pop();
        self.update_filter();
    }

    /// Update filtered indices based on search query
    fn update_filter(&mut self) {
        if self.search_query.is_empty() {
            self.filtered_indices = (0..self.panels.len()).collect();
        } else {
            let query = self.search_query.to_lowercase();
            self.filtered_indices = self
                .panels
                .all_panels()
                .iter()
                .enumerate()
                .filter(|(_, p)| p.title().to_lowercase().contains(&query))
                .map(|(i, _)| i)
                .collect();
        }
    }

    /// Add a result panel
    pub fn add_result<S: Into<String>, C: Into<String>>(&mut self, title: S, content: C) {
        self.panels.add(title, &content.into());
        self.update_filter();
    }

    /// Add a panel with pre-split content
    pub fn add_panel(&mut self, panel: FoldablePanel) {
        self.panels.add_panel(panel);
        self.update_filter();
    }

    /// Set status message
    pub fn set_status(&mut self, message: &str) {
        self.status_message = Some(message.to_string());
    }

    /// Get panels reference
    pub fn panels(&self) -> &PanelCollection {
        &self.panels
    }

    /// Get mutable panels reference
    pub fn panels_mut(&mut self) -> &mut PanelCollection {
        &mut self.panels
    }

    /// Get title
    pub fn title(&self) -> &str {
        &self.title
    }

    /// Focus next item
    pub fn focus_next(&mut self) {
        match self.layout {
            AppLayout::VerticalStack => self.panels.focus_next(),
            AppLayout::SplitView => {
                if self.filtered_indices.is_empty() {
                    return;
                }
                let current_real_index = self.panels.focused_index();
                // Find current position in filtered list
                let current_filtered_pos = self
                    .filtered_indices
                    .iter()
                    .position(|&i| i == current_real_index);

                let next_filtered_pos = match current_filtered_pos {
                    Some(pos) => (pos + 1) % self.filtered_indices.len(),
                    None => 0, // Default to first if not found
                };

                let next_real_index = self.filtered_indices[next_filtered_pos];
                self.panels.set_focused_index(next_real_index);
            }
        }
    }

    /// Focus previous item
    pub fn focus_prev(&mut self) {
        match self.layout {
            AppLayout::VerticalStack => self.panels.focus_prev(),
            AppLayout::SplitView => {
                if self.filtered_indices.is_empty() {
                    return;
                }
                let current_real_index = self.panels.focused_index();
                // Find current position in filtered list
                let current_filtered_pos = self
                    .filtered_indices
                    .iter()
                    .position(|&i| i == current_real_index);

                let prev_filtered_pos = match current_filtered_pos {
                    Some(pos) => {
                        if pos == 0 {
                            self.filtered_indices.len().saturating_sub(1)
                        } else {
                            pos - 1
                        }
                    }
                    None => 0,
                };

                let prev_real_index = self.filtered_indices[prev_filtered_pos];
                self.panels.set_focused_index(prev_real_index);
            }
        }
    }

    /// Render split view (Navi-like)
    pub fn render_split_view(&self, f: &mut Frame, area: Rect) {
        let chunks = Layout::default()
            .direction(Direction::Vertical)
            .constraints([
                Constraint::Length(3),      // Search bar
                Constraint::Percentage(40), // List
                Constraint::Percentage(60), // Preview
            ])
            .split(area);

        // 1. Search Bar
        let search_block = Block::default()
            .borders(Borders::ALL)
            .title(" Search ")
            .border_style(Style::default().fg(Color::Cyan));

        let search = Paragraph::new(self.search_query.as_str())
            .block(search_block)
            .style(Style::default().fg(Color::White));

        f.render_widget(search, chunks[0]);

        // 2. List
        let items: Vec<ListItem> = self
            .filtered_indices
            .iter()
            .map(|&i| {
                let panel = &self.panels.all_panels()[i];
                let style = if i == self.panels.focused_index() {
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(Color::Gray)
                };
                ListItem::new(panel.title()).style(style)
            })
            .collect();

        let list_block = Block::default()
            .borders(Borders::ALL)
            .title(format!(" Results ({}) ", items.len()));

        let list = List::new(items)
            .block(list_block)
            .highlight_style(Style::default().add_modifier(Modifier::REVERSED));
        // We handle selection highlighting manually above for now to sync with PanelCollection focus

        f.render_widget(list, chunks[1]);

        // 3. Preview
        let preview_block = Block::default().borders(Borders::ALL).title(" Preview ");

        let content = if let Some(panel) = self.panels.focused_panel() {
            panel.content.join("\n")
        } else {
            String::new()
        };

        let preview = Paragraph::new(content)
            .block(preview_block)
            .wrap(Wrap { trim: true });

        f.render_widget(preview, chunks[2]);
    }
}
