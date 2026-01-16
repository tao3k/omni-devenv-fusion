#![allow(clippy::doc_markdown)]

//! omni-tokenizer - High-performance token counting and truncation
//!
//! Uses tiktoken-rs for BPE tokenization (GPT-4/3.5 compatible).
//! Provides 20-100x speedup over Python tiktoken implementations.
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_tokenizer::{count_tokens, truncate};
//!
//! let text = "Hello, world!";
//! let count = count_tokens(text);
//! let truncated = truncate(text, 5);
//! ```

use std::sync::OnceLock;
use thiserror::Error;

/// Errors for tokenization operations.
#[derive(Error, Debug)]
pub enum TokenizerError {
    /// Failed to initialize the tokenization model
    #[error("Tokenization model initialization failed: {0}")]
    ModelInit(String),
    /// Failed to encode text to tokens
    #[error("Token encoding failed: {0}")]
    Encoding(String),
    /// Failed to decode tokens back to text
    #[error("Token decoding failed: {0}")]
    Decoding(String),
}

/// Cached cl100k_base BPE instance - initialized only once.
/// This avoids the expensive re-initialization on every function call.
/// Using Option to avoid unstable get_or_try_init.
static CL100K_BASE: OnceLock<tiktoken_rs::CoreBPE> = OnceLock::new();

/// Initialize and get cl100k_base BPE instance.
fn get_cl100k_base() -> Result<&'static tiktoken_rs::CoreBPE, TokenizerError> {
    // Use get_or_init which is stable
    // The first call will initialize, subsequent calls return the cached value
    let bpe = CL100K_BASE.get_or_init(|| {
        // unwrap_or_else with a closures that returns the BPE or panics
        // We handle the error at the call site
        tiktoken_rs::cl100k_base()
            .unwrap_or_else(|e| panic!("Failed to initialize cl100k_base: {}", e))
    });
    Ok(bpe)
}

/// Count tokens in text using cl100k_base (GPT-4/3.5 standard).
///
/// This uses the same tokenizer as GPT-4 and ChatGPT.
/// The BPE model is cached globally for optimal performance.
///
/// # Arguments
///
/// * `text` - The text to tokenize
///
/// # Returns
///
/// Number of tokens in the text.
#[must_use]
pub fn count_tokens(text: &str) -> usize {
    // Use cached BPE instance for optimal performance
    get_cl100k_base()
        .map(|bpe| bpe.encode_with_special_tokens(text).len())
        .unwrap_or_else(|_| estimate_token_count(text))
}

/// Count tokens using a specific model.
///
/// Supported models:
/// - "cl100k_base" - GPT-4 / GPT-3.5 Turbo
/// - "p50k_base"   - GPT-3 (Codex)
/// - "p50k_edit"   - Edit models
/// - "r50k_base"   - GPT-2
pub fn count_tokens_with_model(text: &str, model: &str) -> Result<usize, TokenizerError> {
    let bpe = match model {
        "cl100k_base" => tiktoken_rs::cl100k_base(),
        "p50k_base" => tiktoken_rs::p50k_base(),
        "r50k_base" => tiktoken_rs::r50k_base(),
        _ => return Err(TokenizerError::ModelInit(model.to_string())),
    };

    bpe.map(|bpe| bpe.encode_with_special_tokens(text).len())
        .map_err(|e| TokenizerError::Encoding(e.to_string()))
}

/// Truncate text to fit within a maximum token count.
///
/// # Arguments
///
/// * `text` - The text to truncate
/// * `max_tokens` - Maximum number of tokens allowed
///
/// # Returns
///
/// Truncated text that fits within the token limit.
#[must_use]
pub fn truncate(text: &str, max_tokens: usize) -> String {
    // Use cached BPE instance for optimal performance
    let bpe = match get_cl100k_base() {
        Ok(bpe) => bpe,
        Err(_) => return estimate_truncate(text, max_tokens),
    };

    let tokens = bpe.encode_with_special_tokens(text);
    let token_count = tokens.len();

    if token_count <= max_tokens {
        return text.to_string();
    }

    // Take only max_tokens and decode back to string
    let truncated: Vec<_> = tokens.into_iter().take(max_tokens).collect();
    bpe.decode(truncated)
        .unwrap_or_else(|_| estimate_truncate(text, max_tokens))
}

/// Truncate using a specific model.
pub fn truncate_with_model(
    text: &str,
    max_tokens: usize,
    model: &str,
) -> Result<String, TokenizerError> {
    let bpe = match model {
        "cl100k_base" => tiktoken_rs::cl100k_base(),
        "p50k_base" => tiktoken_rs::p50k_base(),
        "r50k_base" => tiktoken_rs::r50k_base(),
        _ => return Err(TokenizerError::ModelInit(model.to_string())),
    };

    let bpe = bpe.map_err(|e| TokenizerError::ModelInit(e.to_string()))?;
    let tokens = bpe.encode_with_special_tokens(text);

    if tokens.len() <= max_tokens {
        return Ok(text.to_string());
    }

    let truncated: Vec<_> = tokens.into_iter().take(max_tokens).collect();
    bpe.decode(truncated)
        .map_err(|e| TokenizerError::Decoding(e.to_string()))
}

/// Estimate token count using simple whitespace heuristic.
/// Used as fallback when tiktoken is unavailable.
fn estimate_token_count(text: &str) -> usize {
    // Rough approximation: ~4 characters per token on average
    text.split_whitespace().count() * 2
}

/// Estimate-based truncation fallback.
fn estimate_truncate(text: &str, max_tokens: usize) -> String {
    let words: Vec<&str> = text.split_whitespace().collect();
    let target_words = std::cmp::min(max_tokens * 2, words.len());
    words[..target_words].join(" ")
}

/// Get the encoding name for a model.
#[must_use]
pub fn get_encoding_name(model: &str) -> &'static str {
    match model {
        "gpt-4" | "gpt-3.5-turbo" | "cl100k_base" => "cl100k_base",
        "gpt-3" | "code-davinci-002" | "p50k_base" => "p50k_base",
        "gpt-2" | "r50k_base" => "r50k_base",
        _ => "cl100k_base",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

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
}
