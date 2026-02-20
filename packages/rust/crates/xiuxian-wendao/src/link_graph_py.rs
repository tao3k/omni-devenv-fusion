//! PyO3 bindings for markdown link graph engine.

use crate::link_graph::{
    LinkGraphDirection, LinkGraphIndex, LinkGraphRefreshMode, LinkGraphSearchOptions,
    valkey_stats_cache_del, valkey_stats_cache_get, valkey_stats_cache_set,
};
use pyo3::prelude::*;
use std::path::PathBuf;
use std::time::Instant;

/// Read LinkGraph stats cache payload from Valkey.
///
/// Returns JSON object string when cache is valid and fresh, otherwise `None`.
#[pyfunction]
pub fn link_graph_stats_cache_get(source_key: &str, ttl_sec: f64) -> PyResult<Option<String>> {
    valkey_stats_cache_get(source_key, ttl_sec).map_err(pyo3::exceptions::PyValueError::new_err)
}

/// Write LinkGraph stats cache payload to Valkey with TTL.
///
/// `stats_json` must be a JSON object with:
/// `total_notes`, `orphans`, `links_in_graph`, `nodes_in_graph`.
#[pyfunction]
pub fn link_graph_stats_cache_set(
    source_key: &str,
    stats_json: &str,
    ttl_sec: f64,
) -> PyResult<()> {
    valkey_stats_cache_set(source_key, stats_json, ttl_sec)
        .map_err(pyo3::exceptions::PyValueError::new_err)
}

/// Delete LinkGraph stats cache payload from Valkey.
#[pyfunction]
pub fn link_graph_stats_cache_del(source_key: &str) -> PyResult<()> {
    valkey_stats_cache_del(source_key).map_err(pyo3::exceptions::PyValueError::new_err)
}

/// Python wrapper around Rust markdown link-graph index.
#[pyclass]
#[derive(Debug, Clone)]
pub struct PyLinkGraphEngine {
    root: PathBuf,
    include_dirs: Vec<String>,
    excluded_dirs: Vec<String>,
    inner: LinkGraphIndex,
    cache_backend: String,
    cache_status: String,
    cache_miss_reason: Option<String>,
    cache_schema_version: String,
    cache_schema_fingerprint: String,
}

impl PyLinkGraphEngine {
    fn parse_search_options(options_json: Option<&str>) -> PyResult<LinkGraphSearchOptions> {
        let Some(raw) = options_json
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            return Ok(LinkGraphSearchOptions::default());
        };
        let options = serde_json::from_str::<LinkGraphSearchOptions>(raw)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        options
            .validate()
            .map_err(pyo3::exceptions::PyValueError::new_err)?;
        Ok(options)
    }

    fn run_search_planned(
        &self,
        query: &str,
        limit: usize,
        options_json: Option<&str>,
    ) -> PyResult<String> {
        let options = Self::parse_search_options(options_json)?;
        let payload = self
            .inner
            .search_planned_payload(query, limit.max(1), options);
        serde_json::to_string(&payload)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    fn parse_changed_paths(changed_paths_json: Option<&str>) -> PyResult<Vec<PathBuf>> {
        let Some(raw) = changed_paths_json
            .map(str::trim)
            .filter(|value| !value.is_empty())
        else {
            return Ok(Vec::new());
        };
        let payload = serde_json::from_str::<Vec<String>>(raw)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(payload.into_iter().map(PathBuf::from).collect())
    }

    fn apply_cache_meta(&mut self, meta: crate::link_graph::LinkGraphCacheBuildMeta) {
        self.cache_backend = meta.backend;
        self.cache_status = meta.status;
        self.cache_miss_reason = meta.miss_reason;
        self.cache_schema_version = meta.schema_version;
        self.cache_schema_fingerprint = meta.schema_fingerprint;
    }

    fn elapsed_ms(started_at: Instant) -> f64 {
        started_at.elapsed().as_secs_f64() * 1000.0
    }
}

