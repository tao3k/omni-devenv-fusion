//! Panic Safety Utilities
//!
//! Provides safety barriers to prevent Rust panics from crashing the Python process.
//! All Rust-to-Python FFI boundaries should use `run_safe` to catch panics.

use pyo3::prelude::*;
use std::panic::{self, AssertUnwindSafe};

/// Executes a closure, catching any Rust panics and converting them to Python exceptions.
/// This prevents the entire Python process from aborting due to a bug in Rust code.
///
/// # Arguments
/// * `f` - A closure that returns a `PyResult<T>`
///
/// # Returns
/// `Ok(T)` on success, or `Err(PyRuntimeError)` if a panic occurred.
///
/// # Example
/// ```ignore
/// use crate::utils::run_safe;
///
/// fn risky_operation() -> PyResult<String> {
///     run_safe(|| {
///         // Any panic here will be caught and converted to Python exception
///         let result = might_panic()?;
///         Ok(result)
///     })
/// }
/// ```
pub fn run_safe<F, T>(f: F) -> PyResult<T>
where
    F: FnOnce() -> PyResult<T>,
{
    // AssertUnwindSafe is required because the closure might capture variables
    // that are theoretically not unwind safe, but in our FFI context it's usually acceptable.
    let result = panic::catch_unwind(AssertUnwindSafe(f));

    match result {
        Ok(py_result) => py_result, // Normal execution
        Err(payload) => {
            // Extract panic message
            let msg = if let Some(s) = payload.downcast_ref::<&str>() {
                *s
            } else if let Some(s) = payload.downcast_ref::<String>() {
                &**s
            } else {
                "Unknown panic origin"
            };

            // Convert to Python RuntimeError with descriptive message
            Err(pyo3::exceptions::PyRuntimeError::new_err(format!(
                "Rust panic intercepted by safety barrier: {}. System stability preserved.",
                msg
            )))
        }
    }
}
