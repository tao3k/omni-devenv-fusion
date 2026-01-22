//! Type definitions for symbols and search results.
//!
//! Core data structures for the tag extraction system.

use serde::Serialize;
use std::collections::HashMap;

/// Symbol kind enumeration
#[derive(Debug, Clone, Serialize, PartialEq)]
pub enum SymbolKind {
    /// Function definition
    Function,
    /// Class definition
    Class,
    /// Struct definition
    Struct,
    /// Method within a class
    Method,
    /// Trait definition
    Trait,
    /// Impl block
    Impl,
    /// Module or namespace
    Module,
    /// Async function definition
    AsyncFunction,
    /// Enum definition
    Enum,
    /// Interface or type alias
    Interface,
    /// Unknown or unrecognized symbol
    Unknown,
}

impl From<&str> for SymbolKind {
    fn from(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "fn" | "def" | "function" | "method" => SymbolKind::Function,
            "class" => SymbolKind::Class,
            "struct" => SymbolKind::Struct,
            "impl" => SymbolKind::Impl,
            "trait" => SymbolKind::Trait,
            "mod" | "module" => SymbolKind::Module,
            "enum" => SymbolKind::Enum,
            "interface" => SymbolKind::Interface,
            _ => SymbolKind::Unknown,
        }
    }
}

/// A symbol extracted from source code
#[derive(Debug, Clone, Serialize)]
pub struct Symbol {
    /// Name of the symbol
    pub name: String,
    /// Kind of symbol (function, class, etc.)
    pub kind: SymbolKind,
    /// Line number where the symbol is defined
    pub line: usize,
    /// Signature or declaration string
    pub signature: String,
}

// ============================================================================
// Search Results (The Hunter)
// ============================================================================

/// A single search match result
#[derive(Debug, Clone, Serialize)]
pub struct SearchMatch {
    /// Path to the file
    pub path: String,
    /// Line number (1-indexed)
    pub line: usize,
    /// Column number (1-indexed)
    pub column: usize,
    /// Matched content/snippet
    pub content: String,
    /// Captured variables (if any)
    pub captures: HashMap<String, String>,
}

/// Result of a code search
#[derive(Debug, Clone, Serialize)]
pub struct SearchResult {
    /// Total number of matches
    pub count: usize,
    /// Individual matches
    pub matches: Vec<SearchMatch>,
}

/// Directory walker configuration
pub struct SearchConfig {
    /// File patterns to include (e.g., "**/*.py")
    pub file_pattern: String,
    /// Maximum file size in bytes (default 1MB)
    pub max_file_size: u64,
    /// Maximum number of matches per file
    pub max_matches_per_file: usize,
    /// Languages to search (empty means auto-detect)
    pub languages: Vec<String>,
}

impl Default for SearchConfig {
    fn default() -> Self {
        Self {
            file_pattern: "**/*".to_string(),
            max_file_size: 1024 * 1024, // 1MB
            max_matches_per_file: 100,
            languages: Vec::new(),
        }
    }
}