#[pymethods]
impl PyLinkGraphEngine {
    #[new]
    #[pyo3(signature = (notebook_dir, include_dirs=None, excluded_dirs=None))]
    fn new(
        notebook_dir: &str,
        include_dirs: Option<Vec<String>>,
        excluded_dirs: Option<Vec<String>>,
    ) -> PyResult<Self> {
        let root = PathBuf::from(notebook_dir);
        let include_dirs = include_dirs.unwrap_or_default();
        let excluded_dirs = excluded_dirs.unwrap_or_default();
        let (inner, meta) =
            LinkGraphIndex::build_with_cache_with_meta(&root, &include_dirs, &excluded_dirs)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        Ok(Self {
            root,
            include_dirs,
            excluded_dirs,
            inner,
            cache_backend: meta.backend,
            cache_status: meta.status,
            cache_miss_reason: meta.miss_reason,
            cache_schema_version: meta.schema_version,
            cache_schema_fingerprint: meta.schema_fingerprint,
        })
    }

    /// Rebuild index from the same root path.
    fn refresh(&mut self) -> PyResult<()> {
        let (inner, meta) = LinkGraphIndex::build_with_cache_with_meta(
            &self.root,
            &self.include_dirs,
            &self.excluded_dirs,
        )
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
        self.inner = inner;
        self.apply_cache_meta(meta);
        Ok(())
    }

    /// Incremental refresh with changed path list.
    ///
    /// `changed_paths_json` should be a JSON array of path strings.
    #[pyo3(signature = (changed_paths_json=None, force_full=false))]
    fn refresh_with_delta(
        &mut self,
        changed_paths_json: Option<&str>,
        force_full: bool,
    ) -> PyResult<()> {
        if force_full {
            return self.refresh();
        }
        let changed_paths = Self::parse_changed_paths(changed_paths_json)?;
        if changed_paths.is_empty() {
            return Ok(());
        }
        self.inner
            .refresh_incremental(&changed_paths)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Unified refresh planner + executor.
    ///
    /// Returns JSON object with mode/fallback and phase events:
    /// {"mode":"delta|full|noop","changed_count":1,"force_full":false,"fallback":false,"events":[...]}
    #[pyo3(signature = (changed_paths_json=None, force_full=false, full_rebuild_threshold=None))]
    fn refresh_plan_apply(
        &mut self,
        changed_paths_json: Option<&str>,
        force_full: bool,
        full_rebuild_threshold: Option<usize>,
    ) -> PyResult<String> {
        let changed_paths = Self::parse_changed_paths(changed_paths_json)?;
        let changed_count = changed_paths.len();
        let threshold =
            full_rebuild_threshold.unwrap_or_else(LinkGraphIndex::incremental_rebuild_threshold);
        let threshold = threshold.max(1);

        let plan_started = Instant::now();
        let (strategy, reason) = if force_full {
            ("full", "force_full")
        } else if changed_count == 0 {
            ("noop", "noop")
        } else if changed_count >= threshold {
            ("full", "threshold_exceeded")
        } else {
            ("delta", "delta_requested")
        };
        let mut events = Vec::new();
        events.push(serde_json::json!({
            "phase": "link_graph.index.delta.plan",
            "duration_ms": Self::elapsed_ms(plan_started),
            "extra": {
                "strategy": strategy,
                "reason": reason,
                "changed_count": changed_count,
                "force_full": force_full,
                "threshold": threshold,
                "delta_supported": true,
                "full_refresh_supported": true,
            }
        }));

        if strategy == "noop" {
            let payload = serde_json::json!({
                "mode": "noop",
                "changed_count": 0,
                "force_full": false,
                "fallback": false,
                "events": events,
            });
            return serde_json::to_string(&payload)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()));
        }

