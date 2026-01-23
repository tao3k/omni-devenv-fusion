//! Tests for sync module - synchronous file operations.

use std::io::Write;
use tempfile::TempDir;

use omni_io::{IoError, read_text_safe};

#[test]
fn test_sync_read() {
    let dir = TempDir::new().unwrap();
    let p = dir.path().join("sync.txt");
    std::fs::write(&p, "Sync Read").unwrap();
    assert_eq!(read_text_safe(&p, 1024).unwrap(), "Sync Read");
}

#[test]
fn test_sync_binary() {
    let dir = TempDir::new().unwrap();
    let p = dir.path().join("binary.bin");
    let mut file = std::fs::File::create(&p).unwrap();
    file.write_all(b"\x00\x01\x02\x03").unwrap();
    assert!(matches!(read_text_safe(&p, 1024), Err(IoError::BinaryFile)));
}

#[test]
fn test_file_too_large() {
    let dir = TempDir::new().unwrap();
    let p = dir.path().join("large.txt");
    std::fs::write(&p, "12345678901234567890").unwrap();
    assert!(matches!(
        read_text_safe(&p, 10),
        Err(IoError::TooLarge(_, _))
    ));
}

#[test]
fn test_file_not_found() {
    let result = read_text_safe("/nonexistent/file.txt", 1024);
    assert!(matches!(result, Err(IoError::NotFound(_))));
}
