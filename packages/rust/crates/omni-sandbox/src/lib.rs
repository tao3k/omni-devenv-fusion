//! omni-sandbox - NCL-driven sandbox execution layer
//!
//! # Architecture
//!
//! This module executes pre-generated sandbox configurations.
//! Configuration is produced by NCL and exported as JSON.
//! Rust reads JSON and executes the sandbox - NO configuration parsing in Rust.
//!
//! # Data Flow
//!
//! 1. NCL exports configuration to JSON (nickel export --format json)
//! 2. Python loads JSON and passes config path to Rust
//! 3. Rust executor reads JSON, spawns nsjail/seatbelt
//! 4. Rust monitors resources and returns results

use pyo3::prelude::*;

pub mod executor;

pub use executor::NsJailExecutor;
pub use executor::SeatbeltExecutor;
pub use executor::{ExecutionResult, MountConfig, SandboxConfig};

/// Platform detection
#[pyfunction]
#[must_use]
pub fn detect_platform() -> String {
    if cfg!(target_os = "linux") {
        "linux".to_string()
    } else if cfg!(target_os = "macos") {
        "macos".to_string()
    } else {
        "unknown".to_string()
    }
}

/// Check if nsjail is available
#[pyfunction]
#[must_use]
pub fn is_nsjail_available() -> bool {
    which::which("nsjail").is_ok()
}

/// Check if sandbox-exec is available (macOS)
#[pyfunction]
#[must_use]
pub fn is_seatbelt_available() -> bool {
    if cfg!(target_os = "macos") {
        which::which("sandbox-exec").is_ok()
    } else {
        false
    }
}

/// Export Python module
#[pymodule]
fn omni_sandbox(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(pyo3::wrap_pyfunction!(detect_platform, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(is_nsjail_available, m)?)?;
    m.add_function(pyo3::wrap_pyfunction!(is_seatbelt_available, m)?)?;

    m.add_class::<ExecutionResult>()?;
    m.add_class::<SandboxConfig>()?;
    m.add_class::<MountConfig>()?;

    m.add_class::<executor::NsJailExecutor>()?;
    m.add_class::<executor::SeatbeltExecutor>()?;

    Ok(())
}
