//! omni-types - Common type definitions for Omni DevEnv
//!
//! This crate provides shared data structures used across all Omni crates.
//! All types are designed to be serialization-compatible with Python (via PyO3).
//!
//! # Schema Singularity
//! Types derive `schemars::JsonSchema` to enable automatic JSON Schema generation.
//! This establishes Rust as the Single Source of Truth (SSOT) for type definitions,
//! allowing Python and LLM consumers to dynamically retrieve authoritative schemas.

#![allow(clippy::doc_markdown)]

use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Result type with omni-specific error
pub type OmniResult<T> = Result<T, OmniError>;

/// Unified error type for all Omni operations
#[derive(Debug, Error, Serialize, Deserialize)]
#[allow(clippy::enum_variant_names)]
pub enum OmniError {
    /// Git-related operation failures
    #[error("Git error: {0}")]
    Git(String),

    /// File system access failures
    #[error("File system error: {0}")]
    FileSystem(String),

    /// Configuration loading/parsing failures
    #[error("Configuration error: {0}")]
    Config(String),

    /// Unclassified failures
    #[error("Unknown error: {0}")]
    Unknown(String),
}

/// Agent skill definition
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct Skill {
    /// Skill name identifier
    pub name: String,
    /// Human-readable description
    pub description: String,
    /// Skill category
    pub category: String,
}

/// Skill definition with generic metadata container.
/// This enables schema-driven metadata evolution without recompiling Rust.
///
/// All schema-defined fields (version, permissions, require_refs, etc.)
/// are stored in the flexible `metadata` JSON object.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
#[serde(from = "SkillDefinitionHelper", into = "SkillDefinitionHelper")]
pub struct SkillDefinition {
    /// Unique identifier for the skill (e.g., "git", "writer")
    pub name: String,
    /// Semantic description used for vector embedding generation
    pub description: String,
    /// Generic metadata container for schema-defined fields
    pub metadata: serde_json::Value,
    /// Routing keywords for semantic search
    #[serde(default)]
    pub routing_keywords: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct SkillDefinitionHelper {
    name: String,
    description: String,
    metadata: serde_json::Value,
}

impl From<SkillDefinitionHelper> for SkillDefinition {
    fn from(helper: SkillDefinitionHelper) -> Self {
        let metadata = helper.metadata.clone();
        let routing_keywords = metadata
            .get("routing_keywords")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        Self {
            name: helper.name,
            description: helper.description,
            metadata,
            routing_keywords,
        }
    }
}

impl From<SkillDefinition> for SkillDefinitionHelper {
    fn from(def: SkillDefinition) -> Self {
        Self {
            name: def.name,
            description: def.description,
            metadata: def.metadata,
        }
    }
}

impl SkillDefinition {
    /// Create a new skill definition.
    #[must_use]
    pub fn new(name: String, description: String, metadata: serde_json::Value) -> Self {
        let routing_keywords = metadata
            .get("routing_keywords")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();

        Self {
            name,
            description,
            metadata,
            routing_keywords,
        }
    }

