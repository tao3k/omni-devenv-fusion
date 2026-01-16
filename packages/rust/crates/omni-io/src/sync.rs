//! Synchronous file I/O operations.
//!
//! Best for Python `allow_threads` usage via PyO3.

use std::fs as std_fs;
use std::io::Read;
use std::path::Path;

use crate::detect::decode_buffer;
use crate::error::IoError;

/// Read text from a file with size and binary checks (synchronous).
///
/// # Arguments
/// * `path` - Path to the file
/// * `max_bytes` - Maximum file size in bytes
///
/// # Returns
/// Decoded text content or an error.
///
/// # Example
///
/// ```rust,ignore
/// use omni_io::read_text_safe;
///
/// let content = read_text_safe("README.md", 1024 * 1024)?;
/// ```
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::TempDir;

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

    #[test]
    fn test_file_too_large() {
        let dir = TempDir::new().unwrap();
        let p = dir.path().join("large.txt");
        std_fs::write(&p, "12345678901234567890").unwrap();
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
}
