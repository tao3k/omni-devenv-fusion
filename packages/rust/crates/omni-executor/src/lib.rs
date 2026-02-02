//! omni-executor - Nushell Native Bridge for Agentic OS
//!
//! Provides secure, structured execution of Nushell commands:
//! - Security layer for mutation commands
//! - Forced JSON output transformation
//! - Structured error handling
//! - AST-based semantic analysis
//! - Safe query building

mod ast_analyzer;
mod error;
mod nu_bridge;
mod query;

pub use ast_analyzer::{
    AstCommandAnalyzer, CommandAnalysis, SecurityViolation, VariableInfo, ViolationSeverity,
};
pub use error::{ExecutorError, Result};
pub use nu_bridge::{ActionType, NuConfig, NuSystemBridge};
pub use query::{QueryAction, QueryBuilder};
