#![allow(clippy::doc_markdown)]

//! omni-io - Safe and efficient file I/O for Omni DevEnv
//!
//! Features:
//! - Dual API: Sync (std::fs) for Python bindings, Async (tokio::fs) for Rust core.
//! - Safety: Binary detection & Size limits.
//! - Lightweight: Zero-dependency UTF-8 fallback.

use std::path::Path;
use thiserror::Error;
use memchr::memchr;

// Re-export standard/tokio fs traits if needed internally
use std::fs as std_fs;
use std::io::Read;
use tokio::fs as tokio_fs;
use tokio::io::AsyncReadExt;

/// Error types for file I/O operations.
#[derive(Error, Debug)]
pub enum IoError {
    /// File does not exist
    #[error("File not found: {0}")]
    NotFound(String),
    /// File exceeds size limit
    #[error("File too large: {0} bytes (limit: {1})")]
    TooLarge(u64, u64),
    /// File contains binary content
    #[error("Binary file detected")]
    BinaryFile,
    /// Low-level I/O error
    #[error("IO error: {0}")]
    System(#[from] std::io::Error),
    /// Invalid UTF-8 encoding
    #[error("UTF-8 decoding error")]
    Encoding,
}

/// Quick binary detection - checks first 8KB for NULL bytes
fn is_binary(buffer: &[u8]) -> bool {
    let check_len = std::cmp::min(buffer.len(), 8192);
    memchr(0, &buffer[..check_len]).is_some()
}

/// Helper: Decode bytes to String with lossy fallback (Zero-dep version)
fn decode_buffer(buffer: Vec<u8>) -> Result<String, IoError> {
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

// ============================================================================
// Synchronous API (Best for Python `allow_threads` usage)
// ============================================================================

/// Read text from a file with size and binary checks (synchronous).
///
/// # Arguments
/// * `path` - Path to the file
/// * `max_bytes` - Maximum file size in bytes
///
/// # Returns
/// Decoded text content or an error
pub fn read_text_safe<P: AsRef<Path>>(path: P, max_bytes: u64) -> Result<String, IoError> {
    let path = path.as_ref();
    let metadata = std_fs::metadata(path)
        .map_err(|_| IoError::NotFound(path.to_string_lossy().to_string()))?;

    if metadata.len() > max_bytes {
        return Err(IoError::TooLarge(metadata.len(), max_bytes));
    }

    let mut file = std_fs::File::open(path)?;
    let mut buffer = Vec::with_capacity(metadata.len() as usize);
    file.read_to_end(&mut buffer)?;

    decode_buffer(buffer)
}

// ============================================================================
// Asynchronous API (Powered by Tokio)
// ============================================================================

/// Read text from a file with size and binary checks (asynchronous).
///
/// # Arguments
/// * `path` - Path to the file
/// * `max_bytes` - Maximum file size in bytes
///
/// # Returns
/// Decoded text content or an error
pub async fn read_text_safe_async<P: AsRef<Path>>(path: P, max_bytes: u64) -> Result<String, IoError> {
    let path = path.as_ref();
    let metadata = tokio_fs::metadata(path)
        .await
        .map_err(|_| IoError::NotFound(path.to_string_lossy().to_string()))?;

    if metadata.len() > max_bytes {
        return Err(IoError::TooLarge(metadata.len(), max_bytes));
    }

    let mut file = tokio_fs::File::open(path).await?;
    let mut buffer = Vec::with_capacity(metadata.len() as usize);
    file.read_to_end(&mut buffer).await?;

    decode_buffer(buffer)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;
    use tokio::io::AsyncWriteExt;

    #[test]
    fn test_sync_read() {
        let dir = TempDir::new().unwrap();
        let p = dir.path().join("sync.txt");
        std_fs::write(&p, "Sync Read").unwrap();
        assert_eq!(read_text_safe(&p, 1024).unwrap(), "Sync Read");
    }

    #[test]
    fn test_sync_binary() {
        let dir = TempDir::new().unwrap();
        let p = dir.path().join("binary.bin");
        let mut file = std_fs::File::create(&p).unwrap();
        file.write_all(b"\x00\x01\x02\x03").unwrap();
        assert!(matches!(read_text_safe(&p, 1024), Err(IoError::BinaryFile)));
    }

    #[tokio::test]
    async fn test_async_read() {
        let dir = TempDir::new().unwrap();
        let p = dir.path().join("async.txt");
        tokio_fs::write(&p, "Async Read").await.unwrap();
        assert_eq!(read_text_safe_async(&p, 1024).await.unwrap(), "Async Read");
    }

    #[tokio::test]
    async fn test_async_binary() {
        let dir = TempDir::new().unwrap();
        let p = dir.path().join("async_binary.bin");
        let mut file = tokio_fs::File::create(&p).await.unwrap();
        file.write_all(b"\x00\x01\x02\x03").await.unwrap();
        assert!(matches!(read_text_safe_async(&p, 1024).await, Err(IoError::BinaryFile)));
    }
}
