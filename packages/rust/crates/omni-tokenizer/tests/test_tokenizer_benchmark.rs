//! Benchmark tests for tokenization performance.
//!
//! These tests measure the performance of BPE tokenization using tiktoken.
//! The tokenizer uses `OnceLock` caching for optimal performance.

use std::fmt::Write as _;
use std::time::Duration;

/// Generate test text of a given size.
fn generate_test_text(char_count: usize) -> String {
    let words = [
        "hello",
        "world",
        "rust",
        "python",
        "tokenizer",
        "benchmark",
        "performance",
        "optimization",
        "vector",
        "search",
        "database",
        "async",
        "await",
        "parallel",
        "concurrent",
        "memory",
        "cpu",
        "function",
        "class",
        "struct",
        "enum",
        "trait",
        "interface",
    ];

    let mut result = String::with_capacity(char_count);
    let word_count = char_count / 6; // Average word length ~6

    for i in 0..word_count {
        if i > 0 && i % 10 == 0 {
            result.push('\n');
        } else if i > 0 {
            result.push(' ');
        }
        result.push_str(words[i % words.len()]);
    }

    result
}

/// Generate code-like text for benchmarking.
fn generate_code_text(line_count: usize) -> String {
    let mut content = String::with_capacity(line_count * 50);

    for i in 0..line_count {
        let _ = write!(
            content,
            r#"fn function_{i}(arg1: &str, arg2: i32) -> Result<(), Box<dyn std::error::Error>> {{
    let result = process_data(arg1, arg2)?;
    println!("Result: {{}}", result);
    Ok(())
}}

"#
        );
    }

    content
}

/// Generate JSON-like text for benchmarking.
fn generate_json_text(entry_count: usize) -> String {
    let mut content = String::with_capacity(entry_count * 100);
    content.push_str("[\n");

    for i in 0..entry_count {
        if i > 0 {
            content.push_str(",\n");
        }
        let _ = write!(
            content,
            r#"  {{
    "id": {i},
    "name": "item_{i}",
    "description": "This is a test item with index {i}",
    "tags": ["test", "benchmark", "performance"],
    "value": {i}.5,
    "active": true
}}"#
        );
    }

    content.push_str("\n]\n");
    content
}

