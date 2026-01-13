//! omni-types - Common type definitions for Omni DevEnv
//!
//! This crate provides shared data structures used across all Omni crates.
//! All types are designed to be serialization-compatible with Python (via PyO3).

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Result type with omni-specific error
pub type OmniResult<T> = Result<T, OmniError>;

/// Unified error type for all Omni operations
#[derive(Debug, Error, Serialize, Deserialize)]
pub enum OmniError {
    #[error("Git error: {0}")]
    Git(String),

    #[error("File system error: {0}")]
    FileSystem(String),

    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Unknown error: {0}")]
    Unknown(String),
}

/// Agent skill definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Skill {
    pub name: String,
    pub description: String,
    pub category: String,
}

/// Task brief from orchestrator
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskBrief {
    pub task: String,
    pub mission_brief: String,
    pub constraints: Vec<String>,
    pub relevant_files: Vec<String>,
}

/// Agent execution result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentResult {
    pub success: bool,
    pub content: String,
    pub confidence: f64,
    pub message: String,
}

/// Context for agent execution
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentContext {
    pub system_prompt: String,
    pub tools: Vec<Skill>,
    pub mission_brief: String,
    pub constraints: Vec<String>,
    pub relevant_files: Vec<String>,
}

/// Vector search result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VectorSearchResult {
    pub id: String,
    pub content: String,
    pub metadata: serde_json::Value,
    pub distance: f64,
}
