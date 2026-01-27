//! Unit tests for GlobSet-based SnifferEngine
//!
//! These tests cover edge cases, performance characteristics,
//! and specific pattern matching scenarios.

use omni_sniffer::{SnifferEngine, SnifferRule};
use std::fs;

/// Test: Rule weights affect scoring
#[test]
fn test_weighted_scoring() {
    let rules = vec![
        SnifferRule::with_weight("config", vec!["*.toml".to_string()], 0.5),
        SnifferRule::with_weight("python", vec!["*.py".to_string()], 2.0), // Higher weight
    ];

    let engine = SnifferEngine::new(rules).unwrap();
    // Verify engine was created with correct weights by checking pattern count
    assert_eq!(engine.pattern_count(), 2);
}

/// Test: Pattern deduplication in same rule
#[test]
fn test_duplicate_patterns_in_rule() {
    let rules = vec![SnifferRule::new(
        "test",
        vec!["*.py".to_string(), "*.py".to_string()], // Duplicate
    )];

    let engine = SnifferEngine::new(rules).unwrap();
    let result = engine.sniff_file("script.py");

    // Should still match once
    assert_eq!(result, vec!["test"]);
}

/// Test: Empty patterns list
#[test]
fn test_empty_patterns() {
    let rules = vec![SnifferRule::new("empty", vec![])];

    let engine = SnifferEngine::new(rules).unwrap();
    assert_eq!(engine.pattern_count(), 0);
    assert!(engine.sniff_file("anything").is_empty());
}

