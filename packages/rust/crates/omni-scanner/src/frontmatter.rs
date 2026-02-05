//! Shared YAML Frontmatter Parsing
//!
//! Provides common utilities for parsing YAML frontmatter from markdown files.
//! Used by both `skills` (SKILL.md) and `knowledge` (*.md) modules.

use serde::Deserialize;
use std::fs;

/// Extract YAML frontmatter from markdown content.
///
/// Returns `Some(String)` if frontmatter is found, `None` otherwise.
///
/// # Examples
///
/// ```ignore
/// let content = r#"---
/// name: "test"
/// version: "1.0"
/// ---
/// # Content
/// "#;
///
/// let frontmatter = extract_frontmatter(content).unwrap();
/// assert!(frontmatter.contains("name:"));
/// ```
pub fn extract_frontmatter(content: &str) -> Option<String> {
    let start_marker = "---";
    let end_marker = "---";

    // Find first --- marker
    let start = content.find(start_marker)?;
    let content_after_start = &content[start + start_marker.len()..];

    // Find closing --- marker
    let end = content_after_start.find(end_marker)?;

    Some(content_after_start[..end].to_string())
}

/// Parse YAML frontmatter content into a serde value.
///
/// # Errors
///
/// Returns an error if the YAML is invalid.
pub fn parse_frontmatter(yaml_content: &str) -> Result<serde_yaml::Value, serde_yaml::Error> {
    serde_yaml::from_str(yaml_content)
}

/// Generic frontmatter structure that can be extended for different use cases.
#[derive(Debug, Deserialize, PartialEq, Default)]
pub struct GenericFrontmatter {
    /// Document title.
    #[serde(default)]
    pub title: Option<String>,
    /// Human-readable description of the document.
    #[serde(default)]
    pub description: Option<String>,
    /// Category for organizing documents (e.g., "pattern", "technique").
    #[serde(default)]
    pub category: Option<String>,
    /// Tags for discovery and routing.
    #[serde(default)]
    pub tags: Option<Vec<String>>,
    /// Additional metadata as key-value pairs.
    #[serde(default)]
    pub metadata: Option<serde_yaml::Value>,
}

/// Read and parse frontmatter from a markdown file.
///
/// Returns the parsed frontmatter as a GenericFrontmatter, or None if the file doesn't exist
/// or has no valid frontmatter.
pub fn read_frontmatter_from_file(path: &std::path::Path) -> Option<GenericFrontmatter> {
    let content = fs::read_to_string(path).ok()?;
    parse_frontmatter_from_content(&content)
}

/// Read file and extract frontmatter content as string.
pub fn extract_frontmatter_from_file(path: &std::path::Path) -> Option<String> {
    let content = fs::read_to_string(path).ok()?;
    extract_frontmatter(&content)
}

/// Parse frontmatter from markdown content string.
pub fn parse_frontmatter_from_content(content: &str) -> Option<GenericFrontmatter> {
    let yaml_content = extract_frontmatter(content)?;
    serde_yaml::from_str(&yaml_content).ok()
}
