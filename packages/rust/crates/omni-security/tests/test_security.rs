//! Tests for security module - secret scanning and permissions.

use omni_security::{PermissionGatekeeper, SecretScanner};

#[test]
fn test_wildcard_permission() {
    let perms = vec!["filesystem:*".to_string()];
    assert!(PermissionGatekeeper::check("filesystem.read_file", &perms));
    assert!(PermissionGatekeeper::check("filesystem.write_file", &perms));
    assert!(!PermissionGatekeeper::check("git.status", &perms));
}

#[test]
fn test_wildcard_with_colon_separator() {
    let perms = vec!["filesystem:*".to_string()];
    assert!(PermissionGatekeeper::check("filesystem:read", &perms));
}

#[test]
fn test_exact_permission() {
    let perms = vec!["git.status".to_string()];
    assert!(PermissionGatekeeper::check("git.status", &perms));
    assert!(!PermissionGatekeeper::check("git.commit", &perms));
}

#[test]
fn test_admin_permission() {
    let perms = vec!["*".to_string()];
    assert!(PermissionGatekeeper::check("any.tool", &perms));
    assert!(PermissionGatekeeper::check("another.tool", &perms));
}

#[test]
fn test_no_permissions() {
    let perms = vec![];
    assert!(!PermissionGatekeeper::check("filesystem.read_file", &perms));
}

#[test]
fn test_scan_secrets() {
    // Using clearly fake/test keys to avoid GitHub secret scanning false positives
    let text = "AWS: AKIAIOSFODNN7EXAMPLE and Stripe: sk_test_000000000000000000000000000";
    let violations = SecretScanner::scan_all(text);
    assert_eq!(violations.len(), 2);
}
