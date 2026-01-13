#![allow(clippy::doc_markdown)]

//! omni-io - Safe and efficient file I/O for Omni DevEnv
//!
//! A high-performance file reading library with safety features.
//!
//! # Features
//!
//! - **Dual API**: Sync (std::fs) for Python bindings, Async (tokio::fs) for Rust core
//! - **Safety**: Binary detection & Size limits
//! - **Lightweight**: Zero-dependency UTF-8 fallback
//!
//! # Architecture (ODF-REP Compliant)
//!
//! ```text
//! omni-io/src/
//! ├── lib.rs      # Re-exports (this file)
//! ├── error.rs    # IoError enum
//! ├── detect.rs   # Binary detection & decoding
//! ├── sync.rs     # Synchronous API
//! └── async_io.rs # Asynchronous API (Tokio)
//! ```
//!
//! # Example
//!
//! ```rust,ignore
//! use omni_io::{read_text_safe, read_text_safe_async, IoError};
//!
//! // Synchronous (for Python bindings)
//! let content = read_text_safe("file.txt", 1024 * 1024)?;
//!
//! // Asynchronous (for Rust core)
//! let content = read_text_safe_async("file.txt", 1024 * 1024).await?;
//! ```

// ============================================================================
// Module Declarations (ODF-REP: Atomic Structure)
// ============================================================================

mod async_io;
mod detect;
mod error;
mod sync;

// ============================================================================
// Public Re-exports
// ============================================================================

pub use async_io::read_text_safe_async;
pub use error::IoError;
pub use sync::read_text_safe;

// Re-export detection utilities for advanced use
pub use detect::{decode_buffer, is_binary};
