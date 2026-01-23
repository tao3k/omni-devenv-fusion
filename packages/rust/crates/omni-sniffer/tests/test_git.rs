//! Tests for git module - Git repository inspection.

use tempfile::TempDir;

use omni_sniffer::{SnifferError, scan_git_status};

#[test]
fn test_scan_git_status_non_repo() {
    let dir = TempDir::new().unwrap();
    let result = scan_git_status(dir.path());
    assert!(matches!(result, Err(SnifferError::RepoOpen(_))));
}
