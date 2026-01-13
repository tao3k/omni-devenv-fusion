//! Core types for structural editing.
//!
//! Defines the data structures used throughout the editing pipeline.

use serde::Serialize;

/// Result of a structural replace operation.
///
/// Contains both the modified content and metadata about the changes made.
#[derive(Debug, Clone, Serialize)]
pub struct EditResult {
    /// Original content before modification.
    pub original: String,
    /// Modified content after replacement.
    pub modified: String,
    /// Number of replacements made.
    pub count: usize,
    /// Unified diff showing changes.
    pub diff: String,
    /// Individual edit locations.
    pub edits: Vec<EditLocation>,
}

/// Location of an individual edit within a file.
///
/// Provides precise position information for each replacement.
#[derive(Debug, Clone, Serialize)]
pub struct EditLocation {
    /// Line number (1-indexed).
    pub line: usize,
    /// Column number (1-indexed).
    pub column: usize,
    /// Original text that was replaced.
    pub original_text: String,
    /// New text after replacement.
    pub new_text: String,
}

/// Configuration for edit operations.
///
/// Controls behavior like file size limits and preview mode.
pub struct EditConfig {
    /// Maximum file size in bytes (default 1MB).
    pub max_file_size: u64,
    /// Maximum number of replacements per file.
    pub max_replacements: usize,
    /// Whether to preview only (no actual file modification).
    pub preview_only: bool,
}

impl Default for EditConfig {
    fn default() -> Self {
        Self {
            max_file_size: 1024 * 1024, // 1MB
            max_replacements: 100,
            preview_only: true, // Default to preview for safety
        }
    }
}
