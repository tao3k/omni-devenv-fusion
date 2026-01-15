//! ast-grep patterns for different languages.
//!
//! Centralized pattern definitions for symbol extraction.

/// Python class pattern: `class $NAME`
pub const PYTHON_CLASS_PATTERN: &str = "class $NAME";
/// Python function pattern: `def $NAME`
pub const PYTHON_DEF_PATTERN: &str = "def $NAME";
/// Python async function pattern: `async def $NAME`
pub const PYTHON_ASYNC_DEF_PATTERN: &str = "async def $NAME";

/// Rust patterns
/// struct requires pub, but impl/trait/enum don't
/// Rust public function pattern: `pub fn $NAME`
pub const RUST_STRUCT_PATTERN: &str = "pub struct $NAME";
/// Rust function pattern: `pub fn $NAME`
pub const RUST_FN_PATTERN: &str = "pub fn $NAME";
/// Rust enum pattern: `enum $NAME`
pub const RUST_ENUM_PATTERN: &str = "enum $NAME";
/// Rust trait pattern: `trait $NAME`
pub const RUST_TRAIT_PATTERN: &str = "trait $NAME";
/// Rust impl pattern: `impl $NAME`
pub const RUST_IMPL_PATTERN: &str = "impl $NAME";

/// JavaScript patterns
/// JavaScript class pattern: `class $NAME`
pub const JS_CLASS_PATTERN: &str = "class $NAME";
/// JavaScript function pattern: `function $NAME`
pub const JS_FN_PATTERN: &str = "function $NAME";

/// TypeScript patterns
/// TypeScript interface pattern: `interface $NAME`
pub const TS_INTERFACE_PATTERN: &str = "interface $NAME";
