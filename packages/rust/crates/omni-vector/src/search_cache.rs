//! In-process cache for search results (`search_optimized`, `search_hybrid`).
//!
//! Keyed by (`path`, `table`, `limit`, `options_json`, `vector_hash`) to avoid
//! repeated `LanceDB` scans when the same query is issued. LRU eviction
//! with TTL. Aligns with Python `SearchCache` (`max_size=200`, `ttl=300`).

use std::collections::HashMap;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};
use std::sync::{Mutex, OnceLock};
use std::time::{Duration, Instant};

const DEFAULT_MAX_SIZE: usize = 200;
const DEFAULT_TTL_SECS: u64 = 300;

struct CacheEntry {
    results: Vec<String>,
    inserted_at: Instant,
}

struct SearchResultCache {
    entries: HashMap<String, CacheEntry>,
    max_size: usize,
    ttl: Duration,
}

impl SearchResultCache {
    fn new(max_size: usize, ttl_secs: u64) -> Self {
        Self {
            entries: HashMap::new(),
            max_size,
            ttl: Duration::from_secs(ttl_secs),
        }
    }

    fn hash_vector(v: &[f32]) -> u64 {
        let mut hasher = DefaultHasher::new();
        for &f in v {
            f.to_bits().hash(&mut hasher);
        }
        hasher.finish()
    }

    fn key(
        path: &str,
        table: &str,
        limit: usize,
        options_json: Option<&str>,
        vector: &[f32],
    ) -> String {
        let opt = options_json.unwrap_or("");
        let h = Self::hash_vector(vector);
        format!("{path}:{table}:{limit}:{opt}:{h:016x}")
    }

    fn key_hybrid(
        path: &str,
        table: &str,
        limit: usize,
        vector: &[f32],
        query_text: &str,
    ) -> String {
        let h = Self::hash_vector(vector);
        format!("hybrid:{path}:{table}:{limit}:{query_text}:{h:016x}")
    }

    fn get(&mut self, key: &str) -> Option<Vec<String>> {
        let entry = self.entries.get(key)?;
        if entry.inserted_at.elapsed() > self.ttl {
            self.entries.remove(key);
            return None;
        }
        Some(entry.results.clone())
    }

    fn set(&mut self, key: String, results: Vec<String>) {
        self.evict_expired();
        while self.entries.len() >= self.max_size && !self.entries.is_empty() {
            if let Some(oldest_key) = self
                .entries
                .iter()
                .min_by_key(|(_, e)| e.inserted_at)
                .map(|(k, _)| k.clone())
            {
                self.entries.remove(&oldest_key);
            } else {
                break;
            }
        }
        self.entries.insert(
            key,
            CacheEntry {
                results,
                inserted_at: Instant::now(),
            },
        );
    }

    fn evict_expired(&mut self) {
        let now = Instant::now();
        self.entries
            .retain(|_, e| now.duration_since(e.inserted_at) <= self.ttl);
    }
}

static CACHE: OnceLock<Mutex<SearchResultCache>> = OnceLock::new();

fn get_cache() -> &'static Mutex<SearchResultCache> {
    CACHE.get_or_init(|| Mutex::new(SearchResultCache::new(DEFAULT_MAX_SIZE, DEFAULT_TTL_SECS)))
}

/// Get cached search results if present and not expired.
#[must_use]
pub fn get_cached(
    path: &str,
    table: &str,
    limit: usize,
    options_json: Option<&str>,
    vector: &[f32],
) -> Option<Vec<String>> {
    let key = SearchResultCache::key(path, table, limit, options_json, vector);
    get_cache().lock().ok()?.get(&key)
}

/// Store search results in cache.
pub fn set_cached(
    path: &str,
    table: &str,
    limit: usize,
    options_json: Option<&str>,
    vector: &[f32],
    results: Vec<String>,
) {
    let key = SearchResultCache::key(path, table, limit, options_json, vector);
    if let Ok(mut guard) = get_cache().lock() {
        guard.set(key, results);
    }
}

/// Get cached hybrid search results.
#[must_use]
pub fn get_cached_hybrid(
    path: &str,
    table: &str,
    limit: usize,
    vector: &[f32],
    query_text: &str,
) -> Option<Vec<String>> {
    let key = SearchResultCache::key_hybrid(path, table, limit, vector, query_text);
    get_cache().lock().ok()?.get(&key)
}

/// Store hybrid search results in cache.
pub fn set_cached_hybrid(
    path: &str,
    table: &str,
    limit: usize,
    vector: &[f32],
    query_text: &str,
    results: Vec<String>,
) {
    let key = SearchResultCache::key_hybrid(path, table, limit, vector, query_text);
    if let Ok(mut guard) = get_cache().lock() {
        guard.set(key, results);
    }
}

/// Clear the search cache (for testing).
#[allow(dead_code)]
pub fn clear_cache() {
    if let Ok(mut guard) = get_cache().lock() {
        guard.entries.clear();
    }
}
