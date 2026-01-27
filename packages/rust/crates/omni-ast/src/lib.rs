//! omni-ast - Unified AST Utilities using ast-grep
//!
//! This crate provides a unified interface for AST-based code analysis
//! across the Omni DevEnv project.
//!
//! ## Architecture
//!
//! ```text
//! omni-ast/src/
//! ├── lib.rs           # Re-exports (entry point)
//! ├── re_exports.rs    # ast-grep re-exports
//! ├── lang.rs          # Lang enum and language support
//! ├── match.rs         # Match struct
//! ├── scan.rs          # Pattern utilities
//! └── python.rs        # Python-specific utilities
//! ```
//!
//! ## Quick Start
//!
//! ```rust
//! use omni_ast::{scan, Lang};
//!
//! let content = "def hello(): pass";
//! let matches = scan(content, "def $NAME", Lang::Python).unwrap();
//! ```

// ============================================================================
// Module Declarations
// ============================================================================

mod item;
mod lang;
mod python;
mod re_exports;
mod scan;
mod security;

// ============================================================================
// Re-exports (for backwards compatibility)
// ============================================================================

// Re-exports module
pub use re_exports::*;

// Lang enum
pub use lang::Lang;

// Match struct
pub use item::Match;

// Scan functions (both direct and re-exported from scan module)
pub use scan::{extract, pattern, scan};

// Python utilities
pub use python::{
    extract_docstring_from_match, extract_python_docstring, find_python_async_functions,
    find_python_classes, find_python_decorated_by_any, find_python_decorated_functions,
    find_python_functions,
};

// Security scanner for harvested skills
pub use security::{SecurityConfig, SecurityScanner, SecurityViolation};