    /// Get require_refs from metadata safely.
    #[must_use]
    pub fn get_require_refs(&self) -> Vec<String> {
        self.metadata
            .get("requireRefs")
            .or(self.metadata.get("require_refs"))
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Get a specific metadata field as string.
    /// Tries both camelCase and snake_case variations.
    pub fn get_meta_string(&self, key: &str) -> Option<String> {
        // Try camelCase (first char uppercase) and original key
        let camel_key = key
            .chars()
            .next()
            .map(|c| c.to_uppercase().to_string() + &key[1..])
            .unwrap_or_default();

        self.metadata
            .get(&camel_key)
            .or(self.metadata.get(key))
            .and_then(|v| v.as_str())
            .map(String::from)
    }

    /// Get skill version from metadata.
    #[must_use]
    pub fn get_version(&self) -> String {
        self.get_meta_string("version").unwrap_or_default()
    }
}

/// Task brief from orchestrator
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct TaskBrief {
    /// Task description
    pub task: String,
    /// Mission objectives
    pub mission_brief: String,
    /// Constraints to follow
    pub constraints: Vec<String>,
    /// Files relevant to this task
    pub relevant_files: Vec<String>,
}

/// Agent execution result
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct AgentResult {
    /// Whether the task succeeded
    pub success: bool,
    /// Result content
    pub content: String,
    /// Confidence score (0.0-1.0)
    pub confidence: f64,
    /// Human-readable message
    pub message: String,
}

/// Context for agent execution
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct AgentContext {
    /// System prompt for the agent
    pub system_prompt: String,
    /// Available tools/skills
    pub tools: Vec<Skill>,
    /// Mission brief
    pub mission_brief: String,
    /// Constraints
    pub constraints: Vec<String>,
    /// Relevant files
    pub relevant_files: Vec<String>,
}

/// Vector search result
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct VectorSearchResult {
    /// Result identifier
    pub id: String,
    /// Result content
    pub content: String,
    /// Additional metadata
    pub metadata: serde_json::Value,
    /// Distance from query vector
    pub distance: f64,
}

/// Environment snapshot for the sensory system.
/// This is the Rosetta Stone for Rust-Python communication.
#[derive(Debug, Clone, Serialize, Deserialize, JsonSchema)]
pub struct EnvironmentSnapshot {
    /// Current Git branch name
    pub git_branch: String,
    /// Number of modified (unstaged) files
    pub git_modified: usize,
    /// Number of staged files
    pub git_staged: usize,
    /// Number of lines in active context (SCRATCHPAD.md)
    pub active_context_lines: usize,
    /// List of modified file paths
    pub dirty_files: Vec<String>,
    /// Unix timestamp of snapshot creation
    pub timestamp: f64,
}

impl Default for EnvironmentSnapshot {
    fn default() -> Self {
        Self::new()
    }
}

impl EnvironmentSnapshot {
    /// Create a new empty environment snapshot.
    #[must_use]
    pub fn new() -> Self {
        Self {
            git_branch: "unknown".to_string(),
            git_modified: 0,
            git_staged: 0,
            active_context_lines: 0,
            dirty_files: vec![],
            timestamp: 0.0,
        }
    }

    /// Render as human-readable prompt string for Agent consumption.
    #[must_use]
    pub fn to_prompt_string(&self) -> String {
        let dirty_desc = if self.dirty_files.is_empty() {
            "Clean".to_string()
        } else {
            let count = self.dirty_files.len();
            let preview = self
                .dirty_files
                .iter()
                .take(3)
                .cloned()
                .collect::<Vec<_>>()
                .join(", ");
            if count > 3 {
                format!("{count} files ({preview}, ...)")
            } else {
                format!("{count} files ({preview})")
            }
        };

        format!(
            "[LIVE ENVIRONMENT STATE]\n\
            - Git: Branch: {} | Modified: {} | Staged: {} | Status: {}\n\
            - Active Context: {} lines in SCRATCHPAD.md",
            self.git_branch,
            self.git_modified,
            self.git_staged,
            dirty_desc,
            self.active_context_lines
        )
    }
}

// =============================================================================
// Schema Registry: Dynamic JSON Schema Generation for Python/LLM Consumption
// =============================================================================

/// Schema generation error
#[derive(Debug, thiserror::Error)]
pub enum SchemaError {
    #[error("Unknown type: {0}")]
    UnknownType(String),
}

/// Get JSON Schema for a registered type.
/// This enables Python to dynamically retrieve authoritative schemas from Rust.
///
/// # Errors
/// Returns `SchemaError::UnknownType` if the type name is not registered.
pub fn get_schema_json(type_name: &str) -> Result<String, SchemaError> {
    let schema = match type_name {
        // Core types
        "Skill" => schemars::schema_for!(Skill),
        "SkillDefinition" => schemars::schema_for!(SkillDefinition),
        "TaskBrief" => schemars::schema_for!(TaskBrief),
        "AgentResult" => schemars::schema_for!(AgentResult),
        "AgentContext" => schemars::schema_for!(AgentContext),
        "VectorSearchResult" => schemars::schema_for!(VectorSearchResult),
        "EnvironmentSnapshot" => schemars::schema_for!(EnvironmentSnapshot),
        // Legacy alias
        "OmniTool" => schemars::schema_for!(SkillDefinition),
        _ => return Err(SchemaError::UnknownType(type_name.to_string())),
    };
    serde_json::to_string_pretty(&schema)
        .map_err(|e| SchemaError::UnknownType(format!("Serialization failed: {e}")))
}

/// Get list of all registered type names.
pub fn get_registered_types() -> Vec<&'static str> {
    vec![
        "Skill",
        "SkillDefinition",
        "TaskBrief",
        "AgentResult",
        "AgentContext",
        "VectorSearchResult",
        "EnvironmentSnapshot",
        "OmniTool", // Alias for SkillDefinition
    ]
}
