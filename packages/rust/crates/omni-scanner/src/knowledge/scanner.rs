//! Knowledge Scanner - Scans knowledge documents with YAML frontmatter.
//!
//! This module provides the `KnowledgeScanner` struct which scans knowledge
//! directories and extracts metadata from markdown files with YAML frontmatter.
//!
//! # Architecture
//!
//! Knowledge documents follow a simple structure:
//! - `*.md` files in knowledge directories
//! - YAML frontmatter for metadata (category, tags, title, etc.)
//!
//! # Example
//!
//! ```ignore
//! use omni_scanner::knowledge::KnowledgeScanner;
//!
//! let scanner = KnowledgeScanner::new();
//! let entries = scanner.scan_all(PathBuf::from("assets/knowledge")).unwrap();
//!
//! for entry in entries {
//!     println!("Knowledge: {} - {:?}", entry.title, entry.category);
//! }
//! ```

use std::fs;
use std::path::{Path, PathBuf};
use walkdir::WalkDir;

use crate::frontmatter::extract_frontmatter;
use crate::knowledge::types::{KnowledgeCategory, KnowledgeEntry};
use sha2::{Digest, Sha256};

/// YAML frontmatter structure for knowledge documents.
///
/// ```yaml
/// ---
/// title: "Git Commit Best Practices"
/// description: "Guidelines for writing effective commit messages"
/// category: "pattern"
/// tags: ["git", "commit", "best-practices"]
/// authors: ["developer@example.com"]
/// version: "1.0.0"
/// ---
/// ```
#[derive(Debug, Default, serde::Deserialize)]
struct KnowledgeFrontmatter {
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    description: Option<String>,
    #[serde(default)]
    category: Option<String>,
    #[serde(default)]
    tags: Option<Vec<String>>,
    #[serde(default)]
    authors: Option<Vec<String>>,
    #[serde(default)]
    source: Option<String>,
    #[serde(default)]
    version: Option<String>,
}

/// Knowledge Scanner - Scans and indexes knowledge documents.
///
/// Scans knowledge directories to extract:
/// - Title, description, category from frontmatter
/// - Tags for semantic search
/// - File hashes for incremental indexing
///
/// # Usage
///
/// ```ignore
/// use omni_scanner::knowledge::KnowledgeScanner;
///
/// let scanner = KnowledgeScanner::new();
///
/// // Scan single directory
/// let entries = scanner.scan_all(PathBuf::from("assets/knowledge")).unwrap();
///
/// // Scan with filtering
/// let patterns = scanner.scan_category(PathBuf::from("assets/knowledge"), "pattern").unwrap();
/// ```
#[derive(Debug)]
pub struct KnowledgeScanner;

impl KnowledgeScanner {
    /// Create a new knowledge scanner with default settings.
    #[must_use]
    pub fn new() -> Self {
        Self
    }

    /// Scan a single knowledge document.
    ///
    /// # Arguments
    ///
    /// * `path` - Path to the markdown file
    /// * `base_path` - Base path for calculating relative paths
    ///
    /// # Returns
    ///
    /// `Ok(Some(entry))` if document is valid, `Ok(None)` if not a valid markdown.
    pub fn scan_document(&self, path: &Path, base_path: &Path) -> Option<KnowledgeEntry> {
        if !path.exists() || !path.is_file() {
            return None;
        }

        // Only process markdown files
        if path.extension().map_or(true, |ext| ext != "md") {
            return None;
        }

        let content = fs::read_to_string(path).ok()?;
        let relative_path = path.strip_prefix(base_path).unwrap_or(path);

        // Compute file hash
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        let file_hash = format!("{:x}", hasher.finalize());

        // Generate ID from path using SHA256 hash (truncated)
        let path_str = relative_path.to_string_lossy();
        let mut path_hasher = Sha256::new();
        path_hasher.update(path_str.as_bytes());
        let hash_result = path_hasher.finalize();
        let id = hex::encode(&hash_result[..16]);

        // Parse frontmatter
        let (metadata, content_without_frontmatter) = match extract_frontmatter(&content) {
            Some(fm) => {
                let metadata: KnowledgeFrontmatter = serde_yaml::from_str(&fm).ok()?;
                let content_after = content[fm.len() + 6..].to_string(); // Remove frontmatter
                (metadata, content_after)
            }
            None => (KnowledgeFrontmatter::default(), content),
        };

        // Generate title from frontmatter or filename
        let title = metadata.title.unwrap_or_else(|| {
            path.file_stem()
                .and_then(|s| s.to_str())
                .map(|s| s.replace(['-', '_'], " "))
                .unwrap_or_else(|| relative_path.to_string_lossy().into_owned())
        });

        // Parse category
        let category = metadata
            .category
            .as_ref()
            .and_then(|c| c.parse().ok())
            .unwrap_or(KnowledgeCategory::Unknown);

        // Generate content preview (first 500 chars)
        let content_preview = content_without_frontmatter
            .lines()
            .take(10)
            .collect::<Vec<_>>()
            .join("\n")
            .trim()
            .chars()
            .take(500)
            .collect();

        Some(KnowledgeEntry {
            id,
            file_path: relative_path.to_string_lossy().into_owned(),
            title,
            description: metadata.description.unwrap_or_default(),
            category,
            tags: metadata.tags.unwrap_or_default(),
            authors: metadata.authors.unwrap_or_default(),
            source: metadata.source,
            version: metadata.version.unwrap_or_default(),
            file_hash,
            content_preview,
        })
    }

