//! Batch Refactoring Engine - Heavy-Duty Parallel Processing
//!
//! The Ouroboros - Self-Eating Snake
//!
//! Provides parallel batch refactoring across entire codebases using rayon
//! and ignore for maximum performance. Python sends one command, Rust
//! processes thousands of files concurrently.

use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};

use dashmap::DashMap;
use omni_ast::AstLanguage;
use rayon::prelude::*;

use crate::StructuralEditor;

/// Statistics for batch refactoring operations.
#[derive(Debug, Default)]
pub struct BatchRefactorStats {
    /// Number of files scanned
    pub files_scanned: usize,
    /// Number of files with changes
    pub files_changed: usize,
    /// Total number of replacements made
    pub replacements: usize,
    /// Errors encountered (path -> error message)
    pub errors: HashMap<String, String>,
    /// List of modified files
    pub modified_files: Vec<String>,
}

impl BatchRefactorStats {
    /// Create a new empty stats instance.
    #[must_use]
    pub fn new() -> Self {
        Self {
            files_scanned: 0,
            files_changed: 0,
            replacements: 0,
            errors: HashMap::new(),
            modified_files: Vec::new(),
        }
    }
}

/// Configuration for batch refactoring.
#[derive(Debug, Clone)]
pub struct BatchConfig {
    /// File glob pattern (e.g., "**/*.py")
    pub file_pattern: String,
    /// Whether to actually modify files (false) or just preview (true)
    pub dry_run: bool,
    /// Maximum file size in bytes (default 1MB)
    pub max_file_size: u64,
    /// Number of parallel workers (0 = auto-detect)
    pub workers: usize,
    /// Languages to process (empty = all detected)
    pub languages: Vec<String>,
    /// Skip directories matching these patterns
    pub skip_dirs: Vec<String>,
}

impl Default for BatchConfig {
    fn default() -> Self {
        Self {
            file_pattern: "**/*".to_string(),
            dry_run: true,
            max_file_size: 1_048_576,
            workers: 0,
            languages: Vec::new(),
            skip_dirs: vec![".git".to_string(), "node_modules".to_string()],
        }
    }
}

/// Detect programming language from file path.
fn detect_language(path: &Path) -> String {
    use omni_ast::SupportLang;

    if let Some(lang) = SupportLang::from_path(path) {
        return format!("{:?}", lang).to_lowercase();
    }
    "python".to_string()
}

impl StructuralEditor {
    /// Perform batch structural replace across a directory.
    ///
    /// This is the "heavy equipment" function that takes a directory and
    /// applies structural refactoring across all matching files in parallel.
    pub fn batch_replace(
        root: &Path,
        search_pattern: &str,
        rewrite_pattern: &str,
        config: &BatchConfig,
    ) -> BatchRefactorStats {
        let files_scanned = AtomicUsize::new(0);
        let files_changed = AtomicUsize::new(0);
        let total_replacements = AtomicUsize::new(0);
        let modified_files = DashMap::new();
        let errors: DashMap<String, String> = DashMap::new();

        // Determine thread count
        let num_workers = if config.workers > 0 {
            config.workers
        } else {
            rayon::current_num_threads()
        };

        // Collect files first (simple approach)
        let files: Vec<_> = ignore::WalkBuilder::new(root)
            .threads(num_workers)
            .build()
            .filter_map(|result| {
                let entry = match result {
                    Ok(e) => e,
                    Err(_) => return None,
                };
                let path = entry.path();
                if !path.is_file() {
                    return None;
                }
                // Check skip directories
                for skip_dir in &config.skip_dirs {
                    if let Some(parent) = path.parent() {
                        for component in parent.components() {
                            if let std::path::Component::Normal(os_str) = component {
                                if os_str.to_string_lossy() == *skip_dir {
                                    return None;
                                }
                            }
                        }
                    }
                }
                // Check glob pattern
                if !matches_glob(path, &config.file_pattern) {
                    return None;
                }
                Some(path.to_path_buf())
            })
            .collect();

        // Process files in parallel
        files.into_par_iter().for_each(|path| {
            files_scanned.fetch_add(1, Ordering::Relaxed);

            let content = match std::fs::read_to_string(&path) {
                Ok(c) => c,
                Err(e) => {
                    errors.insert(path.display().to_string(), format!("Read error: {}", e));
                    return;
                }
            };

            let lang = detect_language(&path);

            match StructuralEditor::replace(&content, search_pattern, rewrite_pattern, &lang) {
                Ok(result) => {
                    if result.count > 0 {
                        files_changed.fetch_add(1, Ordering::Relaxed);
                        total_replacements.fetch_add(result.count, Ordering::Relaxed);
                        modified_files.insert(path.display().to_string(), result.count);

                        if !config.dry_run {
                            if let Err(e) = std::fs::write(&path, &result.modified) {
                                errors.insert(
                                    path.display().to_string(),
                                    format!("Write error: {}", e),
                                );
                            }
                        }
                    }
                }
                Err(e) => {
                    errors.insert(path.display().to_string(), format!("Edit error: {}", e));
                }
            }
        });

        let mut stats = BatchRefactorStats::new();
        stats.files_scanned = files_scanned.load(Ordering::Relaxed);
        stats.files_changed = files_changed.load(Ordering::Relaxed);
        stats.replacements = total_replacements.load(Ordering::Relaxed);
        stats.modified_files = modified_files.into_iter().map(|(k, _)| k).collect();
        stats.errors = errors.into_iter().collect();

        stats
    }
}

