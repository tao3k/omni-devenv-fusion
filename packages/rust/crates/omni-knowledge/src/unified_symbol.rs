//! Unified Symbol Index - Combines project symbols with external dependency symbols.
//!
//! This enables:
//! - Unified search across project + external deps
//! - Find where external APIs are used in your project
//! - Trace symbol origins and relationships
//!
//! # Usage
//!
//! ```rust
//! use omni_knowledge::unified_symbol::UnifiedSymbolIndex;
//!
//! let mut index = UnifiedSymbolIndex::new();
//!
//! // Add project symbols
//! index.add_project_symbol("my_func", "fn", "src/lib.rs:42", "mycrate");
//!
//! // Add external dependency symbols
//! index.add_external_symbol("spawn", "fn", "task_join_set.rs:1", "tokio");
//!
//! // Record usage of external symbol in project
//! index.record_external_usage("tokio", "spawn", "src/main.rs:10");
//!
//! // Search across both
//! let results = index.search_unified("spawn", 10);
//!
//! // Find where tokio::spawn is used in project
//! let usage = index.find_external_usage("tokio");
//! ```

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Source type for a symbol
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum SymbolSource {
    /// Symbol from the project itself
    Project,
    /// Symbol from an external dependency
    External(String), // crate name
}

/// A unified symbol that can represent both project and external symbols.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UnifiedSymbol {
    /// Symbol name.
    pub name: String,
    /// Symbol kind (for example `fn`, `struct`, `trait`).
    pub kind: String,
    /// Source location in `file:line` format.
    pub location: String, // file:line
    /// Source domain for this symbol.
    pub source: SymbolSource,
    /// Owning crate or package name.
    pub crate_name: String,
}

impl UnifiedSymbol {
    /// Create a project-local symbol record.
    pub fn new_project(name: &str, kind: &str, location: &str, crate_name: &str) -> Self {
        Self {
            name: name.to_string(),
            kind: kind.to_string(),
            location: location.to_string(),
            source: SymbolSource::Project,
            crate_name: crate_name.to_string(),
        }
    }

    /// Create an external dependency symbol record.
    pub fn new_external(name: &str, kind: &str, location: &str, crate_name: &str) -> Self {
        Self {
            name: name.to_string(),
            kind: kind.to_string(),
            location: location.to_string(),
            source: SymbolSource::External(crate_name.to_string()),
            crate_name: crate_name.to_string(),
        }
    }

    /// Returns true when the symbol comes from an external dependency.
    pub fn is_external(&self) -> bool {
        matches!(self.source, SymbolSource::External(_))
    }

    /// Returns true when the symbol comes from the project itself.
    pub fn is_project(&self) -> bool {
        matches!(self.source, SymbolSource::Project)
    }

    /// Returns crate name for both project and external symbols.
    pub fn crate_or_local(&self) -> &str {
        &self.crate_name
    }
}

/// Unified Symbol Index - combines project and external symbols.
#[derive(Debug, Default, Clone)]
pub struct UnifiedSymbolIndex {
    /// All symbols indexed by lowercase name
    by_name: HashMap<String, Vec<usize>>,
    /// All symbols stored in a vector
    symbols: Vec<UnifiedSymbol>,
    /// External crate usage in project (crate_name -> project locations)
    external_usage: HashMap<String, Vec<String>>,
    /// Project files that use external crates
    project_files: HashMap<String, Vec<String>>, // file -> [symbol names]
}

impl UnifiedSymbolIndex {
    /// Create an empty unified index.
    pub fn new() -> Self {
        Self {
            by_name: HashMap::new(),
            symbols: Vec::new(),
            external_usage: HashMap::new(),
            project_files: HashMap::new(),
        }
    }

    /// Add a project symbol.
    pub fn add_project_symbol(&mut self, name: &str, kind: &str, location: &str, crate_name: &str) {
        let symbol = UnifiedSymbol::new_project(name, kind, location, crate_name);
        self.add_symbol(symbol);
    }

