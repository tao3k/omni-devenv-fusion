//! Skill Tool Indexing - Discover and index @skill_command decorated functions
//!
//! This module provides methods for scanning skill directories and indexing
//! tool functions discovered via `skills-scanner` crate.
//!
//! Uses both `SkillScanner` (for SKILL.md) and `ToolsScanner` (for scripts/)
//! to properly enrich tool records with routing_keywords from SKILL.md.
#![allow(clippy::doc_markdown)]

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
    /// Vector-side contribution score before fusion.
    pub vector_score: Option<f32>,
    /// Keyword-side contribution score before fusion.
    pub keyword_score: Option<f32>,
    /// Parent skill name (e.g., "git")
    pub skill_name: String,
    /// Tool function name (e.g., "commit")
    pub tool_name: String,
    /// Source file path
    pub file_path: String,
    /// Routing keywords for hybrid search (schema: routing_keywords)
    pub routing_keywords: Vec<String>,
    /// Associated intents for semantic alignment
    pub intents: Vec<String>,
    /// Tool category from decorator metadata (or inferred fallback).
    pub category: String,
    /// Parameter names from index (for param-type boost when input_schema is empty).
    pub parameters: Vec<String>,
}

/// Optional runtime controls for `search_tools` ranking pipeline.
#[derive(Debug, Clone, Copy)]
pub struct ToolSearchOptions {
    /// Whether to apply metadata-aware rerank bonus after fusion.
    ///
    /// Keeping this explicit allows Python callers to run deterministic
    /// fusion-only mode while preserving backwards compatibility.
    pub rerank: bool,

    /// Override semantic (vector) weight for weighted-RRF fusion.
    /// When `None`, falls back to the global `SEMANTIC_WEIGHT` constant.
    pub semantic_weight: Option<f32>,

    /// Override keyword (BM25) weight for weighted-RRF fusion.
    /// When `None`, falls back to the global `KEYWORD_WEIGHT` constant.
    pub keyword_weight: Option<f32>,
}

impl Default for ToolSearchOptions {
    fn default() -> Self {
        Self {
            rerank: true,
            semantic_weight: None,
            keyword_weight: None,
        }
    }
}

fn is_hex(c: char) -> bool {
    c.is_ascii_hexdigit()
}

fn is_uuid_like(value: &str) -> bool {
    if value.len() != 36 {
        return false;
    }
    let bytes = value.as_bytes();
    if bytes[8] != b'-' || bytes[13] != b'-' || bytes[18] != b'-' || bytes[23] != b'-' {
        return false;
    }
    value
        .chars()
        .enumerate()
        .all(|(idx, ch)| matches!(idx, 8 | 13 | 18 | 23) || is_hex(ch))
}

/// Validate a tool identifier for router usage.
///
/// We intentionally reject UUID-like names and whitespace-only identifiers to prevent
/// non-command documents from polluting routing results.
#[must_use]
pub fn is_routable_tool_name(value: &str) -> bool {
    let name = value.trim();
    if name.is_empty() || name.len() > 160 {
        return false;
    }
    if is_uuid_like(name) {
        return false;
    }
    if name.chars().any(char::is_whitespace) {
        return false;
    }
    if !name.chars().any(|c| c.is_ascii_alphabetic()) {
        return false;
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
    {
        return false;
    }
    if name
        .split('.')
        .any(|segment| !segment.is_empty() && is_uuid_like(segment))
    {
        return false;
    }
    true
}

/// Normalize input_schema to canonical JSON object.
///
/// Accepts:
/// - object (returned as-is)
/// - JSON string representing object (parsed)
/// - doubly-encoded JSON string object (parsed twice)
///
/// Falls back to `{}` for invalid/non-object payloads.
#[must_use]
pub fn normalize_input_schema_value(value: &Value) -> Value {
    fn parse_object_from_str(raw: &str) -> Option<Value> {
        let first: Value = serde_json::from_str(raw).ok()?;
        match first {
            Value::Object(_) => Some(first),
            Value::String(inner) => {
                let second: Value = serde_json::from_str(&inner).ok()?;
                if matches!(second, Value::Object(_)) {
                    Some(second)
                } else {
                    None
                }
            }
            _ => None,
        }
    }

    match value {
        Value::Object(_) => value.clone(),
        Value::String(raw) => parse_object_from_str(raw).unwrap_or_else(|| serde_json::json!({})),
        _ => serde_json::json!({}),
    }
}

fn extract_string_array_field(meta: &Value, key: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut seen = std::collections::HashSet::new();
    if let Some(values) = meta.get(key).and_then(|v| v.as_array()) {
        for value in values {
            if let Some(raw) = value.as_str() {
                let token = raw.trim();
                if token.is_empty() {
                    continue;
                }
                if seen.insert(token.to_string()) {
                    out.push(token.to_string());
                }
            }
        }
    }
    out
}

/// Resolve routing keywords from metadata (strict single-field contract).
#[must_use]
pub fn resolve_routing_keywords(meta: &Value) -> Vec<String> {
    extract_string_array_field(meta, "routing_keywords")
}

/// Resolve intents from metadata with basic normalization.
#[must_use]
pub fn resolve_intents(meta: &Value) -> Vec<String> {
    extract_string_array_field(meta, "intents")
}
