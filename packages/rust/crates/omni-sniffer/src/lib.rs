//! High-performance environment sniffer for Omni `DevEnv`.
//!
//! Uses libgit2 for fast git operations and provides environment snapshots.
//! The `glob_engine` module provides Rust-Native Cortex for high-performance
//! context detection using `GlobSet` (ripgrep's core).
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-sniffer/src/
//! ├── lib.rs          # Re-exports (this file)
//! ├── error.rs        # SnifferError enum
//! ├── git.rs          # Git status scanning
//! ├── context.rs      # Scratchpad scanning
//! ├── sniffer.rs      # OmniSniffer struct (git/context scanning)
//! └── glob_engine.rs  # High-performance GlobSet sniffer (1600+ rules)
//! ```
//!
//! # Example: High-Performance `GlobSet` Sniffer
//!
//! ```rust,ignore
//! use omni_sniffer::{SnifferEngine, SnifferRule};
//!
//! let rules = vec![
//!     SnifferRule::new("python", vec!["*.py", "pyproject.toml"]),
//!     SnifferRule::new("rust", vec!["*.rs", "Cargo.toml"]),
//! ];
//!
//! let engine = SnifferEngine::new(rules).unwrap();
//! let contexts = engine.sniff_path("/path/to/project", 5);
//! ```

// ============================================================================
// Module Declarations (ODF-REP: Atomic Structure)
// ============================================================================

mod context;
mod error;
mod git;
mod glob_engine;
mod sniffer;

// ============================================================================
// Public Re-exports
// ============================================================================

pub use context::scan_scratchpad_context;
pub use error::SnifferError;
pub use git::scan_git_status;
pub use glob_engine::{SnifferEngine, SnifferRule};
pub use sniffer::OmniSniffer;
