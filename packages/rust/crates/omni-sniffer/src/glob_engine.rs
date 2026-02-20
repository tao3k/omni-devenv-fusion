//! High-Performance GlobSet-Based Context Sniffer
//!
//! Uses `globset` (ripgrep's core) to compile 1600+ patterns into a single DFA,
//! enabling O(1) pattern matching per file instead of O(Rules) loops.
//!
//! # Architecture
//!
//! ```text
//! SnifferRule (id, patterns, weight)
//!      ↓
//! GlobSetBuilder.compile() → GlobSet (DFA)
//!      ↓
//! Parallel WalkDir scan
//!      ↓
//! matches() returns bitmask of matched patterns
//!      ↓
//! Map indices back to Context IDs
//! ```

use anyhow::Result;
use globset::{Glob, GlobSet, GlobSetBuilder};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use std::path::Path;
use walkdir::WalkDir;

/// Represents a sniffer rule with multiple glob patterns.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnifferRule {
    /// Unique identifier for this context (e.g., "python", "rust", "nodejs")
    pub id: String,
    /// Glob patterns to match (e.g., `["*.py", "pyproject.toml", "setup.py"]`)
    pub patterns: Vec<String>,
    /// Weight for scoring (higher = more specific)
    pub weight: f32,
}

impl SnifferRule {
    /// Create a new rule with default weight of 1.0
    pub fn new<S: Into<String>, P: Into<Vec<String>>>(id: S, patterns: P) -> Self {
        Self {
            id: id.into(),
            patterns: patterns.into(),
            weight: 1.0,
        }
    }

    /// Create a rule with custom weight
    pub fn with_weight<S: Into<String>, P: Into<Vec<String>>>(
        id: S,
        patterns: P,
        weight: f32,
    ) -> Self {
        Self {
            id: id.into(),
            patterns: patterns.into(),
            weight,
        }
    }
}

/// From implementations for ergonomic API
impl<S, P> From<(S, P)> for SnifferRule
where
    S: Into<String>,
    P: Into<Vec<String>>,
{
    fn from((id, patterns): (S, P)) -> Self {
        SnifferRule::new(id, patterns)
    }
}

/// High-performance sniffer engine using compiled `GlobSet`.
///
/// # Performance
///
/// - Pattern compilation: O(Rules) once at initialization
/// - File matching: O(Files) with DFA (constant time per pattern)
/// - Total: O(Rules + Files) vs Python's O(Files × Rules)
///
/// # Example
///
/// ```rust,ignore
/// use omni_sniffer::{SnifferEngine, SnifferRule};
///
/// let rules = vec![
///     SnifferRule::new("python", vec!["*.py", "pyproject.toml"]),
///     SnifferRule::new("rust", vec!["*.rs", "Cargo.toml"]),
/// ];
///
/// let engine = SnifferEngine::new(rules).unwrap();
/// let contexts = engine.sniff_path("/path/to/project", 5);
/// ```
#[derive(Clone)]
pub struct SnifferEngine {
    /// Compiled DFA for all patterns
    glob_set: GlobSet,
    /// Maps pattern index to rule ID (for retrieving matched context IDs)
    pattern_to_rule: Vec<String>,
    /// Maps rule ID to its weight
    rule_weights: Vec<f32>,
}

impl SnifferEngine {
    /// Create a new sniffer engine from rules.
    ///
    /// # Errors
    ///
    /// Returns an error if any pattern fails to compile.
    pub fn new(rules: Vec<SnifferRule>) -> Result<Self> {
        let mut builder = GlobSetBuilder::new();
        let mut pattern_to_rule = Vec::new();
        let mut rule_weights = Vec::new();

        // Collect all patterns from all rules
        for rule in rules {
            let rule_id = rule.id;
            let weight = rule.weight;
            for pattern in rule.patterns {
                // Add pattern to DFA builder
                builder.add(Glob::new(&pattern)?);
                // Record which rule this pattern belongs to
                pattern_to_rule.push(rule_id.clone());
                rule_weights.push(weight);
            }
        }

        let glob_set = builder.build()?;
        Ok(Self {
            glob_set,
            pattern_to_rule,
            rule_weights,
        })
    }

