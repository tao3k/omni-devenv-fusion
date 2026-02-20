//! Debug test for dependency parsing.
//!
//! Note: These tests verify the integration points. Full parsing/fetching
//! is implemented incrementally. See indexer.rs build() for progress.

use std::fs;
use tempfile::TempDir;
use xiuxian_wendao::DependencyIndexer;

/// Test that the dependency indexer can be created with custom config
#[test]
fn test_indexer_creation_with_config() {
    let temp_dir = TempDir::new().unwrap();
    let temp_root = temp_dir.path().to_str().unwrap();

    // Create a custom references.yaml with manifest pattern
    let config_path = format!("{}/references.yaml", temp_root);
    let config_content = r#"
ast_symbols_external:
  - type: rust
    manifests:
      - "**/Cargo.toml"
"#;
    fs::write(&config_path, config_content).unwrap();

    // Create indexer with config - should not panic
    let indexer = DependencyIndexer::new(temp_root, Some(&config_path));

    // Verify indexer is created correctly
    let crates = indexer.get_indexed();
    assert!(
        crates.is_empty(),
        "New indexer should have no indexed crates"
    );
}

/// Test that build returns a valid result structure
#[test]
fn test_build_returns_valid_structure() {
    let temp_dir = TempDir::new().unwrap();
    let temp_root = temp_dir.path().to_str().unwrap();

    // Create a minimal Cargo.toml
    let cargo_content = r#"[package]
name = "test-project"
version = "0.1.0"

[dependencies]
anyhow = "1.0.100"
"#;
    let cargo_path = format!("{}/Cargo.toml", temp_root);
    fs::write(&cargo_path, cargo_content).unwrap();

    // Provide explicit config so this test is independent from workspace defaults
    let config_path = format!("{}/references.yaml", temp_root);
    let config_content = r#"
ast_symbols_external:
  - type: rust
    manifests:
      - "**/Cargo.toml"
"#;
    fs::write(&config_path, config_content).unwrap();

    // Create indexer
    let mut indexer = DependencyIndexer::new(temp_root, Some(&config_path));

    // Build should return a valid result (placeholder returns zeros)
    let result = indexer.build(true);

    assert!(
        result.files_processed >= 1,
        "Build should process at least the fixture Cargo.toml"
    );
    assert_eq!(result.errors, 0);
    assert!(
        result.crates_indexed >= 1,
        "Build should index at least one crate from fixture"
    );
    assert_eq!(
        result.total_symbols, 0,
        "No source files in fixture means no extracted symbols"
    );
}

/// Test that search methods work on empty index
#[test]
fn test_search_on_empty_index() {
    let temp_dir = TempDir::new().unwrap();
    let temp_root = temp_dir.path().to_str().unwrap();

    let indexer = DependencyIndexer::new(temp_root, None);

    // Search should return empty on new index
    let results = indexer.search("anyhow", 10);
    assert!(
        results.is_empty(),
        "Search on empty index should return empty"
    );

    let crate_results = indexer.search_crate("anyhow", "Error", 10);
    assert!(
        crate_results.is_empty(),
        "Crate search on empty index should return empty"
    );
}

/// Test config loading from file
#[test]
fn test_config_loading() {
    use xiuxian_wendao::DependencyBuildConfig;

    let temp_dir = TempDir::new().unwrap();
    let temp_root = temp_dir.path().to_str().unwrap();

    // Create a custom references.yaml
    let config_path = format!("{}/references.yaml", temp_root);
    let config_content = r#"
ast_symbols_external:
  - type: rust
    registry: cargo
    manifests:
      - "**/Cargo.toml"
  - type: python
    registry: pip
    manifests:
      - "**/pyproject.toml"
"#;
    fs::write(&config_path, config_content).unwrap();

    // Load config
    let config = DependencyBuildConfig::load(&config_path);

    // Should have loaded manifests
    assert!(!config.manifests.is_empty(), "Config should have manifests");

    let rust_dep = config.manifests.iter().find(|d| d.pkg_type == "rust");
    assert!(rust_dep.is_some(), "Should have rust dependency config");
    assert_eq!(rust_dep.unwrap().registry, Some("cargo".to_string()));
}