/// Benchmark test for token counting performance.
#[test]
fn test_token_counting_performance() {
    const TEXT_SIZE: usize = 10000; // 10KB of text

    let text = generate_test_text(TEXT_SIZE);

    let start = std::time::Instant::now();

    // Count tokens multiple times
    for _ in 0..100 {
        let count = omni_tokenizer::count_tokens(&text);
        assert!(count > 0);
    }

    let elapsed = start.elapsed();

    // Should count 100 times in under 2 seconds
    let max_duration = Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Token counting took {:.2}s for 100 iterations, expected < 2s",
        elapsed.as_secs_f64()
    );

    println!(
        "Token counting: {} chars x 100 iterations = {:.2}ms",
        TEXT_SIZE,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for large text tokenization.
#[test]
fn test_large_text_tokenization() {
    const TEXT_SIZE: usize = 100_000; // 100KB of text

    let text = generate_test_text(TEXT_SIZE);

    let start = std::time::Instant::now();

    let count = omni_tokenizer::count_tokens(&text);

    let elapsed = start.elapsed();

    // Should tokenize 100KB in under 500ms
    let max_duration = Duration::from_millis(500);
    assert!(
        elapsed < max_duration,
        "Large text tokenization took {:.2}ms for {} chars, expected < 500ms",
        elapsed.as_secs_f64() * 1000.0,
        TEXT_SIZE
    );

    println!(
        "Large text tokenization: {} chars = {:.2}ms ({} tokens)",
        TEXT_SIZE,
        elapsed.as_secs_f64() * 1000.0,
        count
    );
}

/// Benchmark test for code tokenization.
#[test]
fn test_code_tokenization_performance() {
    const LINE_COUNT: usize = 100; // Reduced for faster testing

    let code = generate_code_text(LINE_COUNT);

    let start = std::time::Instant::now();

    for _ in 0..10 {
        let count = omni_tokenizer::count_tokens(&code);
        assert!(count > 0);
    }

    let elapsed = start.elapsed();

    // Should tokenize 10 times in under 10 seconds (code is more complex)
    let max_duration = Duration::from_secs(10);
    assert!(
        elapsed < max_duration,
        "Code tokenization took {:.2}s for {} iterations, expected < 10s",
        elapsed.as_secs_f64(),
        10
    );

    println!(
        "Code tokenization: {} lines x 10 iterations = {:.2}ms",
        LINE_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for JSON tokenization.
#[test]
fn test_json_tokenization_performance() {
    const ENTRY_COUNT: usize = 200; // Reduced for faster testing

    let json = generate_json_text(ENTRY_COUNT);

    let start = std::time::Instant::now();

    for _ in 0..10 {
        let count = omni_tokenizer::count_tokens(&json);
        assert!(count > 0);
    }

    let elapsed = start.elapsed();

    // Should tokenize 10 times in under 15 seconds (JSON has many special chars)
    let max_duration = Duration::from_secs(15);
    assert!(
        elapsed < max_duration,
        "JSON tokenization took {:.2}s for 10 iterations, expected < 15s",
        elapsed.as_secs_f64()
    );

    println!(
        "JSON tokenization: {} entries x 10 iterations = {:.2}ms",
        ENTRY_COUNT,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for truncate performance.
#[test]
fn test_truncate_performance() {
    const TEXT_SIZE: usize = 5000;
    const MAX_TOKENS: usize = 100;

    let text = generate_test_text(TEXT_SIZE);

    let start = std::time::Instant::now();

    for _ in 0..100 {
        let truncated = omni_tokenizer::truncate(&text, MAX_TOKENS);
        assert!(!truncated.is_empty());
    }

    let elapsed = start.elapsed();

    // Should truncate 100 times in under 3 seconds
    let max_duration = Duration::from_secs(3);
    assert!(
        elapsed < max_duration,
        "Truncate took {:.2}s for 100 iterations, expected < 3s",
        elapsed.as_secs_f64()
    );

    println!(
        "Truncate: {} chars x 100 iterations = {:.2}ms",
        TEXT_SIZE,
        elapsed.as_secs_f64() * 1000.0
    );
}

/// Benchmark test for batch token counting.
#[test]
fn test_batch_token_counting() {
    const BATCH_SIZE: usize = 100;
    const TEXT_SIZE: usize = 1000;

    let texts: Vec<String> = (0..BATCH_SIZE)
        .map(|_| generate_test_text(TEXT_SIZE))
        .collect();

    let start = std::time::Instant::now();

    let total_tokens: usize = texts.iter().map(|t| omni_tokenizer::count_tokens(t)).sum();

    let elapsed = start.elapsed();

    // Should count tokens for 100 texts in under 2 seconds
    let max_duration = Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "Batch token counting took {:.2}s for {} texts, expected < 2s",
        elapsed.as_secs_f64(),
        BATCH_SIZE
    );

    println!(
        "Batch token counting: {} texts x {} chars = {:.2}ms ({} total tokens)",
        BATCH_SIZE,
        TEXT_SIZE,
        elapsed.as_secs_f64() * 1000.0,
        total_tokens
    );
}

/// Benchmark test for varying text sizes.
#[test]
fn test_varying_text_sizes() {
    let sizes = [100, 1000, 5000, 10000, 50000];

    for size in sizes {
        let text = generate_test_text(size);

        let start = std::time::Instant::now();
        let count = omni_tokenizer::count_tokens(&text);
        let elapsed = start.elapsed();

        println!(
            "Text size {} chars: {:.2}ms ({} tokens)",
            size,
            elapsed.as_secs_f64() * 1000.0,
            count
        );

        // Each size should complete in reasonable time
        let max_duration = Duration::from_millis(500);
        assert!(
            elapsed < max_duration,
            "Tokenization of {} chars took {:.2}ms, expected < 500ms",
            size,
            elapsed.as_secs_f64() * 1000.0
        );
    }
}

/// Verify token counting correctness.
#[test]
fn test_token_counting_correctness() {
    // Simple test cases
    assert_eq!(omni_tokenizer::count_tokens("hello world"), 2);
    assert_eq!(omni_tokenizer::count_tokens("hello"), 1);
    assert_eq!(omni_tokenizer::count_tokens(""), 0);

    // Code-like text
    let code = generate_code_text(10);
    let count = omni_tokenizer::count_tokens(&code);
    assert!(count > 0, "Should count some tokens in code");

    // Verify truncate reduces token count
    let text = generate_test_text(5000);
    let truncated = omni_tokenizer::truncate(&text, 50);
    let truncated_count = omni_tokenizer::count_tokens(&truncated);
    assert!(
        truncated_count <= 50,
        "Truncated text should have <= 50 tokens, got {truncated_count}"
    );
}

/// Test `TokenCounter` wrapper.
#[test]
fn test_token_counter_wrapper() {
    let text = generate_test_text(1000);

    let start = std::time::Instant::now();

    for _ in 0..100 {
        let count = omni_tokenizer::TokenCounter::count_tokens(&text);
        assert!(count > 0);
    }

    let elapsed = start.elapsed();

    // Should complete in under 2 seconds
    let max_duration = Duration::from_secs(2);
    assert!(
        elapsed < max_duration,
        "TokenCounter wrapper took {:.2}s",
        elapsed.as_secs_f64()
    );

    println!(
        "TokenCounter wrapper: {:.2}ms",
        elapsed.as_secs_f64() * 1000.0
    );
}
