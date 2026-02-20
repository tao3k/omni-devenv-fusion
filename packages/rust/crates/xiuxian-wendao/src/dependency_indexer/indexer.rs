//! Dependency Indexer - Main implementation for indexing external dependencies.
//!
//! Uses `fd` command for fast file finding.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::process::Command;

pub use crate::dependency_indexer::config::DependencyConfig as DependencyBuildConfig;
pub use crate::dependency_indexer::symbols::{ExternalSymbol, SymbolIndex};

/// Dependency indexer configuration (for Python bindings compatibility)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DependencyConfig {
    /// Project root path used for manifest discovery.
    pub project_root: String,
    /// Optional path to dependency index config file.
    pub config_path: Option<String>,
}

impl Default for DependencyConfig {
    fn default() -> Self {
        Self {
            project_root: ".".to_string(),
            config_path: None,
        }
    }
}

/// Result of dependency indexing
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DependencyIndexResult {
    /// Number of manifests processed.
    pub files_processed: usize,
    /// Number of extracted symbols.
    pub total_symbols: usize,
    /// Number of failed manifest/crate processing operations.
    pub errors: usize,
    /// Number of crates successfully indexed.
    pub crates_indexed: usize,
    /// Detailed error messages for failed crate processing
    pub error_details: Vec<String>,
}

/// Statistics about the index
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DependencyStats {
    /// Number of indexed crates.
    pub total_crates: usize,
    /// Number of indexed symbols.
    pub total_symbols: usize,
}

/// Dependency indexer that coordinates parsing, fetching, and symbol extraction.
#[derive(Debug, Clone)]
pub struct DependencyIndexer {
    /// Symbol index for fast lookup
    pub symbol_index: SymbolIndex,
    /// Crate name to version mapping
    crate_versions: HashMap<String, String>,
    /// Project root directory
    project_root: PathBuf,
    /// Config path
    config_path: Option<PathBuf>,
}

impl DependencyIndexer {
    /// Create a new dependency indexer.
    pub fn new(project_root: &str, config_path: Option<&str>) -> Self {
        Self {
            symbol_index: SymbolIndex::new(),
            crate_versions: HashMap::new(),
            project_root: PathBuf::from(project_root),
            config_path: config_path.map(PathBuf::from),
        }
    }

    /// Load the existing index from disk.
    ///
    /// # Errors
    ///
    /// Returns an error when the cached index exists but cannot be read or parsed.
    pub fn load_index(&mut self) -> Result<(), String> {
        let cache_path = self
            .project_root
            .join(".cache/xiuxian-wendao/dependency-symbol-index.txt");
        if !cache_path.exists() {
            return Ok(());
        }
        let data = std::fs::read_to_string(&cache_path)
            .map_err(|e| format!("Failed to read cache file '{}': {e}", cache_path.display()))?;
        if !self.symbol_index.deserialize(&data) {
            return Err(format!(
                "Failed to deserialize symbol index from '{}'",
                cache_path.display()
            ));
        }
        Ok(())
    }

    /// Build the dependency index with parallel crate processing.
    pub fn build(&mut self, verbose: bool) -> DependencyIndexResult {
        use rayon::prelude::*;

        // Load configuration
        let config_path = self.config_path.as_ref().map_or_else(
            || "packages/conf/references.yaml".to_string(),
            |p| p.to_string_lossy().to_string(),
        );

        let config = DependencyBuildConfig::load(&config_path);

        if verbose {
            log::info!(
                "Loaded config with {} dependency configs",
                config.manifests.len()
            );
        }

        // Collect all manifest paths to process
        let mut all_manifests: Vec<(String, PathBuf)> = Vec::new();

        for ext_dep in &config.manifests {
            if ext_dep.pkg_type != "rust" {
                continue;
            }

            for pattern in &ext_dep.manifests {
                let manifest_paths = find_files(pattern, &self.project_root);
                for manifest_path in manifest_paths {
                    // Extract crate name from path for ordering
                    let crate_name = manifest_path
                        .file_stem()
                        .and_then(|n| n.to_str())
                        .unwrap_or("unknown")
                        .to_string();
                    all_manifests.push((crate_name, manifest_path));
                }
            }
        }

        if verbose {
            log::info!("Found {} manifests to process", all_manifests.len());
        }

        // Process all manifests in parallel using rayon
        // Collect results directly without mutex contention
        let results: Vec<(String, String, PathBuf, Vec<ExternalSymbol>, bool, String)> =
            all_manifests
                .into_par_iter()
                .map(|(crate_name, manifest_path)| {
                    let result = Self::process_manifest_inner(&manifest_path);
                    match result {
                        Ok((name, version, path, symbols)) => {
                            (name, version, path, symbols, false, String::new())
                        }
                        Err(e) => (
                            crate_name,
                            String::new(),
                            manifest_path,
                            Vec::new(),
                            true,
                            e,
                        ),
                    }
                })
                .collect();

        let mut result = DependencyIndexResult {
            files_processed: results.len(),
            total_symbols: 0,
            errors: 0,
            crates_indexed: 0,
            error_details: Vec::new(),
        };

        for (crate_name, version, _source_path, symbols, is_error, error_msg) in results {
            if is_error {
                if verbose {
                    log::warn!("Failed to process: {crate_name} - {error_msg}");
                }
                result.errors += 1;
                result
                    .error_details
                    .push(format!("{crate_name}: {error_msg}"));
            } else {
                self.crate_versions.insert(crate_name.clone(), version);
                self.symbol_index.add_symbols(&crate_name, &symbols);
                result.total_symbols += symbols.len();
                result.crates_indexed += 1;
            }
        }

        if verbose {
            log::info!(
                "Build complete: {} files, {} symbols, {} errors",
                result.files_processed,
                result.total_symbols,
                result.errors
            );
        }

        result
    }

