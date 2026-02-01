//! Python bindings for omni-tui TUI engine

use pyo3::prelude::*;

/// Python wrapper for TuiApp
#[pyclass]
struct PyTuiApp {
    inner: omni_tui::TuiApp,
}

#[pymethods]
impl PyTuiApp {
    #[new]
    fn new(title: &str) -> Self {
        Self {
            inner: omni_tui::TuiApp::new(title),
        }
    }

    /// Add a result panel
    fn add_result(&mut self, title: &str, content: &str) {
        self.inner.add_result(title, content);
    }

    /// Add a panel with fold state
    fn add_panel(&mut self, title: &str, content: &str, expanded: bool) {
        let mut panel = omni_tui::FoldablePanel::new(title, content);
        if expanded {
            panel.set_state(omni_tui::PanelState::Expanded);
        }
        self.inner.add_panel(panel);
    }

    /// Set status message
    fn set_status(&mut self, message: &str) {
        self.inner.set_status(message);
    }

    /// Get panel count
    fn panel_count(&self) -> usize {
        self.inner.panels().len()
    }
}

/// Python wrapper for FoldablePanel
#[pyclass]
struct PyFoldablePanel {
    inner: omni_tui::FoldablePanel,
}

#[pymethods]
impl PyFoldablePanel {
    #[new]
    fn new(title: &str, content: &str) -> Self {
        Self {
            inner: omni_tui::FoldablePanel::new(title, content),
        }
    }

    /// Toggle fold state
    fn toggle(&mut self) {
        self.inner.toggle();
    }

    /// Check if expanded
    fn is_expanded(&self) -> bool {
        self.inner.is_expanded()
    }

    /// Set content
    fn set_content(&mut self, content: &str) {
        self.inner.set_content(content);
    }

    /// Append a line
    fn append_line(&mut self, line: &str) {
        self.inner.append_content(line);
    }

    /// Get title
    fn title(&self) -> String {
        self.inner.title().to_string()
    }

    /// Get line count
    fn line_count(&self) -> usize {
        self.inner.line_count()
    }
}

/// Python module definition
#[pymodule]
fn omni_tui_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyTuiApp>()?;
    m.add_class::<PyFoldablePanel>()?;
    Ok(())
}
