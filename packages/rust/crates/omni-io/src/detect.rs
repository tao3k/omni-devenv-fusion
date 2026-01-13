//! Binary detection and decoding utilities.
//!
//! Quick binary detection using NULL byte scanning.

use memchr::memchr;

use crate::error::IoError;

/// Quick binary detection - checks first 8KB for NULL bytes.
///
/// Files containing NULL bytes in the first 8KB are considered binary.
/// This is a fast heuristic that works well for most text files.
pub fn is_binary(buffer: &[u8]) -> bool {
    let check_len = std::cmp::min(buffer.len(), 8192);
    memchr(0, &buffer[..check_len]).is_some()
}

/// Decode bytes to String with lossy fallback.
///
/// First checks for binary content, then attempts UTF-8 decoding.
/// Invalid UTF-8 sequences are replaced with U+FFFD.
pub fn decode_buffer(buffer: Vec<u8>) -> Result<String, IoError> {
    if is_binary(&buffer) {
        return Err(IoError::BinaryFile);
    }

    match String::from_utf8(buffer) {
        Ok(s) => Ok(s),
        Err(e) => {
            // Standard library lossy conversion: replaces errors with U+FFFD
            Ok(String::from_utf8_lossy(&e.into_bytes()).into_owned())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_binary_detection() {
        assert!(is_binary(b"\x00\x01\x02\x03"));
        assert!(!is_binary(b"Hello, world!"));
        assert!(!is_binary(b""));
    }

    #[test]
    fn test_decode_text() {
        let result = decode_buffer(b"Hello, world!".to_vec());
        assert_eq!(result.unwrap(), "Hello, world!");
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
}
