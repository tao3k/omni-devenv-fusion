//! Benchmark tests for pyproject.toml parsing performance.
//!
//! These tests measure the performance of parsing pyproject.toml files
//! for Python dependency extraction.

use omni_knowledge::dependency_indexer::parse_pyproject_dependencies;
use std::io::Write as StdWrite;
use tempfile::NamedTempFile;

/// Generate a pyproject.toml with many dependencies.
fn generate_pyproject_toml(dep_count: usize) -> String {
    let mut content = String::from(
        r#"[project]
name = "test-project"
version = "0.1.0"
description = "A test project"
requires-python = ">=3.10"
dependencies = [
"#,
    );

    // Add dependencies with various version specifiers
    for i in 0..dep_count {
        content.push_str(&format!(
            "    \"package{}=={}.{}.{}\",\n",
            i,
            i / 100,
            (i / 10) % 10,
            i % 10
        ));
    }

    content.push_str("]\n\n[project.optional-dependencies]\ndev = [\n");
    for i in 0..(dep_count / 3) {
        content.push_str(&format!("    \"dev_package{}>=1.0.0\",\n", i));
    }
    content.push_str("]\n");

    content
}

/// Generate a complex pyproject.toml with extras.
fn generate_pyproject_toml_with_extras(dep_count: usize) -> String {
    let mut content = String::from(
        r#"[project]
name = "test-project"
version = "0.1.0"
dependencies = [
"#,
    );

    // Add dependencies with extras (e.g., package[extra]==version)
    for i in 0..dep_count {
        let extra = if i % 5 == 0 {
            "ssl"
        } else if i % 5 == 1 {
            "cli"
        } else if i % 5 == 2 {
            "dev"
        } else {
            "full"
        };
        content.push_str(&format!(
            "    \"package{}[{}]=={}.{}.{}\",\n",
            i,
            extra,
            i / 100,
            (i / 10) % 10,
            i % 10
        ));
    }

    content.push_str("]\n");
    content
}

/// Benchmark test for parsing pyproject.toml with many dependencies.
#[test]
fn test_pyproject_parsing_performance() {
    const DEP_COUNT: usize = 100;

    let start = std::time::Instant::now();

    // Parse multiple pyproject.toml files
    for _ in 0..20 {
        let content = generate_pyproject_toml(DEP_COUNT);
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_pyproject_dependencies(file.path()).unwrap();
        assert!(!deps.is_empty());
    }

    let elapsed = start.elapsed();

    // Should parse 20 files with 100 deps each in under 1 second
    let max_duration = std::time::Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "pyproject.toml parsing took {:.2}s for 20 files x {} deps, expected < 1s",
        elapsed.as_secs_f64(),
        DEP_COUNT
    );

    println!(
        "pyproject.toml parsing: 20 files x {} deps = {:.2}ms",
        DEP_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for parsing pyproject.toml with extras.
#[test]
fn test_pyproject_extras_parsing_performance() {
    const DEP_COUNT: usize = 100;

    let start = std::time::Instant::now();

    // Parse multiple pyproject.toml files with extras
    for _ in 0..20 {
        let content = generate_pyproject_toml_with_extras(DEP_COUNT);
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_pyproject_dependencies(file.path()).unwrap();
        assert!(!deps.is_empty());
    }

    let elapsed = start.elapsed();

    // Should complete in under 1 second
    let max_duration = std::time::Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "pyproject.toml with extras parsing took {:.2}s, expected < 1s",
        elapsed.as_secs_f64()
    );

    println!(
        "pyproject.toml with extras: 20 files x {} deps = {:.2}ms",
        DEP_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for parsing minimal pyproject.toml.
#[test]
fn test_minimal_pyproject_parsing_performance() {
    let content = r#"
[project]
name = "test"
version = "0.1.0"
dependencies = [
    "requests>=2.0",
    "click>=8.0",
    "rich>=13.0",
    "typer>=0.9",
    "pydantic>=2.0",
]
"#;

    let start = std::time::Instant::now();

    // Parse the same content many times
    for _ in 0..100 {
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_pyproject_dependencies(file.path()).unwrap();
        assert_eq!(deps.len(), 5);
    }

    let elapsed = start.elapsed();

    // Should complete 100 parses in under 300ms
    let max_duration = std::time::Duration::from_millis(300);
    assert!(
        elapsed < max_duration,
        "Minimal pyproject parsing took {:.2}ms for 100 iterations, expected < 300ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Minimal pyproject parsing: 100 iterations = {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for regex fallback parsing.
#[test]
fn test_regex_fallback_parsing_performance() {
    // This tests the regex fallback path (when TOML parsing fails)
    let content =
        "package1==1.0.0\npackage2>=2.0.0\npackage3~=4.0.0\nanother_package[extra]==5.0.0\n";

    let start = std::time::Instant::now();

    for _ in 0..100 {
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_pyproject_dependencies(file.path()).unwrap();
        assert_eq!(deps.len(), 4);
    }

    let elapsed = start.elapsed();

    // Should complete 100 parses in under 200ms
    let max_duration = std::time::Duration::from_millis(200);
    assert!(
        elapsed < max_duration,
        "Regex fallback parsing took {:.2}ms for 100 iterations, expected < 200ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Regex fallback parsing: 100 iterations = {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for mixed pyproject.toml scenarios.
#[test]
fn test_mixed_pyproject_parsing_performance() {
    const FILE_COUNT: usize = 30;

    let start = std::time::Instant::now();
    let mut total_deps = 0;

    for i in 0..FILE_COUNT {
        let dep_count = 25 + (i % 50); // Vary the number of deps

        let content = if i % 3 == 0 {
            generate_pyproject_toml_with_extras(dep_count)
        } else {
            generate_pyproject_toml(dep_count)
        };

        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_pyproject_dependencies(file.path()).unwrap();
        total_deps += deps.len();
    }

    let elapsed = start.elapsed();

    // Should complete in under 2 seconds
    let max_duration = std::time::Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Mixed pyproject parsing took {:.2}s for {} files, expected < 2s",
        elapsed.as_secs_f64(),
        FILE_COUNT
    );

    println!(
        "Mixed pyproject parsing: {} files = {:.2}ms ({} total deps)",
        FILE_COUNT,
        elapsed.as_secs_f64() * 1000.0,
        total_deps
    );
}
