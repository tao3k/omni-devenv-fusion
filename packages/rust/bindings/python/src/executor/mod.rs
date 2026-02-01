//! Python bindings for omni-executor (OmniCell Nushell Bridge)
//!
//! Provides structured access to Nushell execution with safety guarantees.

use omni_executor::{ActionType, NuConfig, NuSystemBridge, QueryAction, QueryBuilder};
use pyo3::prelude::*;

/// Helper to build query strings from Python.
/// This function creates a query builder and returns the final command string.
#[pyfunction]
#[pyo3(signature = (source, path=None, predicate=None, columns=None, sort=None, limit=None, action_type="observe"))]
pub fn build_query(
    source: &str,
    path: Option<&str>,
    predicate: Option<&str>,
    columns: Option<Vec<String>>,
    sort: Option<&str>,
    limit: Option<u32>,
    action_type: &str,
) -> String {
    let mut builder = QueryBuilder::new(source);

    if let Some(p) = path {
        builder = builder.source(p);
    }
    if let Some(pred) = predicate {
        builder = builder.where_clause(pred);
    }
    if let Some(cols) = columns {
        builder = builder.select(&cols.iter().map(|s| s.as_str()).collect::<Vec<_>>());
    }
    if let Some(s) = sort {
        builder = builder.sort_by(s);
    }
    if let Some(n) = limit {
        builder = builder.take(n);
    }

    let action = match action_type {
        "mutate" | "Mutate" | "MUTATE" => QueryAction::Mutate,
        _ => QueryAction::Observe,
    };
    builder = builder.with_action_type(action);

    builder.build()
}

/// Helper to build raw query strings (without JSON conversion).
#[pyfunction]
#[pyo3(signature = (source, path=None, predicate=None, columns=None, sort=None, limit=None))]
pub fn build_query_raw(
    source: &str,
    path: Option<&str>,
    predicate: Option<&str>,
    columns: Option<Vec<String>>,
    sort: Option<&str>,
    limit: Option<u32>,
) -> String {
    let mut builder = QueryBuilder::new(source);

    if let Some(p) = path {
        builder = builder.source(p);
    }
    if let Some(pred) = predicate {
        builder = builder.where_clause(pred);
    }
    if let Some(cols) = columns {
        builder = builder.select(&cols.iter().map(|s| s.as_str()).collect::<Vec<_>>());
    }
    if let Some(s) = sort {
        builder = builder.sort_by(s);
    }
    if let Some(n) = limit {
        builder = builder.take(n);
    }

    builder.build_raw()
}

/// Python wrapper for the Nushell bridge.
#[pyclass]
pub struct PyOmniCell {
    bridge: NuSystemBridge,
}

#[pymethods]
impl PyOmniCell {
    #[new]
    #[pyo3(signature = (nu_path="nu", enable_shellcheck=true))]
    fn new(nu_path: &str, enable_shellcheck: bool) -> Self {
        let config = NuConfig {
            nu_path: nu_path.to_string(),
            enable_shellcheck,
            ..Default::default()
        };
        Self {
            bridge: NuSystemBridge::with_config(config),
        }
    }

    /// Execute a Nushell command with structured output.
    ///
    /// Args:
    ///     cmd: The command to execute
    ///     ensure_structured: If true, forces JSON output
    ///
    /// Returns:
    ///     JSON-serializable result or error string
    fn execute(&self, py: Python, cmd: String, ensure_structured: bool) -> PyResult<String> {
        py.detach(|| match self.bridge.execute(&cmd, ensure_structured) {
            Ok(value) => Ok(value.to_string()),
            Err(e) => Err(pyo3::exceptions::PyRuntimeError::new_err(e.to_string())),
        })
    }

    /// Classify command as 'observe' or 'mutate'.
    fn classify(&self, cmd: String) -> String {
        match NuSystemBridge::classify_action(&cmd) {
            ActionType::Observe => "observe".to_string(),
            ActionType::Mutate => "mutate".to_string(),
        }
    }
}
