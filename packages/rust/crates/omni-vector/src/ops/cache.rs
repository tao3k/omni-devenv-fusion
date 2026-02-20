//! Bounded LRU cache for Lance `Dataset` handles (connection-pool style).

use std::collections::VecDeque;

use dashmap::DashMap;
use lance::dataset::Dataset;

/// Configuration for the Dataset cache (connection-pool style).
#[derive(Clone, Copy, Debug, Default)]
pub struct DatasetCacheConfig {
    /// Max tables to keep open; when exceeded, least-recently-used is evicted.
    /// `None` means unbounded.
    pub max_cached_tables: Option<usize>,
}

/// Cache of table name -> Dataset with optional LRU eviction when at capacity.
pub struct DatasetCache {
    entries: DashMap<String, Dataset>,
    /// Keys in order of last use (front = oldest). Only used when `max_cached_tables` is `Some`.
    lru_order: VecDeque<String>,
    max_size: Option<usize>,
}

impl DatasetCache {
    /// Create a new cache with the given config.
    #[must_use]
    pub fn new(config: DatasetCacheConfig) -> Self {
        Self {
            entries: DashMap::new(),
            lru_order: VecDeque::new(),
            max_size: config.max_cached_tables,
        }
    }

    /// Get a clone of the dataset if present and bump it to most recently used.
    pub fn get(&mut self, key: &str) -> Option<Dataset> {
        let out = self.entries.get(key).map(|r| r.clone())?;
        self.bump_lru(key);
        Some(out)
    }

    /// Insert or replace; evict oldest entries if over `max_cached_tables`.
    pub fn insert(&mut self, key: String, value: Dataset) {
        self.evict_until_under_capacity(1);
        self.lru_order.retain(|k| k != &key);
        self.lru_order.push_back(key.clone());
        self.entries.insert(key, value);
    }

    /// Remove and return the dataset for the key.
    pub fn remove(&mut self, key: &str) -> Option<Dataset> {
        self.lru_order.retain(|k| k != key);
        self.entries.remove(key).map(|(_, v)| v)
    }

    /// Number of datasets currently in the cache.
    #[must_use]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the cache has no entries.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Whether the cache has an entry for the key.
    #[must_use]
    pub fn contains_key(&self, key: &str) -> bool {
        self.entries.contains_key(key)
    }

    fn bump_lru(&mut self, key: &str) {
        self.lru_order.retain(|k| k != key);
        self.lru_order.push_back(key.to_string());
    }

    /// Evict from front of `lru_order` until `len + reserve < max_size` (if `max_size` is `Some`).
    fn evict_until_under_capacity(&mut self, reserve: usize) {
        let Some(max) = self.max_size else {
            return;
        };
        while self.entries.len() + reserve > max {
            let Some(old) = self.lru_order.pop_front() else {
                break;
            };
            self.entries.remove(&old);
        }
    }
}
