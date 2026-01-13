//! Error types for file I/O operations.
//!
//! Follows ODF-REP: Library crates use `thiserror` for explicit error enums.

use thiserror::Error;

/// Error types for file I/O operations.
///
/// Each variant represents a specific failure mode in the I/O pipeline.
#[derive(Error, Debug)]
pub enum IoError {
    /// File does not exist.
    #[error("File not found: {0}")]
    NotFound(String),

    /// File exceeds size limit.
    #[error("File too large: {0} bytes (limit: {1})")]
    TooLarge(u64, u64),

    /// File contains binary content (NULL bytes detected).
    #[error("Binary file detected")]
    BinaryFile,

    /// Low-level I/O error from std::io.
    #[error("IO error: {0}")]
    System(#[from] std::io::Error),

    /// Invalid UTF-8 encoding.
    #[error("UTF-8 decoding error")]
    Encoding,
}
