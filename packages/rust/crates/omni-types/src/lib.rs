//! omni-types - Common type definitions for Omni DevEnv
//!
//! This crate provides shared data structures used across all Omni crates.
//! All types are designed to be serialization-compatible with Python (via PyO3).

#![allow(clippy::doc_markdown)]

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
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Skill {
    /// Skill name identifier
    pub name: String,
    /// Human-readable description
    pub description: String,
    /// Skill category
    pub category: String,
}

/// Task brief from orchestrator
#[derive(Debug, Clone, Serialize, Deserialize)]
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
#[derive(Debug, Clone, Serialize, Deserialize)]
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
#[derive(Debug, Clone, Serialize, Deserialize)]
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
#[derive(Debug, Clone, Serialize, Deserialize)]
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
#[derive(Debug, Clone, Serialize, Deserialize)]
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
            let preview = self.dirty_files.iter().take(3).cloned().collect::<Vec<_>>().join(", ");
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
