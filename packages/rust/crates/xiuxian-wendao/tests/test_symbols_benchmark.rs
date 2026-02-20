//! Benchmark tests for symbols extraction performance.
//!
//! These tests measure the performance of symbol extraction from Rust and Python
//! source files. They are designed to be run with `cargo test` and validate
//! that symbol extraction completes within acceptable time limits.

use std::io::Write as IoWrite;
use std::path::PathBuf;
use tempfile::NamedTempFile;

use xiuxian_wendao::SymbolIndex;
use xiuxian_wendao::dependency_indexer::{ExternalSymbol, SymbolKind, extract_symbols};

/// Generate a large Rust source file for benchmarking.
fn generate_rust_test_file(line_count: usize) -> String {
    let mut content = String::with_capacity(line_count * 50);

    // Add structs
    for i in 0..(line_count / 50) {
        content.push_str(&format!(
            r#"pub struct Struct{} {{
    field_{}: String,
    field_{}: i32,
}}
"#,
            i, i, i
        ));
    }

    // Add enums
    for i in 0..(line_count / 100) {
        content.push_str(&format!(
            r#"pub enum Enum{} {{
    VariantA,
    VariantB(i32),
    VariantC {{ x: i32, y: i32 }},
}}
"#,
            i
        ));
    }

    // Add functions
    for i in 0..(line_count / 30) {
        content.push_str(&format!(
            r#"pub fn function_{}(arg1: &str, arg2: i32) -> Result<(), Box<dyn std::error::Error>> {{
    let _result = process_data(arg1, arg2);
    Ok(())
}}
"#,
            i
        ));
    }

    // Add traits
    for i in 0..(line_count / 80) {
        content.push_str(&format!(
            r#"pub trait Trait{} {{
    fn method_a(&self) -> i32;
    fn method_b(&self, x: i32) -> bool;
}}
"#,
            i
        ));
    }

    content
}

/// Generate a large Python source file for benchmarking.
fn generate_python_test_file(line_count: usize) -> String {
    let mut content = String::with_capacity(line_count * 40);

    // Add classes
    for i in 0..(line_count / 50) {
        content.push_str(&format!(
            r#"class Class{}:
    def __init__(self, param_a: str, param_b: int):
        self.param_a = param_a
        self.param_b = param_b

    def method_a(self) -> str:
        return self.param_a.upper()

    def method_b(self, value: int) -> bool:
        return value > 0

    async def async_method(self) -> dict:
        return {{"status": "ok"}}
"#,
            i
        ));
    }

    // Add functions
    for i in 0..(line_count / 20) {
        content.push_str(&format!(
            r#"def function_{}(arg1: str, arg2: int) -> bool:
    """Process data and return result."""
    result = process(arg1, arg2)
    return result

async def async_function_{}(data: dict) -> list:
    """Async data processing."""
    results = []
    return results
"#,
            i, i
        ));
    }

    content
}

/// Benchmark test for Rust symbol extraction.
#[test]
fn test_rust_symbol_extraction_performance() {
    const FILE_COUNT: usize = 50;
    const LINES_PER_FILE: usize = 500;

    let start = std::time::Instant::now();

    // Create and process multiple test files
    let mut temp_files = Vec::new();
    let mut all_symbols = Vec::new();

    for _ in 0..FILE_COUNT {
        let content = generate_rust_test_file(LINES_PER_FILE);

        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let path = file.path().to_path_buf();

        let symbols = extract_symbols(&path, "rust").unwrap();
        all_symbols.extend(symbols);
        temp_files.push(file);
    }

    let elapsed = start.elapsed();

    // Verify we extracted a reasonable number of symbols
    assert!(!all_symbols.is_empty(), "Should extract symbols");

    // Performance assertion: should process 50 files with 500 lines each in under 2 seconds
    // This is generous to account for slower CI environments
    let max_duration = std::time::Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Rust symbol extraction took {:.2}s, expected < 2s for {} files x {} lines",
        elapsed.as_secs_f64(),
        FILE_COUNT,
        LINES_PER_FILE
    );

    println!(
        "Rust symbol extraction: {} files x {} lines = {:.2}ms ({} symbols extracted)",
        FILE_COUNT,
        LINES_PER_FILE,
        elapsed.as_secs_f64() * 1000.0,
        all_symbols.len()
    );
}

