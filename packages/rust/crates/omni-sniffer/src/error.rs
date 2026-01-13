//! Error types for sniffer operations.
//!
//! Follows ODF-REP: Library crates use `thiserror` for explicit error enums.

use thiserror::Error;

/// Errors for `OmniSniffer` operations.
#[derive(Debug, Error)]
pub enum SnifferError {
    /// Cannot open the git repository
    #[error("Failed to open git repository at {0}")]
    RepoOpen(std::path::PathBuf),

    /// Git repository has no head (empty repo)
    #[error("Git repository has no head reference")]
    NoHead,

    /// Git status scan failed
    #[error("Git status scan failed: {0}")]
    StatusScan(String),

    /// Failed to read the scratchpad file
    #[error("Failed to read scratchpad: {0}")]
    ScratchpadRead(std::path::PathBuf),
}
