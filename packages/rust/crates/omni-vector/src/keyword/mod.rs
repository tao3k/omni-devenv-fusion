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

/// Boost for exact token match in tool name (e.g., "commit" in "git.commit")
/// This is in RRF score space (~0.1 per rank), so boost should be small
pub const NAME_TOKEN_BOOST: f32 = 0.3;
/// Boost for exact phrase match in tool name
pub const EXACT_PHRASE_BOOST: f32 = 0.5;
