//! Asynchronous file I/O operations.
//!
//! Powered by Tokio for non-blocking I/O.

use std::path::Path;

use tokio::fs as tokio_fs;
use tokio::io::AsyncReadExt;

use crate::detect::decode_buffer;
use crate::error::IoError;

/// Read text from a file with size and binary checks (asynchronous).
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
/// use omni_io::read_text_safe_async;
///
/// let content = read_text_safe_async("README.md", 1024 * 1024).await?;
/// ```
pub async fn read_text_safe_async<P: AsRef<Path>>(
    path: P,
    max_bytes: u64,
) -> Result<String, IoError> {
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
