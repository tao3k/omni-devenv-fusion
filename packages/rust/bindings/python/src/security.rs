//! Security Scanner & Permission Gatekeeper
//!
//! Provides:
//! - Secret scanning to detect API keys, tokens, and sensitive data
//! - Permission validation for skill tool execution (Zero Trust)

use omni_security::{PermissionGatekeeper, SecretScanner};
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

/// Check if a tool execution is allowed by the given permissions.
///
/// This implements Zero Trust access control for skills.
///
/// Args:
///     tool_name: Full tool name (e.g., "filesystem.read_file")
///     permissions: List of permission patterns (e.g., ["filesystem:*", "git:status"])
///
/// Returns:
///     True if allowed, False otherwise.
///
/// Examples:
///     # Wildcard category
///     check_permission("filesystem.read_file", ["filesystem:*"]) -> True
///
///     # Exact match
///     check_permission("git.status", ["git:status"]) -> True
///
///     # No permissions (Zero Trust)
///     check_permission("any.tool", []) -> False
///
///     # Admin permission
///     check_permission("any.tool", ["*"]) -> True
#[pyfunction]
pub fn check_permission(tool_name: &str, permissions: Vec<String>) -> bool {
    PermissionGatekeeper::check(tool_name, &permissions)
}
