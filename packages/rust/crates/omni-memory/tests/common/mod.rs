//! Shared test helpers for omni-memory.
//!
//! Store paths go under PRJ_CACHE_HOME/omni-memory per project conventions.

/// Path for test store under PRJ_CACHE/omni-memory.
///
/// Uses a unique suffix per call for parallel test isolation.
pub fn test_store_path(name: &str) -> String {
    let cache = omni_io::PrjDirs::cache_home();
    let base = cache.join("omni-memory").join(name);
    let unique = uuid::Uuid::new_v4();
    base.join(unique.to_string()).to_string_lossy().to_string()
}
