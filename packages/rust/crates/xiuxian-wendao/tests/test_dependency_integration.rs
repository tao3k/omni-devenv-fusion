//! Integration tests for dependency indexer.
//!
//! Note: These tests verify the integration points. Full parsing/fetching
//! is implemented incrementally. See indexer.rs build() for progress.

use std::fs;
use tempfile::TempDir;
use xiuxian_wendao::DependencyIndexer;

/// Integration test for creating indexer with temp project
#[test]
fn test_indexer_with_temp_project() {
    // Create a temp directory
    let temp_dir = TempDir::new().unwrap();
    let temp_root = temp_dir.path().to_str().unwrap();

    // Create a minimal Cargo.toml with a realistic dependency
    let cargo_content = r#"[package]
name = "test-project"
version = "0.1.0"

[dependencies]
anyhow = "1.0.100"
"#;
    let cargo_path = format!("{}/Cargo.toml", temp_root);
    fs::write(&cargo_path, cargo_content).unwrap();

    // Create src directory with a Rust file containing symbols
    fs::create_dir_all(format!("{}/src", temp_root)).unwrap();
    let lib_content = r#"
pub struct TestStruct {
    pub field: String,
}

pub enum TestEnum {
    Variant1,
    Variant2,
}

pub fn test_function() -> bool {
    true
}

trait TestTrait {
    fn method(&self);
}
"#;
    fs::write(format!("{}/src/lib.rs", temp_root), lib_content).unwrap();

    // Create a config file with manifest patterns
    let config_path = format!("{}/references.yaml", temp_root);
    let config_content = r#"
ast_symbols_external:
  - type: rust
    manifests:
      - "**/Cargo.toml"
"#;
    fs::write(&config_path, config_content).unwrap();

    // Create indexer with config - should not panic
    let mut indexer = DependencyIndexer::new(temp_root, Some(&config_path));

    // Test build returns valid structure
    let result = indexer.build(true);

    // Should have processed the Cargo.toml file
    assert!(
        result.files_processed >= 1,
        "Should process at least 1 file"
    );
    assert_eq!(result.errors, 0, "Build should not fail in temp fixture");

    // The crate should be indexed
    let indexed_crates = indexer.get_indexed();
    assert!(!indexed_crates.is_empty(), "Should have indexed crates");
    assert!(indexed_crates.contains(&"test-project".to_string()));

    // Should have extracted symbols from lib.rs
    assert!(
        result.total_symbols >= 4,
        "Should extract at least 4 symbols (struct, enum, fn, trait)"
    );

    // Test search functionality
    let search_results = indexer.search("TestStruct", 10);
    assert!(!search_results.is_empty(), "Should find TestStruct");

    let search_results = indexer.search("test_function", 10);
    assert!(!search_results.is_empty(), "Should find test_function");
}
