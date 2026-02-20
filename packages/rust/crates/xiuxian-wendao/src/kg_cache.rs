//! In-process cache for KnowledgeGraph loaded from Lance.
#![allow(clippy::doc_markdown)]
//!
//! Avoids repeated disk reads when the same knowledge.lance path is accessed
//! across multiple recall operations. Cache is invalidated on save so ingest
//! updates are visible.

use crate::graph::{GraphError, KnowledgeGraph};
use log::debug;
use std::collections::HashMap;
use std::path::Path;
use std::sync::{LazyLock, Mutex};

static KG_CACHE: LazyLock<Mutex<HashMap<String, KnowledgeGraph>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// Normalize path for cache key (trim trailing slash, resolve to absolute when possible).
fn normalize_path(path: &str) -> String {
    let trimmed = path.trim_end_matches('/');
    Path::new(trimmed).canonicalize().map_or_else(
        |_| trimmed.to_string(),
        |p| p.to_string_lossy().into_owned(),
    )
}

/// Load KnowledgeGraph from Lance, using cache when available.
///
/// On cache hit, returns a clone of the cached graph (cheap: Arc clones).
/// On cache miss, loads from disk, inserts into cache, returns clone.
/// Returns None if tables don't exist (graceful fallback).
///
/// # Errors
///
/// Returns [`GraphError::InvalidRelation`] when lock or runtime initialization fails.
pub fn load_from_lance_cached(lance_dir: &str) -> Result<Option<KnowledgeGraph>, GraphError> {
    let key = normalize_path(lance_dir);

    // Check cache first
    {
        let cache = KG_CACHE
            .lock()
            .map_err(|e| GraphError::InvalidRelation("cache_lock".into(), e.to_string()))?;
        if let Some(cached) = cache.get(&key) {
            debug!("KG cache hit for path: {key}");
            return Ok(Some(cached.clone()));
        }
    }

    // Cache miss: load from disk
    let graph = load_from_lance_impl(lance_dir)?;
    let result = if graph.get_stats().total_entities == 0 && graph.get_stats().total_relations == 0
    {
        // Empty graph (tables don't exist yet) - don't cache, return as-is
        Some(graph)
    } else {
        let cloned = graph.clone();
        {
            let mut cache = KG_CACHE
                .lock()
                .map_err(|e| GraphError::InvalidRelation("cache_lock".into(), e.to_string()))?;
            cache.insert(key.clone(), graph);
            debug!(
                "KG cache insert for path: {key} ({} entities, {} relations)",
                cloned.get_stats().total_entities,
                cloned.get_stats().total_relations
            );
        }
        Some(cloned)
    };

    Ok(result)
}

/// Internal: load graph from Lance (no cache). Used by load_from_lance_cached.
fn load_from_lance_impl(lance_dir: &str) -> Result<KnowledgeGraph, GraphError> {
    let runtime = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .map_err(|e| GraphError::InvalidRelation("runtime".into(), e.to_string()))?;

    #[allow(unused_mut)]
    let mut graph = KnowledgeGraph::new();
    runtime.block_on(graph.load_from_lance(lance_dir))?;
    Ok(graph)
}

/// Invalidate the cache for the given path (call after save_to_lance).
pub fn invalidate(lance_dir: &str) {
    let key = normalize_path(lance_dir);
    if let Ok(mut cache) = KG_CACHE.lock()
        && cache.remove(&key).is_some()
    {
        debug!("KG cache invalidated for path: {key}");
    }
}

/// Invalidate all cached graphs (for testing or full reset).
#[allow(dead_code)]
pub fn invalidate_all() {
    if let Ok(mut cache) = KG_CACHE.lock() {
        let count = cache.len();
        cache.clear();
        if count > 0 {
            debug!("KG cache cleared: {count} entries");
        }
    }
}

/// Return the number of cached entries (for testing).
#[allow(dead_code)]
#[must_use]
pub fn cache_len() -> usize {
    KG_CACHE.lock().map_or(0, |c| c.len())
}
