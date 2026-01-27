//! Sync Module - Efficient difference detection for skill index updates.
//!
//! Provides fast comparison between scanned tools and existing index entries
//! using file_hash for quick filtering.
//!
//! # Architecture
//!
//! ```text
//! scanned_tools (from Rust scanner) ──┐
//!                                      ├──> SyncReport ──> Index Update Decision
//! existing_tools (from JSON index) ───┘
//! ```
//!
//! # Usage
//!
//! ```ignore
//! use skills_scanner::{calculate_sync_ops, SyncReport};
//!
//! let report = calculate_sync_ops(scanned_tools, existing_tools);
//! println!("Added: {}, Updated: {}, Deleted: {}",
//!     report.added.len(), report.updated.len(), report.deleted.len());
//! ```

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

use crate::skill_metadata::{IndexToolEntry, ToolRecord};

/// Report of sync operations needed between scanned and existing tools.
#[derive(Debug, Serialize, Deserialize, Default)]
pub struct SyncReport {
    /// Tools that are new and need to be added
    pub added: Vec<ToolRecord>,
    /// Tools that have changed and need to be updated
    pub updated: Vec<ToolRecord>,
    /// Tool names that were deleted
    pub deleted: Vec<String>,
    /// Count of unchanged tools (fast path hit)
    pub unchanged_count: usize,
}

impl SyncReport {
    /// Check if any changes need to be applied.
    pub fn has_changes(&self) -> bool {
        !self.added.is_empty() || !self.updated.is_empty() || !self.deleted.is_empty()
    }

    /// Total count of changed items.
    pub fn change_count(&self) -> usize {
        self.added.len() + self.updated.len() + self.deleted.len()
    }
}

/// Calculate sync operations between scanned tools and existing index.
///
/// Uses a two-tier comparison strategy:
/// 1. **Fast path**: Compare `file_hash` - if identical, tool is unchanged
/// 2. **Slow path**: If hashes differ, compare description, category, input_schema, keywords
///
/// Args:
///   scanned_tools: Tools from the current scan
///   existing_tools: Tools from the existing index
///
/// Returns:
///   SyncReport with lists of added, updated, deleted, and unchanged tools
pub fn calculate_sync_ops(
    scanned_tools: Vec<ToolRecord>,
    existing_tools: Vec<IndexToolEntry>,
) -> SyncReport {
    // Build lookup map for existing tools by name
    let existing_by_name: HashMap<String, &IndexToolEntry> = existing_tools
        .iter()
        .map(|tool| (tool.name.clone(), tool))
        .collect();

    // Track which existing tools were matched
    let mut matched_existing: HashMap<String, bool> = existing_tools
        .iter()
        .map(|tool| (tool.name.clone(), false))
        .collect();

    let mut added: Vec<ToolRecord> = Vec::new();
    let mut updated: Vec<ToolRecord> = Vec::new();
    let mut unchanged_count: usize = 0;

    // Process scanned tools
    for scanned in scanned_tools {
        if let Some(existing) = existing_by_name.get(&scanned.tool_name) {
            matched_existing.insert(scanned.tool_name.clone(), true);

            // Fast path: check file_hash
            if scanned.file_hash == existing.file_hash {
                // Hash matches - tool is unchanged
                unchanged_count += 1;
            } else {
                // Slow path: check if meaningful fields changed
                if hasmeaningful_change(&scanned, existing) {
                    updated.push(scanned);
                } else {
                    unchanged_count += 1;
                }
            }
        } else {
            // New tool
            added.push(scanned);
        }
    }

    // Find deleted tools (existing tools that were not matched)
    let deleted: Vec<String> = matched_existing
        .into_iter()
        .filter(|(_name, matched)| !matched)
        .map(|(name, _)| name)
        .collect();

    SyncReport {
        added,
        updated,
        deleted,
        unchanged_count,
    }
}

