//! Error types for `OmniCell` execution.
//!
//! Follows ODF-EP: Explicit error enums with context.

use thiserror::Error;

/// Executor-specific errors.
#[derive(Error, Debug)]
pub enum ExecutorError {
    /// Security violation detected.
    #[error("Security violation: {0}")]
    SecurityViolation(String),

    /// System process error (spawn/fail).
    #[error("System error: {0}")]
    SystemError(String),

    /// Shell command returned non-zero exit code.
    #[error("Shell error (exit {0}): {1}")]
    ShellError(i32, String),

    /// JSON serialization/deserialization failed.
    #[error("Serialization error: {0}")]
    SerializationError(String),

    /// Command timeout.
    #[error("Timeout exceeded: {0}")]
    Timeout(String),

    /// Invalid configuration.
    #[error("Invalid configuration: {0}")]
    InvalidConfig(String),
}

/// Result type for executor operations.
pub type Result<T> = std::result::Result<T, ExecutorError>;