/// Check if a path matches a glob pattern (simplified implementation).
fn matches_glob(path: &Path, pattern: &str) -> bool {
    let path_str = path.to_string_lossy();
    let file_name = path
        .file_name()
        .map(|n| n.to_string_lossy())
        .unwrap_or_default();

    if pattern.starts_with("**/*") {
        let suffix = pattern.trim_start_matches("**/*");
        if suffix.is_empty() {
            return true;
        }
        path_str.ends_with(suffix) || path_str.contains(suffix)
    } else if pattern.starts_with('*') {
        file_name.ends_with(&pattern[1..])
    } else if pattern.contains('*') {
        let parts: Vec<&str> = pattern.split('*').collect();
        if parts.len() == 1 {
            return file_name == pattern;
        }
        let mut current = 0;
        for part in &parts {
            if let Some(pos) = file_name[current..].find(part) {
                current += pos + part.len();
            } else {
                return false;
            }
        }
        true
    } else {
        file_name == pattern
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use std::io::Write;
    use tempfile::TempDir;

    #[test]
    fn test_batch_replace_python() {
        let dir = TempDir::new().expect("Create temp dir");

        let file1 = dir.path().join("test1.py");
        File::create(&file1)
            .expect("Create file")
            .write_all(b"print('hello')\nprint('world')\n")
            .expect("Write content");

        let file2 = dir.path().join("test2.py");
        File::create(&file2)
            .expect("Create file")
            .write_all(b"print('foo')\n")
            .expect("Write content");

        let config = BatchConfig {
            file_pattern: "**/*.py".to_string(),
            dry_run: true,
            ..Default::default()
        };

        let stats = StructuralEditor::batch_replace(
            dir.path(),
            "print($ARGS)",
            "logger.info($ARGS)",
            &config,
        );

        assert_eq!(stats.files_scanned, 2);
        assert_eq!(stats.files_changed, 2);
        assert_eq!(stats.replacements, 3);
    }

    #[test]
    fn test_batch_replace_apply() {
        let dir = TempDir::new().expect("Create temp dir");

        let file = dir.path().join("test.py");
        File::create(&file)
            .expect("Create file")
            .write_all(b"print('hello')\n")
            .expect("Write content");

        let config = BatchConfig {
            file_pattern: "**/*.py".to_string(),
            dry_run: false,
            ..Default::default()
        };

        let stats = StructuralEditor::batch_replace(
            dir.path(),
            "print($ARGS)",
            "logger.info($ARGS)",
            &config,
        );

        assert_eq!(stats.files_changed, 1);

        let content = std::fs::read_to_string(&file).expect("Read file");
        assert!(content.contains("logger.info"));
    }

    #[test]
    fn test_matches_glob() {
        assert!(matches_glob(Path::new("test.py"), "*.py"));
        assert!(matches_glob(Path::new("test.py"), "**/*.py"));
        assert!(!matches_glob(Path::new("test.rs"), "*.py"));
    }
}
