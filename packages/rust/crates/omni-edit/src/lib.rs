#![allow(clippy::doc_markdown)]

//! omni-edit - Structural Code Refactoring for Omni DevEnv
//!
//! A high-performance AST-based code modification library using ast-grep.
//! Part of Phase 52: The Surgeon (CCA-Aligned Code Modification).
//!
//! # Features
//!
//! - **Structural Replace**: Modify code patterns without touching unrelated code
//! - **Diff Preview**: Generate unified diffs before applying changes
//! - **Multi-language**: Python, Rust, JavaScript, TypeScript support
//! - **Capture Substitution**: Use `$NAME` and `$$$` patterns
//!
//! # Architecture (ODF-REP Compliant)
//!
//! This crate follows the ODF-REP atomic module structure:
//!
//! ```text
//! omni-edit/src/
//! ├── lib.rs      # Re-exports (this file)
//! ├── error.rs    # EditError enum (thiserror)
//! ├── types.rs    # EditResult, EditLocation, EditConfig
//! ├── diff.rs     # Diff generation utilities
//! ├── capture.rs  # Variable capture substitution
//! └── editor.rs   # StructuralEditor implementation
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_edit::StructuralEditor;
//!
//! // Rename function calls (use $$$ for variadic args)
//! let result = StructuralEditor::replace(
//!     "x = connect(host, port)",
//!     "connect($$$)",
//!     "async_connect($$$)",
//!     "python"
//! )?;
//!
//! println!("Modified: {}", result.modified);
//! println!("Diff:\n{}", result.diff);
//! ```

// ============================================================================
// Module Declarations (ODF-REP: Atomic Structure)
// ============================================================================

mod capture;
mod diff;
mod editor;
mod error;
mod types;

// ============================================================================
// Public Re-exports
// ============================================================================

pub use editor::StructuralEditor;
pub use error::EditError;
pub use types::{EditConfig, EditLocation, EditResult};

// Re-export diff utility for external use
pub use diff::generate_unified_diff;
