//! Error types for tag operations.
//!
//! Follows ODF-REP: Library crates use `thiserror` for explicit error enums.

use thiserror::Error;

use omni_io::IoError;

/// Error types for tag extraction
#[derive(Error, Debug)]
pub enum TagError {
    /// File I/O error
    #[error("IO error: {0}")]
    Io(#[from] IoError),
    /// Failed to parse source code
    #[error("Parse error: {0}")]
    Parse(String),
    /// Unsupported programming language
    #[error("Unsupported language: {0}")]
    UnsupportedLanguage(String),
}

/// Error types for search operations
#[derive(Error, Debug)]
pub enum SearchError {
    /// File I/O error
    #[error("IO error: {0}")]
    Io(#[from] IoError),
    /// Failed to parse source code
    #[error("Parse error: {0}")]
    Parse(String),
    /// Invalid ast-grep pattern
    #[error("Pattern error: {0}")]
    Pattern(String),
    /// Unsupported programming language
    #[error("Unsupported language: {0}")]
    UnsupportedLanguage(String),
    /// Specified path is not a file
    #[error("Path is not a file: {0}")]
    NotAFile(String),
}
