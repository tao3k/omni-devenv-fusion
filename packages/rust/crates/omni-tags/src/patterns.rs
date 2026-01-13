//! ast-grep patterns for different languages.
//!
//! Centralized pattern definitions for symbol extraction.

/// Python patterns
pub const PYTHON_CLASS_PATTERN: &str = "class $NAME";
pub const PYTHON_DEF_PATTERN: &str = "def $NAME";
pub const PYTHON_ASYNC_DEF_PATTERN: &str = "async def $NAME";

/// Rust patterns
/// struct requires pub, but impl/trait/enum don't
pub const RUST_STRUCT_PATTERN: &str = "pub struct $NAME";
pub const RUST_FN_PATTERN: &str = "pub fn $NAME";
pub const RUST_ENUM_PATTERN: &str = "enum $NAME";
pub const RUST_TRAIT_PATTERN: &str = "trait $NAME";
pub const RUST_IMPL_PATTERN: &str = "impl $NAME";

/// JavaScript patterns
pub const JS_CLASS_PATTERN: &str = "class $NAME";
pub const JS_FN_PATTERN: &str = "function $NAME";

/// TypeScript patterns
pub const TS_INTERFACE_PATTERN: &str = "interface $NAME";