    /// Scan a knowledge directory for all documents with parallel processing.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the knowledge directory
    /// * `depth` - Maximum directory depth (-1 for unlimited)
    ///
    /// # Returns
    ///
    /// Vector of discovered knowledge entries.
    pub fn scan_all(
        &self,
        base_path: &Path,
        depth: Option<i32>,
    ) -> Result<Vec<KnowledgeEntry>, Box<dyn std::error::Error>> {
        use rayon::prelude::*;

        if !base_path.exists() {
            log::warn!("Knowledge base directory not found: {:?}", base_path);
            return Ok(Vec::new());
        }

        let max_depth = depth.unwrap_or(-1);

        // Collect all markdown files first
        let md_files: Vec<PathBuf> = WalkDir::new(base_path)
            .follow_links(false)
            .max_depth(if max_depth > 0 {
                max_depth as usize + 1
            } else {
                usize::MAX
            })
            .into_iter()
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.file_type().is_file() && e.path().extension().map_or(false, |ext| ext == "md")
            })
            .map(|e| e.path().to_path_buf())
            .collect();

        // Process in parallel using rayon
        let entries: Vec<KnowledgeEntry> = md_files
            .par_iter()
            .filter_map(|path| self.scan_document(path, base_path))
            .collect();

        log::info!(
            "Scanned {} knowledge documents from {:?}",
            entries.len(),
            base_path
        );

        Ok(entries)
    }

    /// Scan and filter knowledge by category.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the knowledge directory
    /// * `category` - Category to filter by
    ///
    /// # Returns
    ///
    /// Vector of knowledge entries matching the category.
    pub fn scan_category(
        &self,
        base_path: &Path,
        category: &str,
    ) -> Result<Vec<KnowledgeEntry>, Box<dyn std::error::Error>> {
        let target_category: KnowledgeCategory =
            category.parse().unwrap_or(KnowledgeCategory::Unknown);
        let all_entries = self.scan_all(base_path, None)?;

        Ok(all_entries
            .into_iter()
            .filter(|e| e.category == target_category)
            .collect())
    }

    /// Scan and filter knowledge by tags.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the knowledge directory
    /// * `tags` - Tags to filter by (entries matching ANY tag)
    ///
    /// # Returns
    ///
    /// Vector of knowledge entries matching any of the tags.
    pub fn scan_with_tags(
        &self,
        base_path: &Path,
        tags: &[String],
    ) -> Result<Vec<KnowledgeEntry>, Box<dyn std::error::Error>> {
        let all_entries = self.scan_all(base_path, None)?;

        if tags.is_empty() {
            return Ok(all_entries);
        }

        Ok(all_entries
            .into_iter()
            .filter(|e| e.tags.iter().any(|t| tags.contains(t)))
            .collect())
    }

    /// Get all unique tags from a knowledge directory.
    ///
    /// # Arguments
    ///
    /// * `base_path` - Path to the knowledge directory
    ///
    /// # Returns
    ///
    /// Vector of unique tags with their counts.
    pub fn get_tags(
        &self,
        base_path: &Path,
    ) -> Result<Vec<(String, usize)>, Box<dyn std::error::Error>> {
        let entries = self.scan_all(base_path, None)?;

        let mut tag_counts: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();
        for entry in entries {
            for tag in &entry.tags {
                *tag_counts.entry(tag.clone()).or_insert(0) += 1;
            }
        }

        let mut tags: Vec<(String, usize)> = tag_counts.into_iter().collect();
        tags.sort_by(|a, b| b.1.cmp(&a.1)); // Sort by count descending

        Ok(tags)
    }
}

impl Default for KnowledgeScanner {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn test_scan_document_with_frontmatter() {
        let temp_dir = TempDir::new().unwrap();
        let doc_path = temp_dir.path().join("git-commits.md");

