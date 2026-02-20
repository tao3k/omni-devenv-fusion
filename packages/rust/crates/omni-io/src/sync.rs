//! Synchronous file I/O operations.
//!
//! Best for Python `allow_threads` usage via `PyO3`.

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
/// # Errors
/// Returns `IoError` when the file does not exist, exceeds `max_bytes`,
/// cannot be read, or cannot be decoded as text.
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

    let file_len = metadata.len();
    let capacity = usize::try_from(file_len).map_err(|_| IoError::TooLarge(file_len, max_bytes))?;
    let mut file = std_fs::File::open(path)?;
    let mut buffer = Vec::with_capacity(capacity);
    file.read_to_end(&mut buffer)?;

    decode_buffer(buffer)
}
