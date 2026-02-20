//! Sync Engine - Incremental Knowledge Synchronization
//!
//! Provides efficient file discovery, manifest management, and diff computation
//! for incremental knowledge base updates.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use xxhash_rust::xxh3;

/// Manifest entry: file path -> content hash
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
pub struct SyncManifest(pub HashMap<String, String>);

/// File change type
#[derive(Debug, Clone, PartialEq)]
pub enum FileChange {
    /// A new file was added.
    Added(PathBuf),
    /// An existing file was modified.
    Modified(PathBuf),
    /// A tracked file was deleted.
    Deleted(PathBuf),
}

/// Sync result
#[derive(Debug, Clone, Default)]
pub struct SyncResult {
    /// Newly added files.
    pub added: Vec<PathBuf>,
    /// Modified files.
    pub modified: Vec<PathBuf>,
    /// Deleted files.
    pub deleted: Vec<PathBuf>,
    /// Number of unchanged files.
    pub unchanged: usize,
}

/// File discovery options
#[derive(Debug, Clone)]
pub struct DiscoveryOptions {
    /// Optional maximum number of files to scan.
    pub max_files: Option<usize>,
    /// Whether to skip hidden files and folders.
    pub skip_hidden: bool,
    /// Directory names to skip during discovery.
    pub skip_dirs: Vec<String>,
    /// Maximum file size in bytes.
    pub max_file_size: u64,
    /// Allowed file extensions.
    pub extensions: Vec<String>,
}

impl Default for DiscoveryOptions {
    fn default() -> Self {
        Self {
            max_files: None,
            skip_hidden: true,
            skip_dirs: vec![
                ".git".to_string(),
                ".venv".to_string(),
                "venv".to_string(),
                "__pycache__".to_string(),
                "node_modules".to_string(),
                "target".to_string(),
                ".cache".to_string(),
            ],
            max_file_size: 1024 * 1024, // 1MB
            extensions: vec![
                "py".to_string(),
                "rs".to_string(),
                "md".to_string(),
                "yaml".to_string(),
                "yml".to_string(),
                "json".to_string(),
                "toml".to_string(),
            ],
        }
    }
}

/// Sync engine for incremental knowledge sync
#[derive(Debug, Clone)]
pub struct SyncEngine {
    project_root: PathBuf,
    manifest_path: PathBuf,
    options: DiscoveryOptions,
}

#[allow(clippy::missing_errors_doc)]
impl SyncEngine {
    /// Create a new sync engine
    pub fn new<P: AsRef<Path>>(project_root: P, manifest_path: P) -> Self {
        Self {
            project_root: project_root.as_ref().to_path_buf(),
            manifest_path: manifest_path.as_ref().to_path_buf(),
            options: DiscoveryOptions::default(),
        }
    }

    /// Set discovery options
    #[must_use]
    pub fn with_options(mut self, options: DiscoveryOptions) -> Self {
        self.options = options;
        self
    }

    /// Load manifest from disk
    #[must_use]
    pub fn load_manifest(&self) -> SyncManifest {
        if self.manifest_path.exists()
            && let Ok(content) = std::fs::read_to_string(&self.manifest_path)
            && let Ok(manifest) = serde_json::from_str(&content)
        {
            return SyncManifest(manifest);
        }
        SyncManifest(HashMap::new())
    }

    /// Save manifest to disk
    pub fn save_manifest(&self, manifest: &SyncManifest) -> std::io::Result<()> {
        if let Some(parent) = self.manifest_path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        let content = serde_json::to_string_pretty(&manifest.0)?;
        std::fs::write(&self.manifest_path, content)
    }

    /// Compute content hash using xxhash (fast)
    #[must_use]
    pub fn compute_hash(content: &str) -> String {
        format!("{:016x}", xxh3::xxh3_64(content.as_bytes()))
    }

    /// Compute hash for file content
    #[must_use]
    pub fn compute_file_hash(path: &Path) -> Option<String> {
        std::fs::read_to_string(path)
            .ok()
            .map(|c| Self::compute_hash(&c))
    }

