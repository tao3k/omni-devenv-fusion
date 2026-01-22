#![allow(clippy::doc_markdown)]

//! omni-edit - Structural Code Refactoring for Omni DevEnv
//!
//! A high-performance AST-based code modification library using ast-grep.
//! Part of The Surgeon (CCA-Aligned Code Modification).
//! The Ouroboros - Heavy-duty parallel batch refactoring.
//!
//! # Features
//!
//! - **Structural Replace**: Modify code patterns without touching unrelated code
//! - **Diff Preview**: Generate unified diffs before applying changes
//! - **Multi-language**: Python, Rust, JavaScript, TypeScript support
//! - **Capture Substitution**: Use `$NAME` and `$$$` patterns
//! - **Batch Refactoring**: Parallel processing across entire codebases (The Ouroboros)
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-edit/src/
//! ├── lib.rs      # Re-exports (this file)
//! ├── error.rs    # EditError enum (thiserror)
//! ├── types.rs    # EditResult, EditLocation, EditConfig
//! ├── diff.rs     # Diff generation utilities
//! ├── capture.rs  # Variable capture substitution
//! ├── editor.rs   # StructuralEditor implementation
//! └── batch.rs    # Batch refactoring with rayon (The Ouroboros)
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_edit::StructuralEditor;
//!
//! // Single file refactoring
//! let result = StructuralEditor::replace(
//!     "x = connect(host, port)",
//!     "connect($$$)",
//!     "async_connect($$$)",
//!     "python"
//! )?;
//!
//! // Batch refactoring across codebase (The Ouroboros)
//! let stats = StructuralEditor::batch_replace(
//!     "/project",
//!     "print($ARGS)",
//!     "logger.info($ARGS)",
//!     BatchConfig {
//!         file_pattern: "**/*.py".to_string(),
//!         dry_run: true,
//!         ..Default::default()
//!     }
//! );
//! ```

// ============================================================================
// Module Declarations (ODF-REP: Atomic Structure)
// ============================================================================

mod batch;
mod capture;
mod diff;
mod editor;
mod error;
mod types; // Heavy-duty batch refactoring

// ============================================================================
// Public Re-exports
// ============================================================================

pub use editor::StructuralEditor;
pub use error::EditError;
pub use types::{EditConfig, EditLocation, EditResult};

// Batch refactoring exports
pub use batch::{BatchConfig, BatchRefactorStats};

// Re-export diff utility for external use
pub use diff::generate_unified_diff;
