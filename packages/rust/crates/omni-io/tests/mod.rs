//! Tests for omni-io crate.
//!
//! Integration tests for safe file I/O operations.

#[cfg(feature = "assembler")]
pub mod test_assembler;
pub mod test_async;
pub mod test_detect;
pub mod test_sync;
