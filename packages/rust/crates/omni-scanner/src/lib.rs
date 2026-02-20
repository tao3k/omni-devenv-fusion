//! Omni-Scanner - Unified scanning for skills and knowledge.
//!
//! This crate provides unified scanning capabilities:
//! - `skills/` - Scans SKILL.md and @`skill_command` scripts
//! - `knowledge/` - Scans knowledge documents with YAML frontmatter
//!
//! # Architecture
//!
//! ```text
//! omni-scanner/src/
//! ├── lib.rs              # Main module and exports
//! ├── frontmatter.rs      # Shared YAML frontmatter parsing
//! ├── skills/             # Skill scanning modules
//! │   ├── mod.rs
//! │   ├── metadata.rs      # Skill metadata types
//! │   ├── scanner.rs       # SKILL.md parser
//! │   ├── tools.rs         # @skill_command tool parser
//! │   └── skill_command/   # @skill_command parsing utilities
//! └── knowledge/          # Knowledge document scanning
//!     ├── mod.rs
//!     ├── scanner.rs       # Knowledge document scanner
//!     └── types.rs         # KnowledgeEntry, KnowledgeCategory
//! ```
//!
//! # YAML Frontmatter Support
//!
//! Both skills and knowledge use YAML frontmatter for metadata:
//!
//! ```yaml
//! ---
//! # For SKILL.md
//! name: git
//! description: Use when you need to work with git
//! metadata:
//!   routing_keywords: [commit, branch, log]
//!   intents: [version_control, repository_management]
//!
//! # For knowledge documents
//! title: Git Commit Best Practices
//! category: pattern
//! tags: [git, commit, best-practices]
//! ---

// ============================================================================
// Module Declarations
// ============================================================================

pub mod frontmatter;
pub mod knowledge;
pub mod skills;

// ============================================================================
// Re-exports from Skills Module
// ============================================================================

pub use skills::{
    CanonicalSkillPayload, CanonicalToolEntry,
    metadata::{
        AssetRecord, DataRecord, DecoratorArgs, DocsAvailable, IndexToolEntry, ReferencePath,
        ReferenceRecord, ScanConfig, SkillIndexEntry, SkillMetadata, SkillStructure, SnifferRule,
        StructureItem, SyncReport, TemplateRecord, TestRecord, ToolAnnotations, ToolRecord,
        calculate_sync_ops,
    },
    scanner::SkillScanner,
    tools::ToolsScanner,
};

// Re-export extract_frontmatter for external use
pub use frontmatter::extract_frontmatter;

// ============================================================================
// Re-exports from Knowledge Module
// ============================================================================

pub use knowledge::{
    scanner::KnowledgeScanner,
    types::{KnowledgeCategory, KnowledgeEntry, KnowledgeMetadata},
};

// ============================================================================
// JSON Schema Generation
// ============================================================================

/// Generate JSON Schema for `SkillIndexEntry`.
#[must_use]
pub fn skill_index_schema() -> String {
    let schema = schemars::schema_for!(SkillIndexEntry);
    serde_json::to_string_pretty(&schema).unwrap_or_default()
}

/// Generate JSON Schema for `KnowledgeEntry`.
#[must_use]
pub fn knowledge_entry_schema() -> String {
    let schema = schemars::schema_for!(KnowledgeEntry);
    serde_json::to_string_pretty(&schema).unwrap_or_default()
}

// ============================================================================
// Version
// ============================================================================

/// Crate version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
