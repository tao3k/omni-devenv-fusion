//! Error types for vector store operations.

use lance::deps::arrow_schema::ArrowError;
use thiserror::Error;

/// Errors for vector store operations
#[derive(Error, Debug)]
pub enum VectorStoreError {
    /// IO error during file operations
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// `LanceDB` error
    #[error("LanceDB error: {0}")]
    LanceDB(#[from] lance::Error),

    /// Arrow error
    #[error("Arrow error: {0}")]
    Arrow(#[from] ArrowError),

    /// Serialization error
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Table not found
    #[error("Table not found: {0}")]
    TableNotFound(String),

    /// Invalid embedding dimension
    #[error("Invalid dimension: expected {expected}, got {actual}")]
    InvalidDimension {
        /// Expected dimension
        expected: usize,
        /// Actual dimension
        actual: usize,
    },

    /// Empty dataset
    #[error("Empty dataset")]
    EmptyDataset,

    /// Invalid embedding dimension (zero or negative)
    #[error("Embedding dimension must be positive")]
    InvalidEmbeddingDimension,

    /// General anyhow error (Script scanning)
    #[error("Script scanning error: {0}")]
    ScriptScanning(#[from] anyhow::Error),
}