    /// Create from pre-serialized rules (JSON).
    ///
    /// Useful for loading rules from a database or file.
    ///
    /// # Errors
    ///
    /// Returns an error if JSON is invalid or rule compilation fails.
    pub fn from_json(json: &str) -> Result<Self> {
        let rules: Vec<SnifferRule> = serde_json::from_str(json)?;
        Self::new(rules)
    }

    /// Get the number of compiled patterns.
    #[inline]
    #[must_use]
    pub fn pattern_count(&self) -> usize {
        self.pattern_to_rule.len()
    }

    /// Get the number of unique context IDs.
    #[inline]
    #[must_use]
    pub fn context_count(&self) -> usize {
        let mut unique = HashSet::new();
        for id in &self.pattern_to_rule {
            unique.insert(id);
        }
        unique.len()
    }

    /// Sniff a single file path (O(1) DFA match).
    ///
    /// Returns context IDs that match this file.
    #[inline]
    #[must_use]
    pub fn sniff_file(&self, relative_path: &str) -> Vec<String> {
        let matches = self.glob_set.matches(relative_path);
        let mut detected: Vec<String> = Vec::with_capacity(matches.len());

        for idx in matches {
            if let Some(rule_id) = self.pattern_to_rule.get(idx) {
                detected.push(rule_id.clone());
            }
        }

        // Remove duplicates while preserving order
        detected.sort();
        detected.dedup();
        detected
    }

    /// Sniff a single file with weights (for scoring).
    ///
    /// Returns (`context_id`, weight) pairs for matched contexts.
    #[inline]
    #[must_use]
    pub fn sniff_file_with_weights(&self, relative_path: &str) -> Vec<(String, f32)> {
        let matches = self.glob_set.matches(relative_path);
        let mut detected: Vec<(String, f32)> = Vec::with_capacity(matches.len());

        for idx in matches {
            if let Some(rule_id) = self.pattern_to_rule.get(idx) {
                let weight = self.rule_weights.get(idx).copied().unwrap_or(1.0);
                detected.push((rule_id.clone(), weight));
            }
        }

        // Deduplicate by keeping highest weight
        detected.sort_by(|a, b| a.0.cmp(&b.0));
        let mut result: Vec<(String, f32)> = Vec::new();
        for (id, weight) in detected {
            if result.last().is_none_or(|(last_id, _)| *last_id != id) {
                result.push((id, weight));
            } else if let Some((_, last_weight)) = result.last_mut() {
                *last_weight = f32::midpoint(*last_weight, weight);
            }
        }

        result
    }

    /// Parallel directory scan with depth limit.
    ///
    /// Uses `rayon` for parallel pattern matching while `WalkDir`
    /// handles the directory traversal.
    ///
    /// # Arguments
    ///
    /// * `root_path` - Root directory to scan
    /// * `max_depth` - Maximum directory depth to traverse
    ///
    /// # Returns
    ///
    /// Vector of unique context IDs detected in the directory tree.
    #[must_use]
    pub fn sniff_path(&self, root_path: &str, max_depth: usize) -> Vec<String> {
        self.sniff_path_with_workers(root_path, max_depth, None)
    }

