//! Tests for context module - scratchpad context scanning.

use std::fs;
use tempfile::TempDir;

use omni_sniffer::scan_scratchpad_context;

#[test]
fn test_scan_scratchpad_nonexistent() {
    let dir = TempDir::new().unwrap();
    let lines = scan_scratchpad_context(dir.path());
    assert_eq!(lines, 0);
}

#[test]
fn test_scan_scratchpad_with_content() {
    let dir = TempDir::new().unwrap();
    let scratchpad = dir.path().join(".memory/active_context/SCRATCHPAD.md");
    fs::create_dir_all(scratchpad.parent().unwrap()).unwrap();
    fs::write(&scratchpad, "Line 1\nLine 2\nLine 3").unwrap();
    let lines = scan_scratchpad_context(dir.path());
    assert_eq!(lines, 3);
}