/// Check if a tool has meaningful changes (not just hash).
fn hasmeaningful_change(scanned: &ToolRecord, existing: &IndexToolEntry) -> bool {
    // Compare meaningful fields (description, category, input_schema)
    // Note: keywords are not stored in IndexToolEntry, only in ToolRecord
    scanned.description != existing.description
        || scanned.category != existing.category
        || scanned.input_schema != existing.input_schema
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_tool_record(
        name: &str,
        description: &str,
        category: &str,
        file_hash: &str,
        _keywords: Vec<String>,
    ) -> ToolRecord {
        ToolRecord {
            tool_name: name.to_string(),
            description: description.to_string(),
            skill_name: "test".to_string(),
            file_path: format!("/test/{}", name),
            function_name: name.to_string(),
            execution_mode: "script".to_string(),
            keywords: _keywords,
            file_hash: file_hash.to_string(),
            docstring: String::new(),
            category: category.to_string(),
            annotations: Default::default(),
            parameters: vec![],
            input_schema: r#"{"type": "object"}"#.to_string(),
        }
    }

    fn create_index_entry(
        name: &str,
        description: &str,
        category: &str,
        file_hash: &str,
        _keywords: Vec<String>,
    ) -> IndexToolEntry {
        IndexToolEntry {
            name: name.to_string(),
            description: description.to_string(),
            category: category.to_string(),
            input_schema: r#"{"type": "object"}"#.to_string(),
            file_hash: file_hash.to_string(),
        }
    }

    #[test]
    fn test_identical_tools_are_unchanged() {
        let scanned = vec![create_tool_record(
            "test_tool",
            "A test tool",
            "testing",
            "abc123",
            vec!["test".to_string()],
        )];
        let existing = vec![create_index_entry(
            "test_tool",
            "A test tool",
            "testing",
            "abc123",
            vec!["test".to_string()],
        )];

        let report = calculate_sync_ops(scanned, existing);

        assert_eq!(report.added.len(), 0);
        assert_eq!(report.updated.len(), 0);
        assert_eq!(report.deleted.len(), 0);
        assert_eq!(report.unchanged_count, 1);
    }

    #[test]
    fn test_new_tool_is_added() {
        let scanned = vec![create_tool_record(
            "new_tool",
            "A new tool",
            "testing",
            "xyz789",
            vec!["new".to_string()],
        )];
        let existing: Vec<IndexToolEntry> = vec![];

        let report = calculate_sync_ops(scanned, existing);

        assert_eq!(report.added.len(), 1);
        assert_eq!(report.updated.len(), 0);
        assert_eq!(report.deleted.len(), 0);
        assert_eq!(report.unchanged_count, 0);
    }

    #[test]
    fn test_changed_tool_is_updated() {
        let scanned = vec![create_tool_record(
            "test_tool",
            "Updated description",
            "testing",
            "new_hash",
            vec!["test".to_string()],
        )];
        let existing = vec![create_index_entry(
            "test_tool",
            "Old description",
            "testing",
            "old_hash",
            vec!["test".to_string()],
        )];

        let report = calculate_sync_ops(scanned, existing);

        assert_eq!(report.added.len(), 0);
        assert_eq!(report.updated.len(), 1);
        assert_eq!(report.deleted.len(), 0);
        assert_eq!(report.unchanged_count, 0);
    }

    #[test]
    fn test_deleted_tool_is_reported() {
        let scanned: Vec<ToolRecord> = vec![];
        let existing = vec![create_index_entry(
            "deleted_tool",
            "A deleted tool",
            "testing",
            "hash123",
            vec!["deleted".to_string()],
        )];

        let report = calculate_sync_ops(scanned, existing);

        assert_eq!(report.added.len(), 0);
        assert_eq!(report.updated.len(), 0);
        assert_eq!(report.deleted.len(), 1);
        assert_eq!(report.unchanged_count, 0);
        assert!(report.deleted.contains(&"deleted_tool".to_string()));
    }

    #[test]
    fn test_mixed_changes() {
        let scanned = vec![
            create_tool_record("new_tool", "New", "testing", "hash1", vec![]),
            create_tool_record("changed_tool", "Changed", "testing", "hash2", vec![]),
            create_tool_record("unchanged_tool", "Same", "testing", "hash3", vec![]),
        ];
        let existing = vec![
            create_index_entry("changed_tool", "Old", "testing", "hash_old", vec![]),
            create_index_entry("unchanged_tool", "Same", "testing", "hash3", vec![]),
            create_index_entry("deleted_tool", "Gone", "testing", "hash4", vec![]),
        ];

        let report = calculate_sync_ops(scanned, existing);

        assert_eq!(report.added.len(), 1);
        assert_eq!(report.updated.len(), 1);
        assert_eq!(report.deleted.len(), 1);
        assert_eq!(report.unchanged_count, 1);
        assert!(report.has_changes());
        assert_eq!(report.change_count(), 3);
    }
}
