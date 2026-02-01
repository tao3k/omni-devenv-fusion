//! Re-exports from ast-grep (Unified ast-grep v0.40.5)
//!
//! This module provides unified access to ast-grep-core and ast-grep-language
//! types, ensuring consistent version usage across the project.

// ============================================================================
// Re-exports (Unified ast-grep version)
// ============================================================================

// Core pattern matching
pub use ast_grep_config::{DeserializeEnv, RuleCore, SerializableRuleCore};
pub use ast_grep_core::Doc;
pub use ast_grep_core::Language as AstLanguage;
pub use ast_grep_core::Pattern;
pub use ast_grep_core::matcher::MatcherExt;
pub use ast_grep_core::matcher::NodeMatch;

// Language support
pub use ast_grep_language::LanguageExt;
pub use ast_grep_language::SupportLang;

// Meta variable handling
pub use ast_grep_core::meta_var::MetaVarEnv;
pub use ast_grep_core::meta_var::MetaVariable;

// ============================================================================
// AST Document & Parsing (for semantic analysis)
// ============================================================================

// String document (for parsing shell commands)
pub use ast_grep_core::tree_sitter::StrDoc;

// Tree traversal utilities
pub use ast_grep_core::tree_sitter::TsPre;
pub use ast_grep_core::tree_sitter::Visitor;

/// Type alias for language parser (re-exported from ast-grep).
pub type LangParser = SupportLang;
