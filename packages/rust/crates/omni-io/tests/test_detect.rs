//! Tests for detect module - binary detection and text decoding.

use omni_io::{IoError, decode_buffer, is_binary};

#[test]
fn test_binary_detection() {
    assert!(is_binary(b"\x00\x01\x02\x03"));
    assert!(!is_binary(b"Hello, world!"));
    assert!(!is_binary(b""));
}

#[test]
fn test_decode_text() -> Result<(), Box<dyn std::error::Error>> {
    let result = decode_buffer(b"Hello, world!".to_vec())?;
    assert_eq!(result, "Hello, world!");
    Ok(())
}

#[test]
fn test_decode_binary() {
    let result = decode_buffer(b"\x00\x01\x02".to_vec());
    assert!(matches!(result, Err(IoError::BinaryFile)));
}

#[test]
fn test_decode_utf8_lossy() {
    // Invalid UTF-8 sequence
    let result = decode_buffer(vec![0x48, 0x65, 0x6c, 0xff, 0x6f]);
    assert!(result.is_ok());
}
