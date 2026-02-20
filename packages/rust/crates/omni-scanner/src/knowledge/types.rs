//! Knowledge Types
//!
//! Defines types for knowledge documents including categories and entries.
//! Knowledge documents use YAML frontmatter for metadata, similar to SKILL.md.

use schemars::JsonSchema as SchemarsJsonSchema;
use serde::{Deserialize, Serialize};

/// Knowledge categories for organizing documents.
///
/// Categories are used for filtering and routing knowledge queries.
#[derive(
    Debug, Clone, Copy, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq, Default,
)]
#[serde(rename_all = "snake_case")]
pub enum KnowledgeCategory {
    /// Architecture and design patterns
    Architecture,
    /// Debugging guides and solutions
    Debugging,
    /// Error handling patterns
    Error,
    /// General notes and informal documentation
    Note,
    /// Best practices and patterns
    Pattern,
    /// Reference documentation
    Reference,
    /// How-to guides and techniques
    Technique,
    /// Workflow documentation
    Workflow,
    /// Solution-oriented documentation
    Solution,
    /// Uncategorized
    #[serde(other)]
    #[default]
    Unknown,
}

impl std::str::FromStr for KnowledgeCategory {
    type Err = ();

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "architecture" | "arch" => Ok(Self::Architecture),
            "debugging" | "debug" => Ok(Self::Debugging),
            "error" | "err" => Ok(Self::Error),
            "note" | "notes" => Ok(Self::Note),
            "pattern" | "patterns" => Ok(Self::Pattern),
            "reference" | "ref" => Ok(Self::Reference),
            "technique" | "techniques" => Ok(Self::Technique),
            "workflow" | "workflows" => Ok(Self::Workflow),
            "solution" | "solutions" => Ok(Self::Solution),
            _ => Ok(Self::Unknown),
        }
    }
}

impl std::fmt::Display for KnowledgeCategory {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Architecture => write!(f, "architecture"),
            Self::Debugging => write!(f, "debugging"),
            Self::Error => write!(f, "error"),
            Self::Note => write!(f, "note"),
            Self::Pattern => write!(f, "pattern"),
            Self::Reference => write!(f, "reference"),
            Self::Technique => write!(f, "technique"),
            Self::Workflow => write!(f, "workflow"),
            Self::Solution => write!(f, "solution"),
            Self::Unknown => write!(f, "unknown"),
        }
    }
}

/// Metadata extracted from knowledge document frontmatter.
#[derive(Debug, Clone, Default, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub struct KnowledgeMetadata {
    /// Document title (optional, extracted from first H1 if not present)
    #[serde(default)]
    pub title: Option<String>,
    /// Human-readable description of the document
    #[serde(default)]
    pub description: Option<String>,
    /// Category for organization and filtering
    #[serde(default)]
    pub category: Option<KnowledgeCategory>,
    /// Tags for semantic search and discovery
    #[serde(default)]
    pub tags: Vec<String>,
    /// Authors who created or maintain this document
    #[serde(default)]
    pub authors: Vec<String>,
    /// Source file or URL
    #[serde(default)]
    pub source: Option<String>,
    /// Version for tracking document changes
    #[serde(default)]
    pub version: Option<String>,
}

impl KnowledgeMetadata {
    /// Create a new empty `KnowledgeMetadata`.
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    /// Create with a category.
    #[must_use]
    pub fn with_category(mut self, category: KnowledgeCategory) -> Self {
        self.category = Some(category);
        self
    }

    /// Add a tag.
    #[must_use]
    pub fn with_tag(mut self, tag: impl Into<String>) -> Self {
        self.tags.push(tag.into());
        self
    }

    /// Add multiple tags.
    #[must_use]
    pub fn with_tags(mut self, tags: impl IntoIterator<Item = impl Into<String>>) -> Self {
        self.tags
            .extend(tags.into_iter().map(std::convert::Into::into));
        self
    }
}

/// Represents a discovered knowledge document.
///
/// Contains metadata extracted from YAML frontmatter along with
/// file path and content information.
#[derive(Debug, Clone, Serialize, Deserialize, SchemarsJsonSchema, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct KnowledgeEntry {
    /// Unique identifier for this entry
    pub id: String,
    /// Relative path to the document
    pub file_path: String,
    /// Document title
    pub title: String,
    /// Document description
    #[serde(default)]
    pub description: String,
    /// Category for organization
    #[serde(default)]
    pub category: KnowledgeCategory,
    /// Tags for semantic search
    #[serde(default)]
    pub tags: Vec<String>,
    /// Authors
    #[serde(default)]
    pub authors: Vec<String>,
    /// Source URL or file path
    #[serde(default)]
    pub source: Option<String>,
    /// Version identifier
    #[serde(default)]
    pub version: String,
    /// SHA256 hash of file content for change detection
    pub file_hash: String,
    /// Content preview (first N characters)
    #[serde(default)]
    pub content_preview: String,
}

impl KnowledgeEntry {
    /// Create a new `KnowledgeEntry`.
    #[must_use]
    pub fn new(
        id: impl Into<String>,
        file_path: impl Into<String>,
        title: impl Into<String>,
    ) -> Self {
        Self {
            id: id.into(),
            file_path: file_path.into(),
            title: title.into(),
            description: String::new(),
            category: KnowledgeCategory::Unknown,
            tags: Vec::new(),
            authors: Vec::new(),
            source: None,
            version: String::new(),
            file_hash: String::new(),
            content_preview: String::new(),
        }
    }

    /// Get the category as a string.
    #[must_use]
    pub fn category_str(&self) -> &str {
        match self.category {
            KnowledgeCategory::Architecture => "architecture",
            KnowledgeCategory::Debugging => "debugging",
            KnowledgeCategory::Error => "error",
            KnowledgeCategory::Note => "note",
            KnowledgeCategory::Pattern => "pattern",
            KnowledgeCategory::Reference => "reference",
            KnowledgeCategory::Technique => "technique",
            KnowledgeCategory::Workflow => "workflow",
            KnowledgeCategory::Solution => "solution",
            KnowledgeCategory::Unknown => "unknown",
        }
    }
}

impl Default for KnowledgeEntry {
    fn default() -> Self {
        Self::new("", "", "")
    }
}