/// Benchmark test for Python symbol extraction.
#[test]
fn test_python_symbol_extraction_performance() {
    const FILE_COUNT: usize = 50;
    const LINES_PER_FILE: usize = 500;

    let start = std::time::Instant::now();

    // Create and process multiple test files
    let mut temp_files = Vec::new();
    let mut all_symbols = Vec::new();

    for _ in 0..FILE_COUNT {
        let content = generate_python_test_file(LINES_PER_FILE);

        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let path = file.path().to_path_buf();

        let symbols = extract_symbols(&path, "python").unwrap();
        all_symbols.extend(symbols);
        temp_files.push(file);
    }

    let elapsed = start.elapsed();

    // Verify we extracted a reasonable number of symbols
    assert!(!all_symbols.is_empty(), "Should extract symbols");

    // Performance assertion
    let max_duration = std::time::Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Python symbol extraction took {:.2}s, expected < 2s",
        elapsed.as_secs_f64()
    );

    println!(
        "Python symbol extraction: {} files x {} lines = {:.2}ms ({} symbols extracted)",
        FILE_COUNT,
        LINES_PER_FILE,
        elapsed.as_secs_f64() * 1000.0,
        all_symbols.len()
    );
}

/// Benchmark test for SymbolIndex search performance.
#[test]
fn test_symbol_index_search_performance() {
    const SYMBOL_COUNT: usize = 5000;

    let mut index = SymbolIndex::new();

    // Add many symbols to the index
    for i in 0..SYMBOL_COUNT {
        index.add_symbols(
            &format!("crate_{}", i % 10),
            &[ExternalSymbol {
                name: format!("SymbolName{}", i),
                kind: if i % 5 == 0 {
                    SymbolKind::Struct
                } else if i % 5 == 1 {
                    SymbolKind::Function
                } else if i % 5 == 2 {
                    SymbolKind::Enum
                } else {
                    SymbolKind::Trait
                },
                file: PathBuf::from(format!("file_{}.rs", i % 100)),
                line: i,
                crate_name: format!("crate_{}", i % 10),
            }],
        );
    }

    // Benchmark search
    let start = std::time::Instant::now();
    for _ in 0..100 {
        let results = index.search("SymbolName", 50);
        assert!(!results.is_empty());
    }
    let elapsed = start.elapsed();

    // Should complete 100 searches quickly
    let max_duration = std::time::Duration::from_millis(500);
    assert!(
        elapsed < max_duration,
        "Symbol search took {:.2}ms for {} symbols, expected < 500ms",
        elapsed.as_secs_f64() * 1000.0,
        SYMBOL_COUNT
    );

    println!(
        "Symbol index search: {} symbols, 100 searches = {:.2}ms",
        SYMBOL_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for mixed Rust/Python symbol extraction.
#[test]
fn test_mixed_symbol_extraction_performance() {
    const TOTAL_FILES: usize = 100; // 50 Rust + 50 Python

    let start = std::time::Instant::now();

    let mut all_symbols = Vec::new();

    // Process Rust files
    for _ in 0..(TOTAL_FILES / 2) {
        let content = generate_rust_test_file(250);
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let symbols = extract_symbols(&file.path().to_path_buf(), "rust").unwrap();
        all_symbols.extend(symbols);
    }

    // Process Python files
    for _ in 0..(TOTAL_FILES / 2) {
        let content = generate_python_test_file(250);
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(content.as_bytes()).unwrap();
        let symbols = extract_symbols(&file.path().to_path_buf(), "python").unwrap();
        all_symbols.extend(symbols);
    }

    let elapsed = start.elapsed();

    // Performance assertion
    let max_duration = std::time::Duration::from_secs(3);
    assert!(
        elapsed < max_duration,
        "Mixed symbol extraction took {:.2}s, expected < 3s",
        elapsed.as_secs_f64()
    );

    println!(
        "Mixed symbol extraction: {} files = {:.2}ms ({} symbols)",
        TOTAL_FILES,
        elapsed.as_secs_f64() * 1000.0,
        all_symbols.len()
    );
}
