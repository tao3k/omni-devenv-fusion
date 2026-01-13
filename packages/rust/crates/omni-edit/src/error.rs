//! Error types for structural editing operations.
//!
//! Follows ODF-REP: Library crates use `thiserror` for explicit error enums.

use omni_io::IoError;
use thiserror::Error;

/// Error types for edit operations.
///
/// Each variant represents a specific failure mode in the editing pipeline.
#[derive(Error, Debug)]
pub enum EditError {
    /// File I/O error (reading source file).
    #[error("IO error: {0}")]
    Io(#[from] IoError),

    /// Failed to parse source code into AST.
    #[error("Parse error: {0}")]
    Parse(String),

    /// Invalid ast-grep pattern syntax.
    #[error("Pattern error: {0}")]
    Pattern(String),

    /// Language not supported by ast-grep.
    #[error("Unsupported language: {0}")]
    UnsupportedLanguage(String),

    /// Replacement operation failed.
    #[error("Replacement error: {0}")]
    Replacement(String),
}
