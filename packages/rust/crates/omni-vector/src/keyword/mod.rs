//! keyword.rs - Tantivy-based Keyword Index for BM25/Sparse Retrieval
//!
//! This module provides high-performance keyword search using Tantivy (Rust Lucene).
//! Features:
//! - BM25 scoring
//! - Simple tokenization with code-specific filtering (snake_case, camelCase)
//! - RRF fusion with vector search results
//! - Robust initialization (avoids destructive recreation)

pub mod fusion;
pub mod index;

pub use fusion::{HybridSearchResult, apply_adaptive_rrf, apply_rrf, apply_weighted_rrf};
pub use index::KeywordIndex;

/// Default RRF k parameter for high precision (Code Search)
/// Based on MariaDB Engineering (2025): k=10 is optimal for precision-critical scenarios
pub const RRF_K: f32 = 10.0;

/// Semantic weight for hybrid search (vector contribution)
pub const SEMANTIC_WEIGHT: f32 = 1.0;

/// Keyword weight for hybrid search (BM25 contribution)
/// Keywords are precise anchors for code/tools, so we weight them higher
pub const KEYWORD_WEIGHT: f32 = 1.5;

/// Boost per token match in tool name (BM25F-inspired field boosting)
/// Increased from 0.2 to 0.5 for "brute force" keyword matching effect
pub const NAME_TOKEN_BOOST: f32 = 0.5;

/// Boost for exact phrase match in tool name
/// Increased from 0.5 to 1.5 to make full matches decisive
pub const EXACT_PHRASE_BOOST: f32 = 1.5;
