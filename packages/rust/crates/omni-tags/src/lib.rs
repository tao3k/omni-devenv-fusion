#![allow(clippy::doc_markdown)]

//! omni-tags - High-Performance Code Symbol Extraction for Omni DevEnv
//!
//! Features:
//! - AST-based symbol extraction using omni-ast (ast-grep)
//! - Syntax-aware matching for Python, Rust, JavaScript, TypeScript
//! - CCA-aligned: Generate outlines to reduce token consumption 10-50x
//!
//! Part of Phase 50: The Cartographer (CCA-Aligned Code Navigation)
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-tags/src/
//! ├── lib.rs      # Re-exports (this file)
//! ├── error.rs    # TagError, SearchError
//! ├── types.rs    # SymbolKind, Symbol, SearchMatch, SearchConfig
//! ├── patterns.rs # ast-grep pattern constants
//! └── extractor.rs # TagExtractor with all methods
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_tags::TagExtractor;
//!
//! let outline = TagExtractor::outline_file("src/main.py", Some("python"))?;
//! println!("{}", outline);
//! ```

// ============================================================================
// Module Declarations (ODF-REP: Atomic Structure)
// ============================================================================

mod error;
mod extractor;
mod patterns;
mod types;

// ============================================================================
// Public Re-exports
// ============================================================================

pub use error::{SearchError, TagError};
pub use extractor::TagExtractor;
pub use patterns::{
    JS_CLASS_PATTERN, JS_FN_PATTERN, PYTHON_ASYNC_DEF_PATTERN, PYTHON_CLASS_PATTERN,
    PYTHON_DEF_PATTERN, RUST_ENUM_PATTERN, RUST_FN_PATTERN, RUST_IMPL_PATTERN, RUST_STRUCT_PATTERN,
    RUST_TRAIT_PATTERN, TS_INTERFACE_PATTERN,
};
pub use types::{SearchConfig, SearchMatch, SearchResult, Symbol, SymbolKind};
