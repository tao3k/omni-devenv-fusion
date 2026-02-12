//! NCL-driven sandbox executor bindings
//!
//! Provides Rust-accelerated sandbox execution for:
//! - nsjail (Linux)
//! - seatbelt (macOS)
//!
//! This module bridges the NCL sandbox configuration with native sandboxing tools.

use omni_sandbox as sandbox;
use pyo3::prelude::*;

/// Platform detection
#[pyfunction]
pub fn sandbox_detect_platform() -> String {
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
pub fn sandbox_is_nsjail_available() -> bool {
    which::which("nsjail").is_ok()
}

/// Check if sandbox-exec is available (macOS)
#[pyfunction]
pub fn sandbox_is_seatbelt_available() -> bool {
    if cfg!(target_os = "macos") {
        which::which("sandbox-exec").is_ok()
    } else {
        false
    }
}

// Re-export types from omni_sandbox
pub use sandbox::ExecutionResult;
pub use sandbox::MountConfig;
pub use sandbox::NsJailExecutor;
pub use sandbox::SandboxConfig;
pub use sandbox::SeatbeltExecutor;