    /// Process a single manifest (thread-safe version for parallel processing).
    fn process_manifest_inner(
        manifest_path: &PathBuf,
    ) -> Result<(String, String, PathBuf, Vec<ExternalSymbol>), String> {
        use std::fs;

        let content = fs::read_to_string(manifest_path)
            .map_err(|e| format!("Failed to read manifest: {e}"))?;

        let value: toml::Value = content
            .parse()
            .map_err(|e| format!("Failed to parse TOML: {e}"))?;

        let package_name = value
            .get("package")
            .and_then(|p| p.get("name"))
            .and_then(|n| n.as_str())
            .ok_or("No package name found in manifest")?;

        let version = value
            .get("package")
            .and_then(|p| p.get("version"))
            .and_then(|v| v.as_str())
            .unwrap_or("unknown")
            .to_string();

        let source_path = manifest_path
            .parent()
            .ok_or("No parent directory for manifest")?
            .to_path_buf();

        // Extract symbols from Rust source files
        let symbols = extract_symbols_from_crate(&source_path, package_name);

        Ok((package_name.to_string(), version, source_path, symbols))
    }

    /// Search for symbols by name pattern.
    #[must_use]
    pub fn search(&self, pattern: &str, limit: usize) -> Vec<ExternalSymbol> {
        self.symbol_index.search(pattern, limit)
    }

    /// Search within a specific crate.
    #[must_use]
    pub fn search_crate(
        &self,
        crate_name: &str,
        pattern: &str,
        limit: usize,
    ) -> Vec<ExternalSymbol> {
        self.symbol_index.search_crate(crate_name, pattern, limit)
    }

    /// Get all indexed crate names.
    #[must_use]
    pub fn get_indexed(&self) -> Vec<String> {
        self.crate_versions.keys().cloned().collect()
    }

    /// Get statistics.
    #[must_use]
    pub fn stats(&self) -> DependencyStats {
        DependencyStats {
            total_crates: self.crate_versions.len(),
            total_symbols: self.symbol_index.symbol_count(),
        }
    }
}

/// Find files using fd command.
/// pattern: glob pattern like "**/Cargo.toml" or "*.rs"
fn find_files(pattern: &str, project_root: &std::path::Path) -> Vec<PathBuf> {
    let mut results = Vec::new();

    // Convert glob pattern to fd pattern
    // "**/Cargo.toml" -> "Cargo.toml" with --recursive
    // "packages/**/Cargo.toml" -> "Cargo.toml" in packages/

    let fd_pattern = if pattern.contains("**") {
        pattern
            .split("**")
            .last()
            .unwrap_or(pattern)
            .trim_start_matches('/')
            .to_string()
    } else {
        pattern.to_string()
    };

    let base_dir = if pattern.starts_with('/') {
        PathBuf::from(
            pattern
                .trim_start_matches('/')
                .split("**")
                .next()
                .unwrap_or("."),
        )
    } else {
        project_root.to_path_buf()
    };

    // Build fd command
    let output = Command::new("fd")
        .arg(&fd_pattern)
        .arg(&base_dir)
        .arg("--max-depth")
        .arg("10")
        .arg("-t")
        .arg("f")
        .output();

    match output {
        Ok(o) if o.status.success() => {
            for line in String::from_utf8_lossy(&o.stdout).lines() {
                if !line.trim().is_empty() {
                    results.push(PathBuf::from(line.trim()));
                }
            }
        }
        Ok(_) | Err(_) => {
            // Fallback: direct path check
            let path = base_dir.join(&fd_pattern);
            if path.exists() && path.file_name().is_some_and(|n| n == "Cargo.toml") {
                results.push(path);
            }
        }
    }

    results
}

