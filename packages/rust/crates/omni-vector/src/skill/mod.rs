//! Skill Tool Indexing - Discover and index @skill_command decorated functions
//!
//! This module provides methods for scanning skill directories and indexing
//! tool functions discovered via `skills-scanner` crate.
//!
//! Uses both `SkillScanner` (for SKILL.md) and `ToolsScanner` (for scripts/)
//! to properly enrich tool records with routing_keywords from SKILL.md.

use serde::Serialize;
use serde_json::Value;

pub mod scanner;

pub use scanner::SkillScannerModule;

/// Tool Search Result - Ready-to-use struct returned to Python
/// Optimized for zero-copy passing through FFI boundary
#[derive(Debug, Clone, Serialize)]
pub struct ToolSearchResult {
    /// Full tool name (e.g., "git.commit")
    pub name: String,
    /// Tool description from content
    pub description: String,
    /// JSON schema for tool inputs
    pub input_schema: Value,
    /// Relevance score (0.0 to 1.0)
    pub score: f32,
    /// Parent skill name (e.g., "git")
    pub skill_name: String,
    /// Tool function name (e.g., "commit")
    pub tool_name: String,
    /// Source file path
    pub file_path: String,
    /// Routing keywords for hybrid search
    pub keywords: Vec<String>,
}