        let content = r#"---
title: "Git Commit Best Practices"
description: "Guidelines for writing effective commit messages"
category: "pattern"
tags: ["git", "commit", "best-practices"]
authors: ["developer@example.com"]
version: "1.0.0"
---

# Git Commit Best Practices

This document describes best practices for git commits.
"#;

        let mut file = File::create(&doc_path).unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let scanner = KnowledgeScanner::new();
        let entry = scanner.scan_document(&doc_path, temp_dir.path()).unwrap();

        assert_eq!(entry.title, "Git Commit Best Practices");
        assert_eq!(
            entry.description,
            "Guidelines for writing effective commit messages"
        );
        assert_eq!(entry.category, KnowledgeCategory::Pattern);
        assert_eq!(entry.tags, vec!["git", "commit", "best-practices"]);
        assert!(!entry.file_hash.is_empty());
    }

    #[test]
    fn test_scan_document_without_frontmatter() {
        let temp_dir = TempDir::new().unwrap();
        let doc_path = temp_dir.path().join("readme.md");

        let content = r#"# README

This is a simple readme without frontmatter.
"#;

        let mut file = File::create(&doc_path).unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let scanner = KnowledgeScanner::new();
        let entry = scanner.scan_document(&doc_path, temp_dir.path()).unwrap();

        // Title should be derived from filename
        assert_eq!(entry.title, "readme");
        assert_eq!(entry.category, KnowledgeCategory::Unknown);
        assert!(entry.tags.is_empty());
    }

    #[test]
    fn test_scan_document_non_markdown() {
        let temp_dir = TempDir::new().unwrap();
        let doc_path = temp_dir.path().join("data.json");

        std::fs::write(&doc_path, r#"{"key": "value"}"#).unwrap();

        let scanner = KnowledgeScanner::new();
        let entry = scanner.scan_document(&doc_path, temp_dir.path());

        assert!(entry.is_none());
    }

    #[test]
    fn test_scan_all() {
        let temp_dir = TempDir::new().unwrap();

        // Create multiple docs
        let docs = [
            (
                "doc1.md",
                r#"---
title: "Document 1"
category: "pattern"
---
# Doc 1
"#,
            ),
            (
                "doc2.md",
                r#"---
title: "Document 2"
category: "note"
---
# Doc 2
"#,
            ),
            (
                "sub/doc3.md",
                r#"---
title: "Document 3"
category: "technique"
---
# Doc 3
"#,
            ),
        ];

        for (name, content) in &docs {
            let path = temp_dir.path().join(name);
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).unwrap();
            }
            std::fs::write(&path, content).unwrap();
        }

        let scanner = KnowledgeScanner::new();
        let entries = scanner.scan_all(temp_dir.path(), None).unwrap();

        assert_eq!(entries.len(), 3);
        assert!(entries.iter().any(|e| e.title == "Document 1"));
        assert!(entries.iter().any(|e| e.title == "Document 2"));
        assert!(entries.iter().any(|e| e.title == "Document 3"));
    }

    #[test]
    fn test_scan_category() {
        let temp_dir = TempDir::new().unwrap();

        let docs = [
            (
                "pattern1.md",
                r#"---
title: "Pattern 1"
category: "pattern"
---
"#,
            ),
            (
                "pattern2.md",
                r#"---
title: "Pattern 2"
category: "pattern"
---
"#,
            ),
            (
                "note1.md",
                r#"---
title: "Note 1"
category: "note"
---
"#,
            ),
        ];

        for (name, content) in &docs {
            std::fs::write(temp_dir.path().join(name), content).unwrap();
        }

        let scanner = KnowledgeScanner::new();
        let patterns = scanner.scan_category(temp_dir.path(), "pattern").unwrap();

        assert_eq!(patterns.len(), 2);
        assert!(
            patterns
                .iter()
                .all(|e| e.category == KnowledgeCategory::Pattern)
        );
    }

    #[test]
    fn test_get_tags() {
        let temp_dir = TempDir::new().unwrap();

        let docs = [
            (
                "doc1.md",
                r#"---
title: "Doc 1"
tags: ["rust", "programming"]
---
"#,
            ),
            (
                "doc2.md",
                r#"---
title: "Doc 2"
tags: ["rust", "cargo"]
---
"#,
            ),
            (
                "doc3.md",
                r#"---
title: "Doc 3"
tags: ["python"]
---
"#,
            ),
        ];

        for (name, content) in &docs {
            std::fs::write(temp_dir.path().join(name), content).unwrap();
        }

        let scanner = KnowledgeScanner::new();
        let tags = scanner.get_tags(temp_dir.path()).unwrap();

        // rust appears 2 times, programming 1, cargo 1, python 1
        assert_eq!(tags.len(), 4);
        // Should be sorted by count descending
        assert_eq!(tags[0].0, "rust");
        assert_eq!(tags[0].1, 2);
    }
}
