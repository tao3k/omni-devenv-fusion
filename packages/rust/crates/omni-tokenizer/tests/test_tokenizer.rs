//! Tests for tokenizer module - token counting and chunking.

use omni_tokenizer::{chunk_text, count_tokens, count_tokens_with_model, truncate};

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
    assert!(result.is_ok_and(|v| v > 0));
}

#[test]
fn test_chunk_text_empty() {
    let out = chunk_text("", 512, 50);
    assert!(out.is_empty());
}

#[test]
fn test_chunk_text_short_returns_single_chunk() {
    let text = "Short document.";
    let out = chunk_text(text, 512, 50);
    assert_eq!(out.len(), 1);
    assert_eq!(out[0].0, text);
    assert_eq!(out[0].1, 0);
}

#[test]
fn test_chunk_text_multiple_chunks_indices_contiguous() {
    let words: Vec<String> = (0..200).map(|i| format!("word{i} ")).collect();
    let text = words.join("");
    let out = chunk_text(&text, 50, 10);
    assert!(out.len() > 1, "expected multiple chunks");
    for (i, (_, idx)) in out.iter().enumerate() {
        assert_eq!(*idx, i as u32, "chunk_index should be contiguous from 0");
    }
}
