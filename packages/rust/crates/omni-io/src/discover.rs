//! High-performance file discovery for knowledge indexing.
//!
//! Uses standard library for walking, optimized for speed.

use std::fs;
use std::path::PathBuf;

/// Options for file discovery.
#[derive(Debug, Clone)]
pub struct DiscoverOptions {
    /// File extensions to include (e.g., `[".py", ".md"]`)
    pub extensions: Vec<String>,
    /// Maximum file size in bytes (default: 1MB)
    pub max_file_size: u64,
    /// Skip hidden files and directories
    pub skip_hidden: bool,
    /// Skip directories by name (e.g., `["target", "node_modules"]`)
    pub skip_dirs: Vec<String>,
    /// Maximum files to return (None for unlimited)
    pub max_files: Option<usize>,
    /// Include subdirectories recursively
    pub recursive: bool,
}

impl Default for DiscoverOptions {
    fn default() -> Self {
        Self {
            extensions: vec![".py".to_string(), ".md".to_string()],
            max_file_size: 1024 * 1024, // 1MB
            skip_hidden: true,
            skip_dirs: vec!["target".to_string(), "node_modules".to_string()],
            max_files: None,
            recursive: true,
        }
    }
}

/// Discover files recursively in a directory matching extensions.
#[must_use]
pub fn discover_files(root: &str, options: &DiscoverOptions) -> Vec<String> {
    let root_path = PathBuf::from(root);

    if !root_path.exists() || !root_path.is_dir() {
        return Vec::new();
    }

    let extensions: Vec<String> = options
        .extensions
        .iter()
        .map(|e| normalize_extension(e))
        .collect();

    let skip_dirs_set: Vec<String> = options.skip_dirs.clone();

    let mut files: Vec<PathBuf> = Vec::new();

    if options.recursive {
        walk_directory(
            &root_path,
            &root_path,
            &extensions,
            options.max_file_size,
            options.skip_hidden,
            &skip_dirs_set,
            &mut files,
        );
    } else {
        read_directory(
            &root_path,
            &root_path,
            &extensions,
            options.max_file_size,
            options.skip_hidden,
            &mut files,
        );
    }

    // Apply max_files limit
    if let Some(max) = options.max_files
        && files.len() > max
    {
        files.truncate(max);
    }

    // Sort and convert to relative paths
    files.sort();
    files
        .into_iter()
        .filter_map(|p| p.to_str().map(ToString::to_string))
        .collect()
}

/// Walk directory recursively.
fn walk_directory(
    root: &PathBuf,
    current: &PathBuf,
    extensions: &[String],
    max_file_size: u64,
    skip_hidden: bool,
    skip_dirs: &[String],
    files: &mut Vec<PathBuf>,
) {
    if let Ok(entries) = fs::read_dir(current) {
        for entry in entries.flatten() {
            let path = entry.path();

            // Skip hidden directories
            if skip_hidden
                && let Some(name) = path.file_name()
                && let Some(s) = name.to_str()
                && s.starts_with('.')
            {
                continue;
            }

            if path.is_dir() {
                // Check if this directory should be skipped
                let dir_name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");

                if skip_dirs.iter().any(|skip| *skip == dir_name) {
                    continue;
                }

                // Recurse into subdirectory
                walk_directory(
                    root,
                    &path,
                    extensions,
                    max_file_size,
                    skip_hidden,
                    skip_dirs,
                    files,
                );
            } else if path.is_file() {
                // Check extension - path.extension() returns "py", we need ".py" to match
                if let Some(ext_os) = path.extension() {
                    let ext = ext_os.to_string_lossy().to_lowercase();
                    let ext_with_dot = format!(".{ext}");
                    if extensions.contains(&ext_with_dot) || extensions.contains(&ext) {
                        // Check file size
                        if let Ok(metadata) = entry.metadata()
                            && metadata.len() <= max_file_size
                            && let Ok(rel_path) = path.strip_prefix(root)
                        {
                            files.push(rel_path.to_path_buf());
                        }
                    }
                }
            }
        }
    }
}

/// Read a single directory (non-recursive).
fn read_directory(
    root: &PathBuf,
    current: &PathBuf,
    extensions: &[String],
    max_file_size: u64,
    skip_hidden: bool,
    files: &mut Vec<PathBuf>,
) {
    if let Ok(entries) = fs::read_dir(current) {
        for entry in entries.flatten() {
            let path = entry.path();

            if path.is_file() {
                // Skip hidden files
                if skip_hidden
                    && let Some(name) = path.file_name()
                    && let Some(s) = name.to_str()
                    && s.starts_with('.')
                {
                    continue;
                }

                // Check extension - path.extension() returns "py", we need ".py" to match
                if let Some(ext_os) = path.extension() {
                    let ext = ext_os.to_string_lossy().to_lowercase();
                    let ext_with_dot = format!(".{ext}");
                    if extensions.contains(&ext_with_dot) || extensions.contains(&ext) {
                        // Check file size
                        if let Ok(metadata) = entry.metadata()
                            && metadata.len() <= max_file_size
                            && let Ok(rel_path) = path.strip_prefix(root)
                        {
                            files.push(rel_path.to_path_buf());
                        }
                    }
                }
            }
        }
    }
}

