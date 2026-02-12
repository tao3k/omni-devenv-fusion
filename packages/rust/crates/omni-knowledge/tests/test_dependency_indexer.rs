//! Tests for dependency indexer functionality.

use omni_knowledge::{
    ConfigExternalDependency, DependencyBuildConfig, ExternalSymbol, SymbolIndex, SymbolKind,
};

#[test]
fn test_symbol_index_search() {
    let mut index = SymbolIndex::new();

    // Add test symbols
    index.add_symbols(
        "serde",
        &std::path::PathBuf::from("lib.rs"),
        &vec![
            ExternalSymbol {
                name: "Serializer".to_string(),
                kind: SymbolKind::Struct,
                file: std::path::PathBuf::from("lib.rs"),
                line: 10,
                crate_name: "serde".to_string(),
            },
            ExternalSymbol {
                name: "serialize".to_string(),
                kind: SymbolKind::Function,
                file: std::path::PathBuf::from("lib.rs"),
                line: 20,
                crate_name: "serde".to_string(),
            },
        ],
    );

    // Search for "TestStruct"
    let results = index.search("Serializer", 10);
    assert_eq!(results.len(), 1);
    assert_eq!(results[0].name, "Serializer");
    assert_eq!(results[0].kind, SymbolKind::Struct);
}

#[test]
fn test_dependency_config_load() {
    // Test loading config from actual references.yaml
    let config = DependencyBuildConfig::load(
        "/Users/guangtao/ghq/github.com/tao3k/omni-dev-fusion/assets/references.yaml",
    );

    // Should have at least rust and python dependencies
    assert!(!config.manifests.is_empty());

    // Find rust dependency
    let rust_dep = config.manifests.iter().find(|d| d.pkg_type == "rust");
    assert!(rust_dep.is_some());
    assert_eq!(rust_dep.unwrap().registry, Some("cargo".to_string()));

    // Find python dependency
    let py_dep = config.manifests.iter().find(|d| d.pkg_type == "python");
    assert!(py_dep.is_some());
    assert_eq!(py_dep.unwrap().registry, Some("pip".to_string()));
}

#[test]
fn test_external_dependency_new() {
    let dep = ConfigExternalDependency {
        pkg_type: "rust".to_string(),
        registry: Some("cargo".to_string()),
        manifests: vec!["**/Cargo.toml".to_string()],
    };
    // Access inner directly in Rust tests
    assert_eq!(dep.pkg_type, "rust");
    assert_eq!(dep.registry, Some("cargo".to_string()));
    assert_eq!(dep.manifests, vec!["**/Cargo.toml"]);
}

#[test]
fn test_external_dependency_no_registry() {
    let dep = ConfigExternalDependency {
        pkg_type: "python".to_string(),
        registry: None,
        manifests: vec!["**/pyproject.toml".to_string()],
    };

    assert_eq!(dep.pkg_type, "python");
    assert_eq!(dep.registry, None);
}
