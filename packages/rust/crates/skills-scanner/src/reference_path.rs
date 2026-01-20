//! Reference Path - Strongly typed path for require_refs.
//!
//! This module provides `ReferencePath`, a strongly-typed wrapper for
//! external documentation reference paths. It ensures:
//! - Not empty
//! - No absolute paths (security)
//! - No path traversal ".." sequences
//! - Valid file extension (.md, .pdf, .txt, etc.)

use schemars::JsonSchema as SchemarsJsonSchema;
use serde::{Deserialize, Serialize};

// =============================================================================
// Reference Path
// =============================================================================

/// Strongly-typed reference path for external documentation.
///
/// Ensures:
/// - Not empty
/// - Valid UTF-8
/// - No absolute paths (security)
/// - No path traversal ".." sequences
/// - Valid file extension (.md, .pdf, .txt, etc.)
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, SchemarsJsonSchema)]
#[serde(try_from = "String", into = "String")]
pub struct ReferencePath(String);

impl ReferencePath {
    /// Valid extensions for reference files.
    const VALID_EXTENSIONS: &[&str] = &["md", "pdf", "txt", "html", "json", "yaml", "yml"];

    /// Create a new ReferencePath from a string.
    ///
    /// Returns `Err` if the path is invalid.
    pub fn new(path: impl Into<String>) -> Result<Self, String> {
        let path = path.into();

        // Check not empty
        if path.trim().is_empty() {
            return Err("Reference path cannot be empty".to_string());
        }

        // Check no absolute paths
        if path.starts_with('/') {
            return Err(format!(
                "Reference path must be relative, got absolute path: {}",
                path
            ));
        }

        // Check no path traversal
        if path.contains("..") {
            return Err(format!(
                "Reference path cannot contain path traversal '..': {}",
                path
            ));
        }

        // Check valid extension
        let ext = path.split('.').last().unwrap_or("");
        if !ext.is_empty() && !Self::VALID_EXTENSIONS.contains(&ext) {
            return Err(format!(
                "Invalid reference file extension '{}'. Valid: {:?}",
                ext,
                Self::VALID_EXTENSIONS
            ));
        }

        Ok(Self(path))
    }

    /// Get the reference path as a string slice.
    #[must_use]
    pub fn as_str(&self) -> &str {
        &self.0
    }

    /// Get the file extension.
    #[must_use]
    pub fn extension(&self) -> Option<&str> {
        self.0.split('.').last()
    }

    /// Get the parent directory.
    #[must_use]
    pub fn parent(&self) -> Option<&str> {
        self.0.rsplitn(2, '/').nth(1)
    }
}

impl std::fmt::Display for ReferencePath {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}

impl From<ReferencePath> for String {
    fn from(val: ReferencePath) -> Self {
        val.0
    }
}

impl TryFrom<String> for ReferencePath {
    type Error = String;

    fn try_from(value: String) -> Result<Self, Self::Error> {
        Self::new(value)
    }
}

// =============================================================================
// Tests
// =============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reference_path_valid() {
        let path = ReferencePath::new("references/guide.md").unwrap();
        assert_eq!(path.as_str(), "references/guide.md");
        assert_eq!(path.extension(), Some("md"));
    }

    #[test]
    fn test_reference_path_empty() {
        assert!(ReferencePath::new("").is_err());
        assert!(ReferencePath::new("   ").is_err());
    }

    #[test]
    fn test_reference_path_absolute() {
        assert!(ReferencePath::new("/absolute/path.md").is_err());
    }

    #[test]
    fn test_reference_path_traversal() {
        assert!(ReferencePath::new("../escape.md").is_err());
        assert!(ReferencePath::new("dir/../../etc/passwd").is_err());
    }

    #[test]
    fn test_reference_path_invalid_extension() {
        assert!(ReferencePath::new("file.exe").is_err());
    }

    #[test]
    fn test_reference_path_valid_extensions() {
        for ext in ["md", "pdf", "txt", "html", "json", "yaml", "yml"] {
            let path = ReferencePath::new(&format!("doc.{}", ext)).unwrap();
            assert_eq!(path.extension(), Some(ext));
        }
    }
}
