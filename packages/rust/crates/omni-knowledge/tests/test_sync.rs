//! Integration tests for Rust SyncEngine

use std::fs;
use tempfile::TempDir;

/// Test SyncEngine manifest load/save operations
#[test]
fn test_manifest_load_save() {
    use omni_knowledge::SyncEngine;

    let temp_dir = TempDir::new().unwrap();
    let manifest_path = temp_dir.path().join("manifest.json");
    let engine = SyncEngine::new(temp_dir.path(), &manifest_path);

    // Create initial manifest
    let mut manifest = omni_knowledge::SyncManifest::default();
    manifest
        .0
        .insert("test.py".to_string(), "hash123".to_string());

    // Save and load
    engine.save_manifest(&manifest).unwrap();
    let loaded = engine.load_manifest();

    assert_eq!(loaded.0.get("test.py"), Some(&"hash123".to_string()));
}

/// Test SyncEngine hash computation
#[test]
fn test_compute_hash() {
    use omni_knowledge::SyncEngine;

    let hash1 = SyncEngine::compute_hash("hello world");
    let hash2 = SyncEngine::compute_hash("hello world");
    let hash3 = SyncEngine::compute_hash("different");

    assert_eq!(hash1, hash2);
    assert_ne!(hash1, hash3);
    // xxhash produces 16 character hex
    assert_eq!(hash1.len(), 16);
}

/// Test SyncEngine file discovery
#[test]
fn test_discover_files() {
    use omni_knowledge::SyncEngine;

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

/// Test SyncEngine diff computation with add/modify/delete
#[test]
fn test_compute_diff() {
    use omni_knowledge::{SyncEngine, SyncManifest};

    let temp_dir = TempDir::new().unwrap();

    // Create test files
    fs::write(temp_dir.path().join("new.py"), "new content").unwrap();
    fs::write(temp_dir.path().join("modified.py"), "modified content").unwrap();
    fs::write(temp_dir.path().join("existing.py"), "existing").unwrap();

    let manifest_path = temp_dir.path().join("manifest.json");
    let engine = SyncEngine::new(temp_dir.path(), &manifest_path);

    // Create old manifest (existing unchanged, modified changed, new missing)
    let mut old_manifest = SyncManifest::default();
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

/// Test SyncEngine skip hidden files and directories
#[test]
fn test_skip_hidden_and_directories() {
    use omni_knowledge::SyncEngine;

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

/// Test SyncEngine detects deleted files
#[test]
fn test_deleted_files_detection() {
    use omni_knowledge::{SyncEngine, SyncManifest};

    let temp_dir = TempDir::new().unwrap();
    let manifest_path = temp_dir.path().join("manifest.json");
    let engine = SyncEngine::new(temp_dir.path(), &manifest_path);

    // Create old manifest with files that don't exist on disk
    let mut old_manifest = SyncManifest::default();
    old_manifest
        .0
        .insert("deleted1.py".to_string(), "hash1".to_string());
    old_manifest
        .0
        .insert("deleted2.rs".to_string(), "hash2".to_string());
    old_manifest.0.insert(
        "still_exists.py".to_string(),
        SyncEngine::compute_hash("exists"),
    );

    // Create file for still_exists
    fs::write(temp_dir.path().join("still_exists.py"), "exists").unwrap();

    let files = engine.discover_files();
    let diff = engine.compute_diff(&old_manifest, &files);

    // deleted1.py should be in deleted
    assert!(
        diff.deleted
            .iter()
            .any(|p| p.file_name().map(|n| n == "deleted1.py").unwrap_or(false))
    );
    // deleted2.rs should be in deleted
    assert!(
        diff.deleted
            .iter()
            .any(|p| p.file_name().map(|n| n == "deleted2.rs").unwrap_or(false))
    );
}

/// Test SyncEngine batch operations
#[test]
fn test_batch_diff_computation() {
    use omni_knowledge::{SyncEngine, SyncManifest};

    let temp_dir = TempDir::new().unwrap();

    // Create many files
    for i in 0..50 {
        fs::write(
            temp_dir.path().join(format!("file_{}.py", i)),
            format!("content {}", i),
        )
        .unwrap();
    }

    let manifest_path = temp_dir.path().join("manifest.json");
    let engine = SyncEngine::new(temp_dir.path(), &manifest_path);

    // Empty manifest - all should be added
    let empty_manifest = SyncManifest::default();
    let files = engine.discover_files();
    let diff = engine.compute_diff(&empty_manifest, &files);

    // All 50 files should be added
    assert_eq!(diff.added.len(), 50);
    assert_eq!(diff.modified.len(), 0);
    assert_eq!(diff.unchanged, 0);
}

/// Test SyncEngine with custom discovery options
#[test]
fn test_custom_discovery_options() {
    use omni_knowledge::{DiscoveryOptions, SyncEngine};

    let temp_dir = TempDir::new().unwrap();

    // Create files with different extensions
    fs::write(temp_dir.path().join("test.rs"), "fn main() {}").unwrap();
    fs::write(temp_dir.path().join("test.go"), "package main").unwrap();

    let manifest_path = temp_dir.path().join("manifest.json");

    // Create engine with custom options (only .rs files)
    let options = DiscoveryOptions {
        extensions: vec!["rs".to_string()],
        ..Default::default()
    };

    let engine = SyncEngine::new(temp_dir.path(), &manifest_path).with_options(options);
    let files = engine.discover_files();

    // Should only find .rs file
    assert_eq!(files.len(), 1);
    assert!(files[0].extension().map(|e| e == "rs").unwrap_or(false));
}