/// Discover files in a single directory (non-recursive).
#[must_use]
pub fn discover_files_in_dir(
    dir: &str,
    extensions: &[String],
    max_file_size: u64,
    skip_hidden: bool,
) -> Vec<String> {
    let dir_path = PathBuf::from(dir);
    if !dir_path.exists() || !dir_path.is_dir() {
        return Vec::new();
    }

    // Normalize extensions to have dot prefix for matching
    let extensions: Vec<String> = extensions.iter().map(|e| normalize_extension(e)).collect();

    let mut files: Vec<PathBuf> = Vec::new();

    if let Ok(entries) = fs::read_dir(&dir_path) {
        for entry in entries.flatten() {
            let path = entry.path();

            // Skip directories
            if path.is_dir() {
                continue;
            }

            // Skip hidden files
            if skip_hidden
                && let Some(name) = path.file_name()
                && let Some(s) = name.to_str()
                && s.starts_with('.')
            {
                continue;
            }

            // Check extension - path.extension() returns "py", we need ".py" to match
            if let Some(ext_os) = path.extension() {
                let ext = ext_os.to_string_lossy().to_lowercase();
                // Check both with and without dot prefix
                let ext_with_dot = format!(".{ext}");
                if extensions.contains(&ext_with_dot) || extensions.contains(&ext) {
                    // Check file size
                    if let Ok(metadata) = entry.metadata()
                        && metadata.len() <= max_file_size
                    {
                        files.push(path);
                    }
                }
            }
        }
    }

    files.sort();
    files
        .into_iter()
        .filter_map(|p| p.to_str().map(ToString::to_string))
        .collect()
}

/// Count files matching extensions in a directory.
#[must_use]
pub fn count_files_in_dir(dir: &str, extensions: &[String], skip_hidden: bool) -> usize {
    discover_files_in_dir(dir, extensions, u64::MAX, skip_hidden).len()
}

/// Check if a path should be skipped.
#[must_use]
pub fn should_skip_path(path: &str, skip_hidden: bool, skip_dirs: &[String]) -> bool {
    let path = PathBuf::from(path);

    // Check if any component is a skip directory
    for component in path.components() {
        if let std::path::Component::Normal(name) = component
            && let Some(s) = name.to_str()
            && skip_dirs.iter().any(|skip| *skip == s)
        {
            return true;
        }
    }

    // Check hidden files
    if skip_hidden
        && let Some(file_name) = path.file_name()
        && let Some(s) = file_name.to_str()
        && s.starts_with('.')
    {
        return true;
    }

    false
}

/// Normalize extension to lowercase with dot prefix.
fn normalize_extension(ext: &str) -> String {
    let mut ext = ext.to_lowercase();
    if !ext.starts_with('.') {
        ext = format!(".{ext}");
    }
    ext
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs::File;
    use tempfile::TempDir;

    #[test]
    fn test_discover_files_in_dir() -> std::io::Result<()> {
        let temp = TempDir::new()?;
        let dir = temp.path().to_string_lossy().to_string();
        let dir_path = std::path::Path::new(&dir);

        // Create test files
        File::create(dir_path.join("test.py"))?;
        File::create(dir_path.join("readme.md"))?;
        File::create(dir_path.join("data.txt"))?;

        let extensions = vec!["py".to_string(), "md".to_string()];
        let files = discover_files_in_dir(&dir, &extensions, 1024 * 1024, true);

        // Debug: print what we got
        if files.is_empty()
            && let Ok(entries) = std::fs::read_dir(dir_path)
        {
            let entries: Vec<_> = entries
                .collect::<Result<Vec<_>, std::io::Error>>()
                .unwrap_or_default();
            println!("Directory entries: {entries:?}");
        }

        assert_eq!(files.len(), 2, "Expected 2 files, got: {files:?}");
        assert!(
            files.iter().any(|f| f.ends_with("test.py")),
            "Missing test.py in {files:?}"
        );
        assert!(
            files.iter().any(|f| f.ends_with("readme.md")),
            "Missing readme.md in {files:?}"
        );
        Ok(())
    }

    #[test]
    fn test_discover_files_recursive() -> std::io::Result<()> {
        let temp = TempDir::new()?;
        let dir = temp.path().to_string_lossy().to_string();
        let dir_path = std::path::Path::new(&dir);

        // Create test structure
        File::create(dir_path.join("root.py"))?;
        std::fs::create_dir(dir_path.join("src"))?;
        File::create(dir_path.join("src").join("module.py"))?;
        std::fs::create_dir(dir_path.join("src").join("nested"))?;
        File::create(dir_path.join("src").join("nested").join("deep.py"))?;

        let extensions = vec!["py".to_string()];
        let options = DiscoverOptions {
            extensions,
            recursive: true,
            ..Default::default()
        };

        let files = discover_files(&dir, &options);

        // Debug: print what we got
        if files.len() < 3 {
            println!("Expected >=3 files, got: {files:?}");
        }

        assert!(files.len() >= 3, "Expected >=3 files, got: {files:?}");
        assert!(
            files.iter().any(|f| f.ends_with("root.py")),
            "Missing root.py in {files:?}"
        );
        assert!(
            files.iter().any(|f| f.ends_with("module.py")),
            "Missing module.py in {files:?}"
        );
        assert!(
            files.iter().any(|f| f.ends_with("deep.py")),
            "Missing deep.py in {files:?}"
        );
        Ok(())
    }

    #[test]
    fn test_should_skip_path() {
        let skip_dirs = vec!["target".to_string(), "node_modules".to_string()];

        assert!(should_skip_path(
            "/project/target/file.py",
            true,
            &skip_dirs
        ));
        assert!(should_skip_path(
            "/project/node_modules/pkg",
            true,
            &skip_dirs
        ));
        assert!(!should_skip_path("/project/src/main.py", true, &skip_dirs));
        assert!(!should_skip_path("/project/.config.yml", false, &skip_dirs));
        assert!(should_skip_path("/project/.env", true, &skip_dirs));
    }

    #[test]
    fn test_normalize_extension() {
        assert_eq!(normalize_extension("py"), ".py");
        assert_eq!(normalize_extension(".py"), ".py");
        assert_eq!(normalize_extension("PY"), ".py");
    }
}
