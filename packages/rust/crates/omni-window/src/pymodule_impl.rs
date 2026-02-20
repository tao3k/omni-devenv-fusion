//! Python bindings for omni-window.

use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::SessionWindow;

/// Python-exposed session window (Rust-only backend for `run_entry`).
#[pyclass]
pub struct PySessionWindow {
    inner: SessionWindow,
}

#[pymethods]
impl PySessionWindow {
    #[new]
    #[pyo3(signature = (session_id, max_turns=2048))]
    fn new(session_id: &str, max_turns: usize) -> Self {
        Self {
            inner: SessionWindow::new(session_id, max_turns),
        }
    }

    #[pyo3(signature = (role, content, tool_count=0, checkpoint_id=None))]
    fn append_turn(
        &mut self,
        role: &str,
        content: &str,
        tool_count: u32,
        checkpoint_id: Option<&str>,
    ) {
        self.inner
            .append_turn(role, content, tool_count, checkpoint_id);
    }

    fn get_recent_turns(&self, max_turns: usize, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let turns = self.inner.get_recent_turns(max_turns);
        let list = pyo3::types::PyList::empty(py);
        for slot in turns {
            let dict = PyDict::new(py);
            dict.set_item("role", slot.role.as_str())?;
            dict.set_item("content", slot.content.as_str())?;
            dict.set_item("tool_count", slot.tool_count)?;
            if let Some(ref id) = slot.checkpoint_id {
                dict.set_item("checkpoint_id", id.as_str())?;
            }
            list.append(dict)?;
        }
        Ok(list.into())
    }

    fn get_stats(&self, py: Python<'_>) -> PyResult<Py<PyAny>> {
        let (total_turns, total_tool_calls, window_used) = self.inner.get_stats();
        let dict = PyDict::new(py);
        dict.set_item("total_turns", total_turns)?;
        dict.set_item("total_tool_calls", total_tool_calls)?;
        dict.set_item("window_used", window_used)?;
        Ok(dict.into())
    }

    #[getter]
    fn session_id(&self) -> &str {
        self.inner.session_id()
    }
}