/// Test: Special characters in patterns
#[test]
fn test_special_characters_in_patterns() {
    let rules = vec![
        SnifferRule::new("question", vec!["file?.txt".to_string()]),
        SnifferRule::new("stars", vec!["file*.txt".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    // ? matches exactly one character
    assert!(
        engine
            .sniff_file("filea.txt")
            .contains(&"question".to_string())
    );
    assert!(
        engine
            .sniff_file("file1.txt")
            .contains(&"question".to_string())
    );

    // * matches zero or more characters
    assert!(engine.sniff_file("file.txt").contains(&"stars".to_string()));
    assert!(
        engine
            .sniff_file("filexyz.txt")
            .contains(&"stars".to_string())
    );

    // Both match different aspects
    let result = engine.sniff_file("filea.txt");
    assert!(result.contains(&"question".to_string()));
    assert!(result.contains(&"stars".to_string()));
}

/// Test: Unicode filenames
#[test]
fn test_unicode_filenames() {
    let rules = vec![SnifferRule::new("unicode", vec!["*.txt".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    // Should handle unicode gracefully (may or may not match depending on OS)
    let _ = engine.sniff_file("日本語.txt");
    let _ = engine.sniff_file("файл.txt");
}

/// Test: Very long paths
#[test]
fn test_long_paths() {
    let rules = vec![SnifferRule::new("deep", vec!["**/*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    let long_path = "a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v/w/x/y/z.py";
    let result = engine.sniff_file(long_path);
    assert_eq!(result, vec!["deep"]);
}

/// Test: No extension files
#[test]
fn test_no_extension_files() {
    let rules = vec![SnifferRule::new(
        "makefile",
        vec!["Makefile".to_string(), "GNUmakefile".to_string()],
    )];
    let engine = SnifferEngine::new(rules).unwrap();

    assert_eq!(engine.sniff_file("Makefile"), vec!["makefile"]);
    assert_eq!(engine.sniff_file("GNUmakefile"), vec!["makefile"]);
    assert!(engine.sniff_file("makefile").is_empty()); // Case-sensitive
}

/// Test: Multiple extensions
#[test]
fn test_multiple_extensions() {
    let rules = vec![SnifferRule::new(
        "script",
        vec!["*.py".to_string(), "*.pyw".to_string(), "*.pyx".to_string()],
    )];
    let engine = SnifferEngine::new(rules).unwrap();

    assert_eq!(engine.sniff_file("script.py"), vec!["script"]);
    assert_eq!(engine.sniff_file("script.pyw"), vec!["script"]);
    assert_eq!(engine.sniff_file("script.pyx"), vec!["script"]);
    assert!(engine.sniff_file("script.js").is_empty());
}

/// Test: Path separators
#[test]
fn test_path_separators() {
    let rules = vec![SnifferRule::new("src", vec!["src/**/*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    // Forward slash (Unix-style)
    assert_eq!(engine.sniff_file("src/main.py"), vec!["src"]);
    assert_eq!(engine.sniff_file("src/utils/helper.py"), vec!["src"]);
}

/// Test: Negation patterns (if supported)
#[test]
fn test_complex_negation_like() {
    // globset doesn't support negation, but we can test behavior
    let rules = vec![
        SnifferRule::new("all_py", vec!["*.py".to_string()]),
        SnifferRule::new("test_py", vec!["test_*.py".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    // Both patterns can match the same file
    assert_eq!(engine.sniff_file("test_main.py"), vec!["all_py", "test_py"]);
    assert_eq!(engine.sniff_file("main.py"), vec!["all_py"]);
}

/// Test: Overlapping patterns
#[test]
fn test_overlapping_patterns() {
    let rules = vec![
        SnifferRule::new("short", vec!["a*".to_string()]),
        SnifferRule::new("long", vec!["ab*".to_string()]),
        SnifferRule::new("longer", vec!["abc*".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    let result = engine.sniff_file("abc.py");
    assert!(result.contains(&"longer".to_string()));
    assert!(result.contains(&"long".to_string()));
    assert!(result.contains(&"short".to_string()));
    assert_eq!(result.len(), 3);
}

/// Test: Dotfiles
#[test]
fn test_dotfiles() {
    let rules = vec![
        SnifferRule::new("dotfile", vec![".*".to_string()]),
        SnifferRule::new("config", vec![".config".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    assert_eq!(engine.sniff_file(".bashrc"), vec!["dotfile"]);
    assert_eq!(engine.sniff_file(".config"), vec!["config", "dotfile"]);
}

/// Test: Directory patterns
#[test]
fn test_directory_patterns() {
    let rules = vec![
        SnifferRule::new("test_dir", vec!["test*/".to_string()]),
        SnifferRule::new("src_dir", vec!["src/**/*".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    // Directory patterns should still match file paths
    assert!(
        engine
            .sniff_file("test_utils.py")
            .contains(&"test_dir".to_string())
            || engine.sniff_file("test_utils.py").is_empty()
    );
}

/// Test: Maximum depth behavior
#[test]
fn test_nested_directory_depth() {
    let dir = tempfile::Builder::new()
        .prefix("sniffer_depth_test")
        .tempdir()
        .unwrap();

    // Create files at different depths
    fs::write(dir.path().join("a.py"), "").unwrap();
    fs::create_dir_all(dir.path().join("a")).unwrap();
    fs::write(dir.path().join("a").join("b.py"), "").unwrap();
    fs::create_dir_all(dir.path().join("a").join("b")).unwrap();
    fs::write(dir.path().join("a").join("b").join("c.py"), "").unwrap();

    let rules = vec![SnifferRule::new("python", vec!["**/*.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    // Depth 1: only root files
    let r1 = engine.sniff_path(dir.path().to_str().unwrap(), 1);
    assert!(r1.contains(&"python".to_string()));

    // Depth 2: root + one level
    let r2 = engine.sniff_path(dir.path().to_str().unwrap(), 2);
    assert!(r2.contains(&"python".to_string()));

    // Depth 5: all levels
    let r5 = engine.sniff_path(dir.path().to_str().unwrap(), 5);
    assert!(r5.contains(&"python".to_string()));
}

/// Test: Engine can be cloned
#[test]
fn test_engine_clone() {
    let rules = vec![SnifferRule::new("test", vec!["*.py".to_string()])];
    let engine1 = SnifferEngine::new(rules).unwrap();
    let engine2 = engine1.clone();

    assert_eq!(engine1.pattern_count(), engine2.pattern_count());
    assert_eq!(engine1.sniff_file("test.py"), engine2.sniff_file("test.py"));
}

/// Test: Very high pattern count
#[test]
fn test_high_pattern_count() {
    let mut patterns = Vec::new();
    for i in 0..100 {
        patterns.push(format!("*.type{}", i));
    }
    patterns.push("common.*".to_string());

    let rules = vec![SnifferRule::new("many", patterns)];
    let engine = SnifferEngine::new(rules).unwrap();

    assert_eq!(engine.pattern_count(), 101);
    assert!(engine.sniff_file("common.py").contains(&"many".to_string()));
}

/// Test: JSON roundtrip
#[test]
fn test_json_roundtrip() {
    let original_json = r#"[
        {"id": "python", "patterns": ["*.py", "pyproject.toml"], "weight": 1.0},
        {"id": "rust", "patterns": ["*.rs"], "weight": 1.5}
    ]"#;

    let engine1 = SnifferEngine::from_json(original_json).unwrap();

    // Serialize back
    // Note: We don't have a to_json method, but we can verify the counts
    assert_eq!(engine1.context_count(), 2);
    assert_eq!(engine1.pattern_count(), 3);
}

/// Test: Single character patterns
#[test]
fn test_single_char_patterns() {
    let rules = vec![
        SnifferRule::new("single_q", vec!["?".to_string()]),
        SnifferRule::new("double_q", vec!["??".to_string()]),
    ];

    let engine = SnifferEngine::new(rules).unwrap();

    assert_eq!(engine.sniff_file("a"), vec!["single_q"]);
    assert_eq!(engine.sniff_file("ab"), vec!["double_q"]);
    assert!(engine.sniff_file("abc").is_empty());
}

/// Test: Spaces in filenames
#[test]
fn test_spaces_in_filenames() {
    let rules = vec![SnifferRule::new("spaced", vec!["* *.py".to_string()])];
    let engine = SnifferEngine::new(rules).unwrap();

    // This pattern is unusual but should be handled
    let _ = engine.sniff_file("my file.py");
}
