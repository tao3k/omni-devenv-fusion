//! Security Scanner - Phase 49: The Hyper-Immune System
//!
//! Provides secret scanning to detect API keys, tokens, and other sensitive data.

use omni_security::SecretScanner;
use pyo3::prelude::*;

/// Scan content for secrets (AWS keys, Stripe keys, Slack tokens, etc.)
/// Returns a violation message if secrets are found, None if clean.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
pub fn scan_secrets(content: &str) -> Option<String> {
    Python::attach(|py| {
        py.detach(|| {
            SecretScanner::scan(content).map(|v| {
                format!(
                    "[SECURITY VIOLATION] Found {}: {}",
                    v.rule_id, v.description
                )
            })
        })
    })
}

/// Check if content contains any secrets (boolean check only).
/// More efficient than scan_secrets when you only need a boolean result.
/// Releases GIL for CPU-intensive regex scanning.
#[pyfunction]
pub fn contains_secrets(content: &str) -> bool {
    Python::attach(|py| py.detach(|| SecretScanner::contains_secrets(content)))
}
