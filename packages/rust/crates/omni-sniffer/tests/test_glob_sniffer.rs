//! Tests for Rust-Native GlobSet Sniffer

use omni_sniffer::{SnifferEngine, SnifferRule};
use std::fs;
use tempfile::TempDir;

/// Helper to create a test directory structure.
fn create_test_project(dir: &TempDir) {
    // Python project
    fs::write(dir.path().join("main.py"), "").unwrap();
    fs::write(dir.path().join("utils.py"), "").unwrap();
    fs::write(dir.path().join("pyproject.toml"), "").unwrap();

    // Rust project in subdirectory
    fs::create_dir_all(dir.path().join("src")).unwrap();
    fs::write(dir.path().join("src").join("main.rs"), "").unwrap();
    fs::write(dir.path().join("Cargo.toml"), "").unwrap();

    // Node.js project
    fs::write(dir.path().join("index.js"), "").unwrap();
    fs::write(dir.path().join("package.json"), "").unwrap();

    // Nested Go project
    fs::create_dir_all(dir.path().join("cmd")).unwrap();
    fs::write(dir.path().join("go.mod"), "").unwrap();
    fs::write(dir.path().join("cmd").join("main.go"), "").unwrap();
}

#[test]
fn test_basic_sniffing() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_test")
        .tempdir()
        .unwrap();
    create_test_project(&dir);

    let rules = vec![
        SnifferRule::new(
            "python",
            vec!["*.py".to_string(), "pyproject.toml".to_string()],
        ),
        SnifferRule::new("rust", vec!["*.rs".to_string(), "Cargo.toml".to_string()]),
        SnifferRule::new(
            "nodejs",
            vec!["*.js".to_string(), "package.json".to_string()],
        ),
        SnifferRule::new("golang", vec!["*.go".to_string(), "go.mod".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();
    let contexts = engine.sniff_path(dir.path().to_str().unwrap(), 10);

    assert!(contexts.contains(&"python".to_string()));
    assert!(contexts.contains(&"rust".to_string()));
    assert!(contexts.contains(&"nodejs".to_string()));
    assert!(contexts.contains(&"golang".to_string()));
}

#[test]
fn test_max_depth_limit() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_test")
        .tempdir()
        .unwrap();

    // Create nested file
    fs::create_dir_all(dir.path().join("a").join("b").join("c")).unwrap();
    fs::write(dir.path().join("a").join("b").join("c").join("deep.py"), "").unwrap();

    let rules = vec![SnifferRule::new("python", vec!["**/*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    // With max_depth=2, should not find deep.py
    let result_shallow = engine.sniff_path(dir.path().to_str().unwrap(), 2);
    assert!(!result_shallow.contains(&"python".to_string()));

    // With max_depth=5, should find it
    let result_deep = engine.sniff_path(dir.path().to_str().unwrap(), 5);
    assert!(result_deep.contains(&"python".to_string()));
}

#[test]
fn test_single_file_sniff() {
    let engine = SnifferEngine::new(vec![SnifferRule::new(
        "python",
        vec!["*.py".to_string(), "pyproject.toml".to_string()],
    )])
    .unwrap();

    assert_eq!(engine.sniff_file("main.py"), vec!["python"]);
    assert_eq!(engine.sniff_file("pyproject.toml"), vec!["python"]);
    assert_eq!(engine.sniff_file("README.md"), Vec::<String>::new());
}

#[test]
fn test_pattern_to_rule_mapping() {
    let rules = vec![
        SnifferRule::new("python", vec!["*.py".to_string()]),
        SnifferRule::new("config", vec!["*.toml".to_string(), "*.json".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    // Should map to correct rule IDs
    assert_eq!(engine.sniff_file("script.py"), vec!["python"]);
    assert_eq!(engine.sniff_file("config.json"), vec!["config"]);
    assert_eq!(engine.sniff_file("Cargo.toml"), vec!["config"]);
}

#[test]
fn test_scoring() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_test")
        .tempdir()
        .unwrap();

    // Create multiple Python files
    for i in 0..5 {
        fs::write(dir.path().join(format!("file_{}.py", i)), "").unwrap();
    }
    // Only one Rust file
    fs::write(dir.path().join("main.rs"), "").unwrap();

    let rules = vec![
        SnifferRule::with_weight("python", vec!["*.py".to_string()], 1.0),
        SnifferRule::with_weight("rust", vec!["*.rs".to_string()], 1.0),
    ];

    let engine = SnifferEngine::new(rules).unwrap();
    let scored = engine.sniff_path_with_scores(dir.path().to_str().unwrap(), 10);

    // Python should have higher score (more matches)
    let python_score = scored.iter().find(|(id, _)| id == "python").unwrap().1;
    let rust_score = scored.iter().find(|(id, _)| id == "rust").unwrap().1;

    assert!(python_score > rust_score);
}

#[test]
fn test_has_any_context() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_test")
        .tempdir()
        .unwrap();

    fs::write(dir.path().join("main.py"), "").unwrap();

    let rules = vec![SnifferRule::new("python", vec!["*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    assert!(engine.has_any_context(dir.path().to_str().unwrap(), 5));
}

#[test]
fn test_empty_directory() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_test")
        .tempdir()
        .unwrap();

    let rules = vec![SnifferRule::new("python", vec!["*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    let result = engine.sniff_path(dir.path().to_str().unwrap(), 5);
    assert!(result.is_empty());
}

#[test]
fn test_invalid_pattern() {
    let rules = vec![SnifferRule::new("test", vec!["[invalid".to_string()])];
    let result = SnifferEngine::new(rules);
    assert!(result.is_err());
}

#[test]
fn test_json_serialization() {
    let json = r#"[
        {"id": "python", "patterns": ["*.py"], "weight": 1.0},
        {"id": "rust", "patterns": ["*.rs"], "weight": 2.0}
    ]"#;

    let engine = SnifferEngine::from_json(json).unwrap();
    assert_eq!(engine.context_count(), 2);
    assert_eq!(engine.pattern_count(), 2);
}

#[test]
fn test_deduplication() {
    // Same pattern in multiple rules
    let rules = vec![
        SnifferRule::new("python", vec!["*.py".to_string(), "*.pyc".to_string()]),
        SnifferRule::new("pyc", vec!["*.pyc".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();
    let result = engine.sniff_file("module.pyc");

    // Should match both
    assert_eq!(result.len(), 2);
}

#[test]
fn test_nested_patterns() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_test")
        .tempdir()
        .unwrap();

    fs::create_dir_all(dir.path().join("src")).unwrap();
    fs::write(dir.path().join("src").join("main.py"), "").unwrap();

    let rules = vec![SnifferRule::new("python", vec!["**/*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    let result = engine.sniff_path(dir.path().to_str().unwrap(), 10);
    assert!(result.contains(&"python".to_string()));
}

#[test]
fn test_case_sensitivity() {
    let engine =
        SnifferEngine::new(vec![SnifferRule::new("python", vec!["*.PY".to_string()])]).unwrap();

    // Default globset is case-sensitive on Unix
    let python = "python".to_string();
    assert!(engine.sniff_file("main.PY").contains(&python));
    assert!(!engine.sniff_file("main.py").contains(&python));
}

#[test]
fn test_complex_patterns() {
    let rules = vec![
        SnifferRule::new(
            "config",
            vec![
                "pyproject.toml".to_string(),
                "setup.py".to_string(),
                "Makefile".to_string(),
            ],
        ),
        SnifferRule::new(
            "test",
            vec!["test_*.py".to_string(), "*_test.py".to_string()],
        ),
        SnifferRule::new("src", vec!["src/**/*.py".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    assert_eq!(
        engine.sniff_file("pyproject.toml"),
        vec!["config".to_string()]
    );
    assert_eq!(engine.sniff_file("test_main.py"), vec!["test".to_string()]);
    assert_eq!(engine.sniff_file("main_test.py"), vec!["test".to_string()]);
}
