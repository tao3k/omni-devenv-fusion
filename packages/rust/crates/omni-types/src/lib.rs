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