    /// Add an external dependency symbol.
    pub fn add_external_symbol(
        &mut self,
        name: &str,
        kind: &str,
        location: &str,
        crate_name: &str,
    ) {
        let symbol = UnifiedSymbol::new_external(name, kind, location, crate_name);
        self.add_symbol(symbol);
    }

    /// Record usage of an external symbol in a project file.
    pub fn record_external_usage(
        &mut self,
        crate_name: &str,
        symbol_name: &str,
        project_file: &str,
    ) {
        // Record in external_usage: which project locations use this external crate
        self.external_usage
            .entry(crate_name.to_string())
            .or_insert_with(Vec::new)
            .push(project_file.to_string());

        // Record in project_files: which symbols are used in this file
        self.project_files
            .entry(project_file.to_string())
            .or_insert_with(Vec::new)
            .push(symbol_name.to_string());
    }

    fn add_symbol(&mut self, symbol: UnifiedSymbol) {
        let idx = self.symbols.len();
        self.symbols.push(symbol.clone());

        // Index by lowercase name for search
        let key = symbol.name.to_lowercase();
        self.by_name.entry(key).or_insert_with(Vec::new).push(idx);
    }

    /// Search across both project and external symbols.
    pub fn search_unified(&self, pattern: &str, limit: usize) -> Vec<&UnifiedSymbol> {
        let pattern = pattern.to_lowercase();
        let mut results: Vec<&UnifiedSymbol> = self
            .symbols
            .iter()
            .filter(|s| s.name.to_lowercase().contains(&pattern))
            .collect();

        results.truncate(limit);
        results
    }

    /// Search only project symbols.
    pub fn search_project(&self, pattern: &str, limit: usize) -> Vec<&UnifiedSymbol> {
        let pattern = pattern.to_lowercase();
        let results: Vec<&UnifiedSymbol> = self
            .symbols
            .iter()
            .filter(|s| s.name.to_lowercase().contains(&pattern) && s.is_project())
            .take(limit)
            .collect();

        results
    }

    /// Search only external symbols.
    pub fn search_external(&self, pattern: &str, limit: usize) -> Vec<&UnifiedSymbol> {
        let pattern = pattern.to_lowercase();
        let results: Vec<&UnifiedSymbol> = self
            .symbols
            .iter()
            .filter(|s| s.name.to_lowercase().contains(&pattern) && s.is_external())
            .take(limit)
            .collect();

        results
    }

    /// Search within a specific crate (project or external).
    pub fn search_crate(
        &self,
        crate_name: &str,
        pattern: &str,
        limit: usize,
    ) -> Vec<&UnifiedSymbol> {
        let pattern = pattern.to_lowercase();
        let results: Vec<&UnifiedSymbol> = self
            .symbols
            .iter()
            .filter(|s| s.crate_name == crate_name && s.name.to_lowercase().contains(&pattern))
            .take(limit)
            .collect();

        results
    }

    /// Find where an external crate's symbols are used in the project.
    pub fn find_external_usage(&self, crate_name: &str) -> Vec<&str> {
        self.external_usage
            .get(crate_name)
            .map(|v| v.iter().map(|s| s.as_str()).collect())
            .unwrap_or_default()
    }

    /// Find project files that use a specific external symbol.
    pub fn find_symbol_usage(&self, symbol_name: &str, crate_name: &str) -> Vec<&str> {
        self.symbols
            .iter()
            .filter(|s| {
                s.name == symbol_name
                    && matches!(s.source, SymbolSource::External(ref c) if c == crate_name)
            })
            .map(|s| s.location.as_str())
            .collect()
    }

    /// Get all external crates used in the project.
    pub fn get_external_crates(&self) -> Vec<&str> {
        self.external_usage.keys().map(|s| s.as_str()).collect()
    }

