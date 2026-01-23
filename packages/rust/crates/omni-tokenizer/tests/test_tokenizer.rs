//! Tests for tokenizer module - token counting.

use omni_tokenizer::{count_tokens, count_tokens_with_model, truncate};

#[test]
fn test_count_tokens_simple() {
    let text = "Hello, world! This is a test.";
    let count = count_tokens(text);
    assert!(count > 0);
}

#[test]
fn test_truncate_short() {
    let text = "Hello, world! This is a test.";
    let truncated = truncate(text, 5);
    assert!(!truncated.is_empty());
}

#[test]
fn test_truncate_no_op() {
    let text = "Hello";
    let truncated = truncate(text, 100);
    assert_eq!(truncated, "Hello");
}

#[test]
fn test_count_tokens_with_model() {
    let result = count_tokens_with_model("Hello, world!", "cl100k_base");
    assert!(result.is_ok());
    assert!(result.unwrap() > 0);
}