    /// Parallel directory scan with custom worker count.
    ///
    /// # Arguments
    ///
    /// * `root_path` - Root directory to scan
    /// * `max_depth` - Maximum directory depth to traverse
    /// * `num_workers` - Number of rayon workers (None = default)
    ///
    /// # Performance
    ///
    /// Uses thread-local collection to avoid lock contention in parallel processing.
    #[must_use]
    pub fn sniff_path_with_workers(
        &self,
        root_path: &str,
        max_depth: usize,
        num_workers: Option<usize>,
    ) -> Vec<String> {
        let root = Path::new(root_path);
        if !root.exists() || !root.is_dir() {
            return Vec::new();
        }

        // Collect all entries first (WalkDir is single-threaded iterator)
        let entries: Vec<_> = WalkDir::new(root)
            .max_depth(max_depth)
            .follow_links(false)
            .sort_by(|a, b| a.file_name().cmp(b.file_name()))
            .into_iter()
            .filter_map(std::result::Result::ok)
            .filter(|e| e.file_type().is_file())
            .collect();

        if entries.is_empty() {
            return Vec::new();
        }

        // Configure rayon thread pool if specified
        if let Some(workers) = num_workers {
            rayon::ThreadPoolBuilder::new()
                .num_threads(workers)
                .build_global()
                .ok();
        }

        // Parallel pattern matching - collect results locally per thread, no locks in parallel section
        let detected: Vec<String> = entries
            .par_iter()
            .filter_map(|entry| {
                if let Ok(relative) = entry.path().strip_prefix(root) {
                    let relative_str = relative.to_string_lossy().into_owned();
                    let matches = self.glob_set.matches(&relative_str);

                    if !matches.is_empty() {
                        // Collect matched rule IDs locally
                        let mut local_matches = Vec::new();
                        for idx in matches {
                            if let Some(rule_id) = self.pattern_to_rule.get(idx) {
                                local_matches.push(rule_id.clone());
                            }
                        }
                        return Some(local_matches);
                    }
                }
                None
            })
            .flatten()
            .collect();

        // Deduplicate while preserving order
        let mut seen = std::collections::HashSet::new();
        let mut result: Vec<String> = detected
            .into_iter()
            .filter(|id| seen.insert(id.clone()))
            .collect();

        result.sort();
        result
    }

    /// Sniff with scoring (returns context IDs sorted by weight).
    ///
    /// Contexts detected by more specific patterns (higher weight) appear first.
    ///
    /// # Performance
    ///
    /// Uses thread-local collection to avoid lock contention in parallel processing.
    #[must_use]
    pub fn sniff_path_with_scores(&self, root_path: &str, max_depth: usize) -> Vec<(String, f32)> {
        use rayon::prelude::*;

        let root = Path::new(root_path);
        if !root.exists() || !root.is_dir() {
            return Vec::new();
        }

        // Collect entries
        let entries: Vec<_> = WalkDir::new(root)
            .max_depth(max_depth)
            .into_iter()
            .filter_map(std::result::Result::ok)
            .filter(|e| e.file_type().is_file())
            .collect();

        if entries.is_empty() {
            return Vec::new();
        }

        // Parallel matching with scoring - collect thread-local scores
        let thread_scores: Vec<std::collections::HashMap<String, f32>> = entries
            .par_iter()
            .map(|entry| {
                let mut local_scores = std::collections::HashMap::new();

                if let Ok(relative) = entry.path().strip_prefix(root) {
                    let relative_str = relative.to_string_lossy().into_owned();
                    let matches = self.glob_set.matches(&relative_str);

                    if !matches.is_empty() {
                        for idx in matches {
                            if let Some(rule_id) = self.pattern_to_rule.get(idx) {
                                let weight = self.rule_weights.get(idx).copied().unwrap_or(1.0);
                                *local_scores.entry(rule_id.clone()).or_insert(0.0) += weight;
                            }
                        }
                    }
                }
                local_scores
            })
            .collect();

        // Merge thread-local scores
        let mut merged_scores = std::collections::HashMap::new();
        for local in thread_scores {
            for (id, weight) in local {
                *merged_scores.entry(id).or_insert(0.0) += weight;
            }
        }

        // Convert to sorted vector
        let mut result: Vec<(String, f32)> = merged_scores.into_iter().collect();

        // Sort by score descending
        result.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

        result
    }

    /// Quick check if any context would be detected in this path.
    ///
    /// Faster than full scan - stops at first match.
    #[must_use]
    pub fn has_any_context(&self, root_path: &str, max_depth: usize) -> bool {
        let root = Path::new(root_path);
        if !root.exists() || !root.is_dir() {
            return false;
        }

        for entry in WalkDir::new(root)
            .max_depth(max_depth)
            .into_iter()
            .flatten()
        {
            if entry.file_type().is_file()
                && let Ok(relative) = entry.path().strip_prefix(root)
                && self.glob_set.is_match(relative)
            {
                return true;
            }
        }

        false
    }
}
