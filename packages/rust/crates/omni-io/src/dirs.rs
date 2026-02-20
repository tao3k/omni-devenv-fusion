//! Project Directory Standards (`PRJ_SPEC`) for Rust
//!
//! Matches `python/foundation/src/omni/foundation/config/dirs.py`
//!
//! This module provides a way to resolve project directories based on
//! environment variables set by the Python Agent Bootstrap layer.

use std::env;
use std::path::PathBuf;
use std::sync::OnceLock;

/// Cache for resolved directories to avoid repeated env lookups
static CONFIG_HOME: OnceLock<PathBuf> = OnceLock::new();
static DATA_HOME: OnceLock<PathBuf> = OnceLock::new();
static CACHE_HOME: OnceLock<PathBuf> = OnceLock::new();
static RUNTIME_DIR: OnceLock<PathBuf> = OnceLock::new();
static PROJECT_ROOT: OnceLock<PathBuf> = OnceLock::new();

/// Project Directory Resolver (`PRJ_SPEC` Compliant)
///
/// This struct provides methods to resolve project-standard directories.
/// It respects environment variables set by the Python Agent Bootstrap layer,
/// ensuring cross-language configuration consistency.
#[derive(Debug, Clone)]
pub struct PrjDirs;

impl PrjDirs {
    /// Get `PRJ_CONFIG_HOME` - Configuration directory
    ///
    /// Default: `.config` (relative to project root)
    #[inline]
    pub fn config_home() -> PathBuf {
        CONFIG_HOME
            .get_or_init(|| resolve_dir("PRJ_CONFIG_HOME", ".config"))
            .clone()
    }

    /// Get `PRJ_DATA_HOME` - Data directory
    ///
    /// Default: `.data` (relative to project root)
    #[inline]
    pub fn data_home() -> PathBuf {
        DATA_HOME
            .get_or_init(|| resolve_dir("PRJ_DATA_HOME", ".data"))
            .clone()
    }

    /// Get `PRJ_CACHE_HOME` - Cache directory
    ///
    /// Default: `.cache` (relative to project root)
    #[inline]
    pub fn cache_home() -> PathBuf {
        CACHE_HOME
            .get_or_init(|| resolve_dir("PRJ_CACHE_HOME", ".cache"))
            .clone()
    }

    /// Get `PRJ_RUNTIME_DIR` - Runtime directory
    ///
    /// Default: `.run` (relative to project root)
    #[inline]
    pub fn runtime_dir() -> PathBuf {
        RUNTIME_DIR
            .get_or_init(|| resolve_dir("PRJ_RUNTIME_DIR", ".run"))
            .clone()
    }

    /// Get `PRJ_ROOT` - Project Root Directory
    ///
    /// Used as the anchor for relative path resolution.
    /// Falls back to current working directory if not set.
    #[inline]
    pub fn project_root() -> PathBuf {
        PROJECT_ROOT
            .get_or_init(|| {
                env::var("PRJ_ROOT").map_or_else(
                    |_| env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
                    PathBuf::from,
                )
            })
            .clone()
    }
}

/// Resolve a directory path
///
/// Logic:
/// 1. Read environment variable
/// 2. If absolute, return as-is
/// 3. If relative, anchor to project root
fn resolve_dir(env_key: &str, default: &str) -> PathBuf {
    let val = env::var(env_key).unwrap_or_else(|_| default.to_string());
    let path = PathBuf::from(val);

    if path.is_absolute() {
        return path;
    }

    let root = env::var("PRJ_ROOT").map_or_else(
        |_| env::current_dir().unwrap_or_else(|_| PathBuf::from(".")),
        PathBuf::from,
    );

    root.join(path)
}

/// Get config home as a String (convenience for FFI)
#[inline]
#[must_use]
pub fn get_config_home() -> String {
    PrjDirs::config_home().to_string_lossy().to_string()
}

/// Get data home as a String (convenience for FFI)
#[inline]
#[must_use]
pub fn get_data_home() -> String {
    PrjDirs::data_home().to_string_lossy().to_string()
}

/// Get cache home as a String (convenience for FFI)
#[inline]
#[must_use]
pub fn get_cache_home() -> String {
    PrjDirs::cache_home().to_string_lossy().to_string()
}

// Note: Unit tests for this module are in Python (test_rust_bridge_config.py)
// to avoid unsafe code in Rust tests while ensuring cross-language compatibility.
