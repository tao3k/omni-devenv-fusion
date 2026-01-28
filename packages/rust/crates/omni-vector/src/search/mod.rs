//! Search operations for the vector store.
//!
//! This module provides search functionality:
//! - Pure vector search using LanceDB
//! - Hybrid search combining vector similarity with keyword search (Tantivy BM25)
//! - Filter matching and keyword boost logic
//!
//! # Modules
//!
//! - [`vector_search`] - Pure vector nearest neighbor search
//! - [`hybrid_search`] - Hybrid search with RRF fusion
//! - [`filter`] - Metadata filtering and keyword boosting

pub mod filter;
pub mod hybrid_search;
pub mod vector_search;