        if strategy == "full" {
            let full_started = Instant::now();
            self.refresh()?;
            events.push(serde_json::json!({
                "phase": "link_graph.index.rebuild.full",
                "duration_ms": Self::elapsed_ms(full_started),
                "extra": {
                    "success": true,
                    "reason": reason,
                    "changed_count": changed_count,
                }
            }));
            let payload = serde_json::json!({
                "mode": "full",
                "changed_count": changed_count,
                "force_full": force_full,
                "fallback": false,
                "events": events,
            });
            return serde_json::to_string(&payload)
                .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()));
        }

        let delta_started = Instant::now();
        match self
            .inner
            .refresh_incremental_with_threshold(&changed_paths, threshold)
        {
            Ok(LinkGraphRefreshMode::Noop) => {
                events.push(serde_json::json!({
                    "phase": "link_graph.index.delta.apply",
                    "duration_ms": Self::elapsed_ms(delta_started),
                    "extra": {
                        "success": true,
                        "changed_count": 0,
                    }
                }));
                let payload = serde_json::json!({
                    "mode": "noop",
                    "changed_count": 0,
                    "force_full": false,
                    "fallback": false,
                    "events": events,
                });
                serde_json::to_string(&payload)
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
            }
            Ok(LinkGraphRefreshMode::Delta) => {
                events.push(serde_json::json!({
                    "phase": "link_graph.index.delta.apply",
                    "duration_ms": Self::elapsed_ms(delta_started),
                    "extra": {
                        "success": true,
                        "changed_count": changed_count,
                    }
                }));
                let payload = serde_json::json!({
                    "mode": "delta",
                    "changed_count": changed_count,
                    "force_full": false,
                    "fallback": false,
                    "events": events,
                });
                serde_json::to_string(&payload)
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
            }
            Ok(LinkGraphRefreshMode::Full) => {
                events.push(serde_json::json!({
                    "phase": "link_graph.index.rebuild.full",
                    "duration_ms": Self::elapsed_ms(delta_started),
                    "extra": {
                        "success": true,
                        "reason": "threshold_exceeded",
                        "changed_count": changed_count,
                    }
                }));
                let payload = serde_json::json!({
                    "mode": "full",
                    "changed_count": changed_count,
                    "force_full": false,
                    "fallback": false,
                    "events": events,
                });
                serde_json::to_string(&payload)
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
            }
            Err(delta_error) => {
                events.push(serde_json::json!({
                    "phase": "link_graph.index.delta.apply",
                    "duration_ms": Self::elapsed_ms(delta_started),
                    "extra": {
                        "success": false,
                        "changed_count": changed_count,
                        "error": delta_error,
                    }
                }));
                let full_started = Instant::now();
                self.refresh()?;
                events.push(serde_json::json!({
                    "phase": "link_graph.index.rebuild.full",
                    "duration_ms": Self::elapsed_ms(full_started),
                    "extra": {
                        "success": true,
                        "reason": "delta_failed_fallback",
                        "changed_count": changed_count,
                    }
                }));
                let payload = serde_json::json!({
                    "mode": "full",
                    "changed_count": changed_count,
                    "force_full": false,
                    "fallback": true,
                    "events": events,
                });
                serde_json::to_string(&payload)
                    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
            }
        }
    }

    /// Search and return parsed query plan + effective options:
    /// {"query":"...","options":{...},"results":[...]}
    #[pyo3(signature = (query, limit=20, options_json=None))]
    fn search_planned(
        &self,
        query: &str,
        limit: usize,
        options_json: Option<&str>,
    ) -> PyResult<String> {
        self.run_search_planned(query, limit, options_json)
    }

    /// Fetch neighbors around a note.
    #[pyo3(signature = (stem, direction="both", hops=1, limit=50))]
    fn neighbors(
        &self,
        stem: &str,
        direction: &str,
        hops: usize,
        limit: usize,
    ) -> PyResult<String> {
        let rows = self.inner.neighbors(
            stem,
            LinkGraphDirection::from_alias(direction),
            hops.max(1),
            limit.max(1),
        );
        serde_json::to_string(&rows)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Fetch related notes through bidirectional traversal.
    #[pyo3(signature = (stem, max_distance=2, limit=20))]
    fn related(&self, stem: &str, max_distance: usize, limit: usize) -> PyResult<String> {
        serde_json::to_string(&self.inner.related(stem, max_distance.max(1), limit.max(1)))
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Fetch note metadata.
    fn metadata(&self, stem: &str) -> PyResult<String> {
        serde_json::to_string(&self.inner.metadata(stem))
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Return table-of-contents rows.
    #[pyo3(signature = (limit=1000))]
    fn toc(&self, limit: usize) -> PyResult<String> {
        serde_json::to_string(&self.inner.toc(limit.max(1)))
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Return graph stats.
    fn stats(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner.stats())
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }

    /// Return cache schema version/fingerprint used by Valkey snapshot payloads.
    fn cache_schema_info(&self) -> PyResult<String> {
        let payload = serde_json::json!({
            "backend": self.cache_backend,
            "cache_status": self.cache_status,
            "cache_miss_reason": self.cache_miss_reason,
            "schema_version": self.cache_schema_version,
            "schema_fingerprint": self.cache_schema_fingerprint,
        });
        serde_json::to_string(&payload)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))
    }
}
