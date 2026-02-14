//! Shared types for RRF fusion.

/// Result type for hybrid search combining vector and keyword scores.
#[derive(Debug, Clone)]
pub struct HybridSearchResult {
    /// Full tool name (e.g., "git.commit")
    pub tool_name: String,
    /// Final combined RRF score after fusion
    pub rrf_score: f32,
    /// Raw vector similarity score from semantic search
    pub vector_score: f32,
    /// BM25 keyword score from keyword search
    pub keyword_score: f32,
}
