//! Benchmark tests for Cargo.toml parsing performance.
//!
//! These tests measure the performance of parsing Cargo.toml files
//! for dependency extraction.

use omni_knowledge::dependency_indexer::parse_cargo_dependencies;
use std::io::Write as StdWrite;
use tempfile::NamedTempFile;

/// Generate a complex Cargo.toml for benchmarking.
fn generate_cargo_toml(dep_count: usize) -> String {
    let mut content = String::from(
        "[package]\nname = \"test-crate\"\nversion = \"0.1.0\"\nedition = \"2021\"\n\n[dependencies]\n",
    );

    // Add simple dependencies
    for i in 0..dep_count {
        content.push_str(&format!(
            "dep{} = \"{}.{}.{}\"\n",
            i,
            i / 100,
            (i / 10) % 10,
            i % 10
        ));
    }

    content.push_str("\n[dev-dependencies]\n");
    for i in 0..(dep_count / 3) {
        content.push_str(&format!(
            "dev_dep{} = \"{}.{}.{}\"\n",
            i,
            i / 100,
            (i / 10) % 10,
            i % 10
        ));
    }

    content
}

/// Generate a workspace Cargo.toml for benchmarking.
fn generate_workspace_cargo_toml(member_count: usize, dep_count: usize) -> String {
    let mut content = String::from("[workspace]\nmembers = [");

    // Add workspace members
    for i in 0..member_count {
        content.push_str(&format!("\"crate{}\", ", i));
    }
    content.push_str("]\n\n[workspace.dependencies]\n");

    // Add workspace dependencies with complex format
    for i in 0..dep_count {
        content.push_str(&format!(
            "dep{} = {{ version = \"{}.{}.{}\", features = [\"feature-a\", \"feature-b\"] }}\n",
            i,
            i / 100,
            (i / 10) % 10,
            i % 10
        ));
    }

    // Add simple dependencies
    for i in 0..(dep_count / 2) {
        content.push_str(&format!(
            "simple_dep{} = \"{}.{}.{}\"\n",
            i,
            i / 100,
            (i / 10) % 10,
            i % 10
        ));
    }

    content
}

/// Benchmark test for parsing Cargo.toml with many dependencies.
#[test]
fn test_cargo_toml_parsing_performance() {
    const DEP_COUNT: usize = 100;

    let start = std::time::Instant::now();

    // Parse multiple Cargo.toml files
    for _ in 0..20 {
        let content = generate_cargo_toml(DEP_COUNT);
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_cargo_dependencies(file.path()).unwrap();
        assert!(!deps.is_empty());
    }

    let elapsed = start.elapsed();

    // Should parse 20 files with 100 deps each in under 1 second
    let max_duration = std::time::Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "Cargo.toml parsing took {:.2}s for 20 files x {} deps, expected < 1s",
        elapsed.as_secs_f64(),
        DEP_COUNT
    );

    println!(
        "Cargo.toml parsing: 20 files x {} deps = {:.2}ms",
        DEP_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for parsing workspace Cargo.toml.
#[test]
fn test_workspace_cargo_toml_parsing_performance() {
    const MEMBER_COUNT: usize = 50;
    const DEP_COUNT: usize = 100;

    let start = std::time::Instant::now();

    // Parse multiple workspace Cargo.toml files
    for _ in 0..10 {
        let content = generate_workspace_cargo_toml(MEMBER_COUNT, DEP_COUNT);
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_cargo_dependencies(file.path()).unwrap();
        assert!(!deps.is_empty());
    }

    let elapsed = start.elapsed();

    // Should parse 10 workspace files in under 1 second
    let max_duration = std::time::Duration::from_secs(1);
    assert!(
        elapsed < max_duration,
        "Workspace Cargo.toml parsing took {:.2}s for 10 files, expected < 1s",
        elapsed.as_secs_f64()
    );

    println!(
        "Workspace Cargo.toml parsing: 10 files x {} members x {} deps = {:.2}ms",
        MEMBER_COUNT,
        DEP_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for parsing complex dependency format.
#[test]
fn test_complex_dependency_parsing_performance() {
    // Test the complex format: name = { version = "x.y.z", features = [...] }
    let content = r#"
[package]
name = "test"
version = "0.1.0"

[dependencies]
tokio = { version = "1.49.0", features = ["full", "tracing"] }
serde = { version = "1.0.228", features = ["derive", "rc"] }
serde_json = { version = "1.0.149", features = ["std", "arbitrary_precision"] }
anyhow = { version = "1.0.100", features = ["backtrace"] }
thiserror = { version = "2.0.17", features = ["std"] }
async-trait = { version = "0.1.83", features = ["async-lift"] }
futures = { version = "0.3.31", features = ["async-await", "compat"] }
"#;

    let start = std::time::Instant::now();

    // Parse the same content multiple times
    for _ in 0..100 {
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();

        let deps = parse_cargo_dependencies(file.path()).unwrap();
        assert_eq!(deps.len(), 7);
    }

    let elapsed = start.elapsed();

    // Should complete 100 parses in under 500ms
    let max_duration = std::time::Duration::from_millis(500);
    assert!(
        elapsed < max_duration,
        "Complex dependency parsing took {:.2}ms for 100 iterations, expected < 500ms",
        elapsed.as_secs_f64() * 1000.0
    );

    println!(
        "Complex dependency parsing: 100 iterations = {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test comparing file I/O vs parsing overhead.
#[test]
fn test_parsing_vs_io_overhead() {
    const DEP_COUNT: usize = 50;

    // Generate content once
    let content = generate_cargo_toml(DEP_COUNT);

    // Test pure parsing (multiple parses of same content)
    let parse_start = std::time::Instant::now();
    for _ in 0..50 {
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let _deps = parse_cargo_dependencies(file.path()).unwrap();
    }
    let parse_elapsed = parse_start.elapsed();

    // Report the breakdown
    println!(
        "Parsing {} deps: {:.2}ms for 50 iterations (includes I/O)",
        DEP_COUNT,
        parse_elapsed.as_secs_f64() * 1000.0
    );

    // Just verify it completes in reasonable time
    let max_duration = std::time::Duration::from_secs(2);
    assert!(
        parse_elapsed < max_duration,
        "Parsing took too long: {:.2}s",
        parse_elapsed.as_secs_f64()
    );
}