    /// Get all project crates.
    pub fn get_project_crates(&self) -> Vec<&str> {
        let mut crates: Vec<&str> = self
            .symbols
            .iter()
            .filter(|s| s.is_project())
            .map(|s| s.crate_name.as_str())
            .collect();

        crates.sort();
        crates.dedup();
        crates
    }

    /// Get statistics.
    pub fn stats(&self) -> UnifiedIndexStats {
        let project_count = self.symbols.iter().filter(|s| s.is_project()).count();
        let external_count = self.symbols.iter().filter(|s| s.is_external()).count();

        UnifiedIndexStats {
            total_symbols: self.symbols.len(),
            project_symbols: project_count,
            external_symbols: external_count,
            external_crates: self.external_usage.len(),
            project_files_with_externals: self.project_files.len(),
        }
    }

    /// Clear all symbols.
    pub fn clear(&mut self) {
        self.by_name.clear();
        self.symbols.clear();
        self.external_usage.clear();
        self.project_files.clear();
    }
}

/// Statistics for unified symbol index.
#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct UnifiedIndexStats {
    /// Total number of indexed symbols.
    pub total_symbols: usize,
    /// Number of project-local symbols.
    pub project_symbols: usize,
    /// Number of external dependency symbols.
    pub external_symbols: usize,
    /// Number of external crates with recorded usage.
    pub external_crates: usize,
    /// Number of project files that reference external symbols.
    pub project_files_with_externals: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_unified_symbol_creation() {
        let proj = UnifiedSymbol::new_project("my_func", "fn", "src/lib.rs:42", "mycrate");
        assert!(proj.is_project());
        assert_eq!(proj.crate_name, "mycrate");

        let ext = UnifiedSymbol::new_external("spawn", "fn", "task_join_set.rs:1", "tokio");
        assert!(ext.is_external());
        assert_eq!(ext.crate_name, "tokio");
    }

    #[test]
    fn test_unified_search() {
        let mut index = UnifiedSymbolIndex::new();

        // Add project symbol
        index.add_project_symbol("my_func", "fn", "src/lib.rs:42", "mycrate");

        // Add external symbols
        index.add_external_symbol("spawn", "fn", "task_join_set.rs:1", "tokio");
        index.add_external_symbol("spawn_local", "mod", "task_join_set.rs:1", "tokio");

        // Search unified
        let results = index.search_unified("spawn", 10);
        assert_eq!(results.len(), 2);

        // Search project only
        let proj_results = index.search_project("spawn", 10);
        assert_eq!(proj_results.len(), 0);

        // Search external only
        let ext_results = index.search_external("spawn", 10);
        assert_eq!(ext_results.len(), 2);
    }

    #[test]
    fn test_external_usage() {
        let mut index = UnifiedSymbolIndex::new();

        // Record usage
        index.record_external_usage("tokio", "spawn", "src/main.rs:10");
        index.record_external_usage("tokio", "spawn", "src/worker.rs:5");

        let usage = index.find_external_usage("tokio");
        assert_eq!(usage.len(), 2);
        assert!(usage.contains(&"src/main.rs:10"));
        assert!(usage.contains(&"src/worker.rs:5"));
    }

    #[test]
    fn test_stats() {
        let mut index = UnifiedSymbolIndex::new();

        index.add_project_symbol("func1", "fn", "src/lib.rs:1", "mycrate");
        index.add_project_symbol("func2", "fn", "src/lib.rs:2", "mycrate");
        index.add_external_symbol("spawn", "fn", "task.rs:1", "tokio");

        // Record usage to populate external_usage
        index.record_external_usage("tokio", "spawn", "src/main.rs:10");

        let stats = index.stats();
        assert_eq!(stats.total_symbols, 3);
        assert_eq!(stats.project_symbols, 2);
        assert_eq!(stats.external_symbols, 1);
        assert_eq!(stats.external_crates, 1); // From external_usage
    }
}