/// Find Rust source files using fd.
fn find_rs_files(source_path: &std::path::Path) -> Vec<PathBuf> {
    let mut results = Vec::new();

    let output = Command::new("fd")
        .arg("\\.rs$")
        .arg(source_path)
        .arg("--max-depth")
        .arg("10")
        .arg("-t")
        .arg("f")
        .output();

    match output {
        Ok(o) if o.status.success() => {
            for line in String::from_utf8_lossy(&o.stdout).lines() {
                if !line.trim().is_empty() {
                    results.push(PathBuf::from(line.trim()));
                }
            }
        }
        Ok(_) | Err(_) => {
            log::debug!("fd not available or failed for: {}", source_path.display());
        }
    }

    results
}

/// Extract symbols from Rust source files in a crate directory.
fn extract_symbols_from_crate(
    source_path: &std::path::Path,
    crate_name: &str,
) -> Vec<ExternalSymbol> {
    use crate::dependency_indexer::symbols::extract_symbols;

    let mut all_symbols = Vec::new();

    // Use fd to find .rs files
    let rs_files = find_rs_files(source_path);

    for rs_file in &rs_files {
        match extract_symbols(rs_file, "rust") {
            Ok(mut symbols) => {
                for sym in &mut symbols {
                    sym.crate_name = crate_name.to_string();
                }
                all_symbols.extend(symbols);
            }
            Err(e) => {
                log::debug!(
                    "Failed to extract symbols from {}: {}",
                    rs_file.display(),
                    e
                );
            }
        }
    }

    all_symbols
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;

    #[test]
    fn test_indexer_creation() {
        let indexer = DependencyIndexer::new(".", None);
        assert_eq!(indexer.stats().total_crates, 0);
    }

    #[test]
    fn test_config_default() {
        let config = DependencyConfig::default();
        assert_eq!(config.project_root, ".");
    }

    #[test]
    fn test_find_files() {
        let temp_dir = tempfile::tempdir().unwrap();
        let temp_path = temp_dir.path();

        // Create a Cargo.toml
        let cargo_path = temp_dir.path().join("Cargo.toml");
        let mut file = File::create(&cargo_path).unwrap();
        writeln!(file, "[package]\nname = \"test\"").unwrap();

        // Create nested Cargo.toml
        let nested_dir = temp_dir.path().join("crates");
        std::fs::create_dir(&nested_dir).unwrap();
        let nested_cargo = nested_dir.join("Cargo.toml");
        let mut file = File::create(&nested_cargo).unwrap();
        writeln!(file, "[package]\nname = \"nested\"").unwrap();

        let pattern = "**/Cargo.toml";
        let files = find_files(pattern, &PathBuf::from(temp_path));

        // Should find 2 Cargo.toml files
        assert_eq!(files.len(), 2);
    }

    #[test]
    fn test_find_rs_files() {
        let temp_dir = tempfile::tempdir().unwrap();
        let temp_path = temp_dir.path().to_path_buf();

        // Create test Rust files
        let _ = File::create(temp_dir.path().join("lib.rs"));
        let _ = File::create(temp_dir.path().join("main.rs"));
        let _ = File::create(temp_dir.path().join("not_rust.txt"));

        // Create subdirectory
        let sub_dir = temp_dir.path().join("src");
        std::fs::create_dir(&sub_dir).unwrap();
        let _ = File::create(sub_dir.join("module.rs"));

        let files = find_rs_files(&temp_path);

        // Should find 3 .rs files
        assert_eq!(files.len(), 3);
    }

    #[test]
    fn test_build_performance() {
        use std::path::PathBuf;
        use std::time::Instant;

        let project_root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .ancestors()
            .nth(4)
            .unwrap_or_else(|| panic!("failed to resolve workspace root from CARGO_MANIFEST_DIR"))
            .to_path_buf();
        let project_root_str = project_root.to_string_lossy().to_string();
        let config_path = project_root.join("packages/conf/references.yaml");

        let mut indexer = DependencyIndexer::new(
            &project_root_str,
            Some(config_path.to_string_lossy().as_ref()),
        );

        let start = Instant::now();
        let result = indexer.build(false);
        let elapsed = start.elapsed();

        // Performance assertions
        // With parallel processing and pre-compiled regex:
        // - Should process all manifests in under 2 seconds
        // - Should index at least 10 crates
        // - Should extract at least 100 symbols
        assert!(
            elapsed.as_secs() < 2,
            "Build should complete in under 2 seconds, took: {:?}",
            elapsed
        );
        assert!(
            result.crates_indexed >= 10,
            "Should index at least 10 crates, got: {}",
            result.crates_indexed
        );
        assert!(
            result.total_symbols >= 100,
            "Should extract at least 100 symbols, got: {}",
            result.total_symbols
        );

        println!(
            "Build performance: {:.2}s for {} crates, {} symbols",
            elapsed.as_secs_f64(),
            result.crates_indexed,
            result.total_symbols
        );
    }
}
