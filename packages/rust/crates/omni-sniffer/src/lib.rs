#![allow(clippy::doc_markdown, clippy::uninlined_format_args)]

//! High-performance environment sniffer for Omni DevEnv.
//!
//! Uses libgit2 for fast git operations and provides environment snapshots.
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-sniffer/src/
//! ├── lib.rs      # Re-exports (this file)
//! ├── error.rs    # SnifferError enum
//! ├── git.rs      # Git status scanning
//! ├── context.rs  # Scratchpad scanning
//! └── sniffer.rs  # OmniSniffer struct
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_sniffer::{OmniSniffer, SnifferError};
//!
//! let sniffer = OmniSniffer::new(".")?;
//! let snapshot = sniffer.get_snapshot();
//! ```

// ============================================================================
// Module Declarations (ODF-REP: Atomic Structure)
// ============================================================================

mod context;
mod error;
mod git;
mod sniffer;

// ============================================================================
// Public Re-exports
// ============================================================================

pub use context::scan_scratchpad_context;
pub use error::SnifferError;
pub use git::scan_git_status;
pub use sniffer::OmniSniffer;
