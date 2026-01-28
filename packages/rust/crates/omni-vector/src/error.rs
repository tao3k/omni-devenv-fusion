//! Error types for vector store operations.

pub use lance::deps::arrow_schema::ArrowError;
use thiserror::Error;
use tokio::task::JoinError;

/// Errors for vector store operations
#[derive(Error, Debug)]
pub enum VectorStoreError {
    /// IO error during file operations
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    /// Tokio task join error
    #[error("Tokio task join error: {0}")]
    JoinError(#[from] JoinError), // Added

    /// `LanceDB` error
    #[error("LanceDB error: {0}")]
    LanceDB(#[from] lance::Error),

    /// Arrow error
    #[error("Arrow error: {0}")]
    Arrow(#[from] ArrowError),

    /// Serialization error
    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    /// Tantivy error (keyword search)
    #[error("Tantivy error: {0}")]
    Tantivy(#[from] tantivy::TantivyError),

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

    /// General error with message
    #[error("{0}")]
    General(String),
}