    /// Discover files in project root
    #[must_use]
    pub fn discover_files(&self) -> Vec<PathBuf> {
        let mut files = Vec::new();
        self.discover_recursive(&self.project_root, &mut files);
        files
    }

    fn discover_recursive(&self, dir: &Path, files: &mut Vec<PathBuf>) {
        if let Ok(entries) = std::fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    if self.should_skip_dir(&path) {
                        continue;
                    }
                    self.discover_recursive(&path, files);
                } else if path.is_file() {
                    // Skip hidden files
                    if self.options.skip_hidden
                        && let Some(name) = path.file_name()
                        && name.to_string_lossy().starts_with('.')
                    {
                        continue;
                    }
                    if self.should_include_file(&path) {
                        files.push(path);
                    }
                }
            }
        }
    }

    fn should_skip_dir(&self, path: &Path) -> bool {
        // Skip hidden directories
        if let Some(name) = path.file_name() {
            let name_str = name.to_string_lossy();
            if name_str.starts_with('.') {
                return true;
            }
        }

        // Skip configured directories
        for skip_dir in &self.options.skip_dirs {
            if let Some(name) = path.file_name()
                && name.to_string_lossy() == *skip_dir
            {
                return true;
            }
        }

        false
    }

    fn should_include_file(&self, path: &Path) -> bool {
        // Check extension
        if let Some(ext) = path.extension() {
            let ext_str = ext.to_string_lossy().to_lowercase();
            if !self.options.extensions.is_empty() && !self.options.extensions.contains(&ext_str) {
                return false;
            }
        } else {
            return false;
        }

        // Check file size
        if let Ok(metadata) = path.metadata()
            && metadata.len() > self.options.max_file_size
        {
            return false;
        }

        true
    }

    /// Compute sync diff: added, modified, deleted files
    #[must_use]
    pub fn compute_diff(&self, manifest: &SyncManifest, files: &[PathBuf]) -> SyncResult {
        let mut result = SyncResult::default();

        // Build current files map (relative -> absolute)
        let current_files: HashMap<String, PathBuf> = files
            .iter()
            .filter_map(|f| {
                f.strip_prefix(&self.project_root)
                    .ok()
                    .map(|p| (p.to_string_lossy().to_string(), f.clone()))
            })
            .collect();

        // Check for added/modified files
        for (rel_path, abs_path) in &current_files {
            if let Ok(content) = std::fs::read_to_string(abs_path) {
                let hash = Self::compute_hash(&content);

                match manifest.0.get(rel_path) {
                    Some(existing_hash) => {
                        if &hash == existing_hash {
                            result.unchanged += 1;
                        } else {
                            result.modified.push(abs_path.clone());
                        }
                    }
                    None => {
                        result.added.push(abs_path.clone());
                    }
                }
            }
        }

        // Check for deleted files
        for rel_path in manifest.0.keys() {
            if !current_files.contains_key(rel_path) {
                result.deleted.push(self.project_root.join(rel_path));
            }
        }

        result
    }

    /// Get project root
    #[must_use]
    pub fn project_root(&self) -> &PathBuf {
        &self.project_root
    }

    /// Get manifest path
    #[must_use]
    pub fn manifest_path(&self) -> &PathBuf {
        &self.manifest_path
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    #[test]
    fn test_manifest_load_save() {
        let temp_dir = TempDir::new().unwrap();
        let manifest_path = temp_dir.path().join("manifest.json");
        let engine = SyncEngine::new(temp_dir.path(), &manifest_path);

        // Create initial manifest
        let mut manifest = SyncManifest(HashMap::new());
        manifest
            .0
            .insert("test.py".to_string(), "hash123".to_string());

        // Save and load
        engine.save_manifest(&manifest).unwrap();
        let loaded = engine.load_manifest();

        assert_eq!(loaded.0.get("test.py"), Some(&"hash123".to_string()));
    }

    #[test]
    fn test_compute_hash() {
        let hash1 = SyncEngine::compute_hash("hello world");
        let hash2 = SyncEngine::compute_hash("hello world");
        let hash3 = SyncEngine::compute_hash("different");

        assert_eq!(hash1, hash2);
        assert_ne!(hash1, hash3);
        // xxhash produces 16 character hex
        assert_eq!(hash1.len(), 16);
    }

    #[test]
    fn test_discover_files() {
        let temp_dir = TempDir::new().unwrap();

        // Create test files
        fs::write(temp_dir.path().join("test.py"), "print('hello')").unwrap();
        fs::write(temp_dir.path().join("test.md"), "# Hello").unwrap();
        fs::write(temp_dir.path().join("test.txt"), "hello").unwrap(); // Should be skipped

        // Create subdirectory with file
        let subdir = temp_dir.path().join("subdir");
        fs::create_dir_all(&subdir).unwrap();
        fs::write(subdir.join("module.py"), "def foo(): pass").unwrap();

        let manifest_path = temp_dir.path().join("manifest.json");
        let engine = SyncEngine::new(temp_dir.path(), &manifest_path);
        let files = engine.discover_files();

        // Should find .py and .md files, not .txt
        assert!(
            files
                .iter()
                .any(|p| p.extension().map(|e| e == "py").unwrap_or(false))
        );
        assert!(
            files
                .iter()
                .any(|p| p.extension().map(|e| e == "md").unwrap_or(false))
        );
        assert!(
            !files
                .iter()
                .any(|p| p.extension().map(|e| e == "txt").unwrap_or(false))
        );
    }

    #[test]
    fn test_compute_diff() {
        let temp_dir = TempDir::new().unwrap();

        // Create test files
        fs::write(temp_dir.path().join("new.py"), "new content").unwrap();
        fs::write(temp_dir.path().join("modified.py"), "modified content").unwrap();
        fs::write(temp_dir.path().join("existing.py"), "existing").unwrap();

        let manifest_path = temp_dir.path().join("manifest.json");
        let engine = SyncEngine::new(temp_dir.path(), &manifest_path);

        // Create old manifest (existing.py unchanged, modified.py changed, missing new.py)
        let mut old_manifest = SyncManifest(HashMap::new());
        old_manifest.0.insert(
            "existing.py".to_string(),
            SyncEngine::compute_hash("existing"),
        );
        old_manifest
            .0
            .insert("modified.py".to_string(), "old_hash".to_string()); // Different content

        let files = engine.discover_files();
        let diff = engine.compute_diff(&old_manifest, &files);

        // new.py should be in added
        assert!(
            diff.added
                .iter()
                .any(|p| p.file_name().map(|n| n == "new.py").unwrap_or(false))
        );

        // modified.py should be in modified
        assert!(
            diff.modified
                .iter()
                .any(|p| p.file_name().map(|n| n == "modified.py").unwrap_or(false))
        );

        // existing.py should be unchanged
        assert_eq!(diff.unchanged, 1);
    }

    #[test]
    fn test_skip_hidden_and_directories() {
        let temp_dir = TempDir::new().unwrap();

        // Create hidden file/dir
        fs::write(temp_dir.path().join(".hidden.py"), "hidden").unwrap();
        fs::create_dir_all(temp_dir.path().join(".git")).unwrap();
        fs::write(temp_dir.path().join(".git").join("config"), "config").unwrap();

        // Create normal files
        fs::write(temp_dir.path().join("visible.py"), "visible").unwrap();

        let manifest_path = temp_dir.path().join("manifest.json");
        let engine = SyncEngine::new(temp_dir.path(), &manifest_path);
        let files = engine.discover_files();

        // Should not include hidden files (file name starts with .)
        assert!(!files.iter().any(|p| {
            p.file_name()
                .map(|n| n.to_string_lossy().starts_with('.'))
                .unwrap_or(false)
        }));
        // Should include visible file
        assert!(
            files
                .iter()
                .any(|p| p.file_name().map(|n| n == "visible.py").unwrap_or(false))
        );
    }
}
