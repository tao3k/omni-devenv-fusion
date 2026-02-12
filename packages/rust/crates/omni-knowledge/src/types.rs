//! Knowledge types - KnowledgeEntry, KnowledgeCategory, and related types.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Knowledge category enumeration.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum KnowledgeCategory {
    #[serde(rename = "patterns")]
    /// Reusable pattern knowledge.
    Pattern,
    #[serde(rename = "solutions")]
    /// Problem-solution knowledge.
    Solution,
    #[serde(rename = "errors")]
    /// Error diagnosis and fixes.
    Error,
    #[serde(rename = "techniques")]
    /// Techniques and methods.
    Technique,
    #[serde(rename = "notes")]
    /// Free-form note content.
    Note,
    #[serde(rename = "references")]
    /// Reference material.
    Reference,
    #[serde(rename = "architecture")]
    /// Architecture design and decisions.
    Architecture,
    #[serde(rename = "workflows")]
    /// Process and workflow guidance.
    Workflow,
}

impl Default for KnowledgeCategory {
    fn default() -> Self {
        KnowledgeCategory::Note
    }
}

/// Knowledge entry struct representing a single knowledge piece.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct KnowledgeEntry {
    /// Unique identifier for the entry
    pub id: String,
    /// Human-readable title
    pub title: String,
    /// Main content/body of the knowledge entry
    pub content: String,
    /// Classification category
    pub category: KnowledgeCategory,
    /// Tags for filtering and search
    pub tags: Vec<String>,
    /// Original source file path or URL
    pub source: Option<String>,
    /// Creation timestamp
    pub created_at: DateTime<Utc>,
    /// Last modification timestamp
    pub updated_at: DateTime<Utc>,
    /// Entry version for change tracking
    pub version: i32,
    /// Additional metadata for extensibility
    pub metadata: HashMap<String, serde_json::Value>,
}

impl KnowledgeEntry {
    /// Create a new KnowledgeEntry with required fields.
    pub fn new(id: String, title: String, content: String, category: KnowledgeCategory) -> Self {
        let now = Utc::now();
        Self {
            id,
            title,
            content,
            category,
            tags: Vec::new(),
            source: None,
            created_at: now,
            updated_at: now,
            version: 1,
            metadata: HashMap::new(),
        }
    }

    /// Set tags for this entry.
    pub fn with_tags(mut self, tags: Vec<String>) -> Self {
        self.tags = tags;
        self
    }

    /// Set source for this entry.
    pub fn with_source(mut self, source: Option<String>) -> Self {
        self.source = source;
        self
    }

    /// Add a tag to this entry.
    pub fn add_tag(&mut self, tag: String) {
        if !self.tags.contains(&tag) {
            self.tags.push(tag);
        }
    }
}

/// Search query for knowledge entries.
#[derive(Debug, Clone, Default)]
pub struct KnowledgeSearchQuery {
    /// Search query text
    pub query: String,
    /// Optional category filter
    pub category: Option<KnowledgeCategory>,
    /// Tags to filter by (entries matching ANY tag)
    pub tags: Vec<String>,
    /// Maximum results to return
    pub limit: i32,
}

impl KnowledgeSearchQuery {
    /// Create a new search query.
    pub fn new(query: String) -> Self {
        Self {
            query,
            category: None,
            tags: Vec::new(),
            limit: 5,
        }
    }

    /// Set category filter.
    pub fn with_category(mut self, category: KnowledgeCategory) -> Self {
        self.category = Some(category);
        self
    }

    /// Set tags filter.
    pub fn with_tags(mut self, tags: Vec<String>) -> Self {
        self.tags = tags;
        self
    }

    /// Set result limit.
    pub fn with_limit(mut self, limit: i32) -> Self {
        self.limit = limit;
        self
    }
}

/// Knowledge base statistics.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct KnowledgeStats {
    /// Total number of entries
    pub total_entries: i64,
    /// Count per category
    pub entries_by_category: HashMap<String, i64>,
    /// Total unique tags
    pub total_tags: i64,
    /// Last update timestamp
    pub last_updated: Option<DateTime<Utc>>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_knowledge_entry_creation() {
        let entry = KnowledgeEntry::new(
            "test-001".to_string(),
            "Test Entry".to_string(),
            "Test content".to_string(),
            KnowledgeCategory::Note,
        );

        assert_eq!(entry.id, "test-001");
        assert_eq!(entry.title, "Test Entry");
        assert_eq!(entry.category, KnowledgeCategory::Note);
        assert_eq!(entry.version, 1);
    }

    #[test]
    fn test_knowledge_entry_with_tags() {
        let entry = KnowledgeEntry::new(
            "test-002".to_string(),
            "Tagged Entry".to_string(),
            "Content".to_string(),
            KnowledgeCategory::Pattern,
        )
        .with_tags(vec!["rust".to_string(), "patterns".to_string()])
        .with_source(Some("docs/test.md".to_string()));

        assert_eq!(entry.tags.len(), 2);
        assert_eq!(entry.source, Some("docs/test.md".to_string()));
    }

    #[test]
    fn test_search_query() {
        let query = KnowledgeSearchQuery::new("error handling".to_string())
            .with_category(KnowledgeCategory::Error)
            .with_tags(vec!["exception".to_string()])
            .with_limit(10);

        assert_eq!(query.query, "error handling");
        assert_eq!(query.limit, 10);
    }
}
