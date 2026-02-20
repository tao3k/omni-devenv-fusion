use super::{
    INCREMENTAL_REBUILD_THRESHOLD, IndexedSection, LinkGraphCacheBuildMeta, LinkGraphDocument,
    LinkGraphIndex, LinkGraphRefreshMode, ParsedNote, doc_sort_key, is_supported_note,
    normalize_alias, parse_note,
};
use crate::link_graph::runtime_config::{
    LinkGraphCacheRuntimeConfig, resolve_link_graph_cache_runtime,
};
use crate::link_graph::saliency::{
    DEFAULT_DECAY_RATE, DEFAULT_SALIENCY_BASE, LINK_GRAPH_SALIENCY_SCHEMA_VERSION,
    LinkGraphSaliencyPolicy, LinkGraphSaliencyState, compute_link_graph_saliency, edge_in_key,
    edge_out_key, saliency_key,
};
use rayon::prelude::*;
use serde::{Deserialize, Serialize};
use std::collections::hash_map::DefaultHasher;
use std::collections::{HashMap, HashSet};
use std::hash::{Hash, Hasher};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;
use std::time::{SystemTime, UNIX_EPOCH};
use walkdir::WalkDir;

const LINK_GRAPH_VALKEY_CACHE_SCHEMA_JSON: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../shared/schemas/xiuxian_wendao.link_graph.valkey_cache_snapshot.v1.schema.json"
));
static LINK_GRAPH_CACHE_SCHEMA_FINGERPRINT: OnceLock<String> = OnceLock::new();
const LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION: &str =
    "xiuxian_wendao.link_graph.valkey_cache_snapshot.v1";
const DEFAULT_EXCLUDED_DIR_NAMES: &[&str] = &[
    ".git",
    ".cache",
    ".data",
    ".run",
    ".venv",
    "venv",
    ".devenv",
    "target",
    "node_modules",
];

fn snapshot_default_saliency_base() -> f64 {
    DEFAULT_SALIENCY_BASE
}

fn snapshot_default_decay_rate() -> f64 {
    DEFAULT_DECAY_RATE
}

fn cache_schema_fingerprint() -> &'static str {
    LINK_GRAPH_CACHE_SCHEMA_FINGERPRINT.get_or_init(|| {
        let mut hasher = DefaultHasher::new();
        LINK_GRAPH_VALKEY_CACHE_SCHEMA_JSON.hash(&mut hasher);
        format!("{:016x}", hasher.finish())
    })
}

#[derive(Debug, Clone, Default, Serialize, Deserialize, PartialEq, Eq)]
struct LinkGraphFingerprint {
    note_count: usize,
    latest_modified_ts: Option<i64>,
    total_size_bytes: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct SnapshotDocument {
    id: String,
    id_lower: String,
    stem: String,
    stem_lower: String,
    path: String,
    path_lower: String,
    title: String,
    title_lower: String,
    tags: Vec<String>,
    tags_lower: Vec<String>,
    lead: String,
    word_count: usize,
    search_text: String,
    search_text_lower: String,
    #[serde(default = "snapshot_default_saliency_base")]
    saliency_base: f64,
    #[serde(default = "snapshot_default_decay_rate")]
    decay_rate: f64,
    created_ts: Option<i64>,
    modified_ts: Option<i64>,
}

impl From<&LinkGraphDocument> for SnapshotDocument {
    fn from(value: &LinkGraphDocument) -> Self {
        Self {
            id: value.id.clone(),
            id_lower: value.id_lower.clone(),
            stem: value.stem.clone(),
            stem_lower: value.stem_lower.clone(),
            path: value.path.clone(),
            path_lower: value.path_lower.clone(),
            title: value.title.clone(),
            title_lower: value.title_lower.clone(),
            tags: value.tags.clone(),
            tags_lower: value.tags_lower.clone(),
            lead: value.lead.clone(),
            word_count: value.word_count,
            search_text: value.search_text.clone(),
            search_text_lower: value.search_text_lower.clone(),
            saliency_base: value.saliency_base,
            decay_rate: value.decay_rate,
            created_ts: value.created_ts,
            modified_ts: value.modified_ts,
        }
    }
}

impl SnapshotDocument {
    fn into_document(self) -> LinkGraphDocument {
        LinkGraphDocument {
            id: self.id,
            id_lower: self.id_lower,
            stem: self.stem,
            stem_lower: self.stem_lower,
            path: self.path,
            path_lower: self.path_lower,
            title: self.title,
            title_lower: self.title_lower,
            tags: self.tags,
            tags_lower: self.tags_lower,
            lead: self.lead,
            word_count: self.word_count,
            search_text: self.search_text,
            search_text_lower: self.search_text_lower,
            saliency_base: self.saliency_base,
            decay_rate: self.decay_rate,
            created_ts: self.created_ts,
            modified_ts: self.modified_ts,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct LinkGraphIndexSnapshot {
    schema_version: String,
    #[serde(default)]
    schema_fingerprint: Option<String>,
    root: PathBuf,
    include_dirs: Vec<String>,
    excluded_dirs: Vec<String>,
    fingerprint: LinkGraphFingerprint,
    docs_by_id: HashMap<String, SnapshotDocument>,
    sections_by_doc: HashMap<String, Vec<IndexedSection>>,
    alias_to_doc_id: HashMap<String, String>,
    outgoing: HashMap<String, HashSet<String>>,
    incoming: HashMap<String, HashSet<String>>,
    rank_by_id: HashMap<String, f64>,
    edge_count: usize,
}

impl LinkGraphIndexSnapshot {
    fn from_index(index: &LinkGraphIndex, fingerprint: LinkGraphFingerprint) -> Self {
        let docs_by_id = index
            .docs_by_id
            .iter()
            .map(|(k, v)| (k.clone(), SnapshotDocument::from(v)))
            .collect();
        Self {
            schema_version: LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION.to_string(),
            schema_fingerprint: Some(cache_schema_fingerprint().to_string()),
            root: index.root.clone(),
            include_dirs: index.include_dirs.clone(),
            excluded_dirs: index.excluded_dirs.clone(),
            fingerprint,
            docs_by_id,
            sections_by_doc: index.sections_by_doc.clone(),
            alias_to_doc_id: index.alias_to_doc_id.clone(),
            outgoing: index.outgoing.clone(),
            incoming: index.incoming.clone(),
            rank_by_id: index.rank_by_id.clone(),
            edge_count: index.edge_count,
        }
    }

    fn into_index(self) -> LinkGraphIndex {
        let docs_by_id = self
            .docs_by_id
            .into_iter()
            .map(|(k, v)| (k, v.into_document()))
            .collect();
        LinkGraphIndex {
            root: self.root,
            include_dirs: self.include_dirs,
            excluded_dirs: self.excluded_dirs,
            docs_by_id,
            sections_by_doc: self.sections_by_doc,
            alias_to_doc_id: self.alias_to_doc_id,
            outgoing: self.outgoing,
            incoming: self.incoming,
            rank_by_id: self.rank_by_id,
            edge_count: self.edge_count,
        }
    }
}

#[derive(Debug)]
enum CacheLookupOutcome {
    Hit(LinkGraphIndex),
    Miss(&'static str),
}

fn normalize_include_dir(path: &str) -> Option<String> {
    let normalized = path
        .trim()
        .replace('\\', "/")
        .trim_matches('/')
        .to_lowercase();
    if normalized.is_empty() || normalized == "." {
        return None;
    }
    Some(normalized)
}

fn normalize_excluded_dir(name: &str) -> Option<String> {
    let trimmed = name.trim().trim_matches('/').to_lowercase();
    if trimmed.is_empty() {
        return None;
    }
    Some(trimmed)
}

fn merge_excluded_dirs(excluded_dirs: &[String]) -> Vec<String> {
    let mut merged: Vec<String> = DEFAULT_EXCLUDED_DIR_NAMES
        .iter()
        .map(|name| (*name).to_string())
        .collect();
    merged.extend(excluded_dirs.iter().cloned());
    let mut out: Vec<String> = merged
        .into_iter()
        .filter_map(|name| normalize_excluded_dir(&name))
        .collect();
    out.sort();
    out.dedup();
    out
}

fn relative_path_string(path: &Path, root: &Path) -> Option<String> {
    let Ok(relative) = path.strip_prefix(root) else {
        return None;
    };
    let value = relative
        .components()
        .map(|c| c.as_os_str().to_string_lossy().to_lowercase())
        .collect::<Vec<String>>()
        .join("/");
    Some(value)
}

fn is_under_any_prefix(path: &str, prefixes: &HashSet<String>) -> bool {
    prefixes
        .iter()
        .any(|prefix| path == prefix || path.starts_with(&format!("{prefix}/")))
}

fn is_ancestor_of_any_prefix(path: &str, prefixes: &HashSet<String>) -> bool {
    prefixes.iter().any(|prefix| {
        if path.is_empty() {
            return true;
        }
        prefix == path || prefix.starts_with(&format!("{path}/"))
    })
}

fn should_skip_entry(
    path: &Path,
    is_dir: bool,
    root: &Path,
    include_dirs: &HashSet<String>,
    excluded_dirs: &HashSet<String>,
) -> bool {
    let Some(relative) = relative_path_string(path, root) else {
        return false;
    };

    if !include_dirs.is_empty()
        && !is_under_any_prefix(&relative, include_dirs)
        && !is_ancestor_of_any_prefix(&relative, include_dirs)
    {
        return true;
    }

    let mut components = relative
        .split('/')
        .filter(|value| !value.is_empty())
        .peekable();
    while let Some(component) = components.next() {
        let is_last = components.peek().is_none();
        if !is_dir && is_last {
            break;
        }
        if component.starts_with('.') {
            return true;
        }
    }

    if excluded_dirs.is_empty() {
        return false;
    }

    relative
        .split('/')
        .any(|component| excluded_dirs.contains(component.to_lowercase().as_str()))
}

fn is_supported_note_candidate(path: &Path) -> bool {
    if is_supported_note(path) {
        return true;
    }
    path.extension()
        .and_then(|v| v.to_str())
        .map(|ext| matches!(ext.to_lowercase().as_str(), "md" | "markdown" | "mdx"))
        .unwrap_or(false)
}

fn normalized_relative_note_alias(path: &Path, root: &Path) -> Option<String> {
    let relative = path.strip_prefix(root).unwrap_or(path);
    let raw = relative.to_string_lossy().replace('\\', "/");
    let normalized = normalize_alias(&raw);
    if normalized.is_empty() {
        None
    } else {
        Some(normalized)
    }
}

fn system_time_to_unix(ts: SystemTime) -> Option<i64> {
    let seconds = ts.duration_since(UNIX_EPOCH).ok()?.as_secs();
    i64::try_from(seconds).ok()
}

fn update_fingerprint(path: &Path, fingerprint: &mut LinkGraphFingerprint) {
    let Ok(meta) = std::fs::metadata(path) else {
        return;
    };
    fingerprint.note_count = fingerprint.note_count.saturating_add(1);
    fingerprint.total_size_bytes = fingerprint.total_size_bytes.saturating_add(meta.len());
    let modified = meta.modified().ok().and_then(system_time_to_unix);
    if let Some(ts) = modified {
        fingerprint.latest_modified_ts =
            Some(fingerprint.latest_modified_ts.map_or(ts, |v| v.max(ts)));
    }
}

fn scan_note_fingerprint(
    root: &Path,
    include_dirs: &HashSet<String>,
    excluded_dirs: &HashSet<String>,
) -> LinkGraphFingerprint {
    let mut fingerprint = LinkGraphFingerprint::default();
    for entry in WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|entry| {
            !should_skip_entry(
                entry.path(),
                entry.file_type().is_dir(),
                root,
                include_dirs,
                excluded_dirs,
            )
        })
        .filter_map(Result::ok)
    {
        let path = entry.path();
        if !entry.file_type().is_file() || !is_supported_note(path) {
            continue;
        }
        update_fingerprint(path, &mut fingerprint);
    }
    fingerprint
}

fn cache_slot_key(root: &Path, include_dirs: &[String], excluded_dirs: &[String]) -> String {
    let mut hasher = DefaultHasher::new();
    root.to_string_lossy().hash(&mut hasher);
    include_dirs.hash(&mut hasher);
    excluded_dirs.hash(&mut hasher);
    cache_schema_fingerprint().hash(&mut hasher);
    format!("{:016x}", hasher.finish())
}

fn valkey_cache_key(slot_key: &str, key_prefix: &str) -> String {
    format!("{key_prefix}:{slot_key}")
}

impl LinkGraphIndex {
    fn decode_cached_index_payload(
        raw: &str,
        root: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
        fingerprint: &LinkGraphFingerprint,
    ) -> CacheLookupOutcome {
        let snapshot = match serde_json::from_str::<LinkGraphIndexSnapshot>(raw) {
            Ok(snapshot) => snapshot,
            Err(_) => return CacheLookupOutcome::Miss("payload_parse_error"),
        };
        if snapshot.schema_version != LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION {
            return CacheLookupOutcome::Miss("schema_version_mismatch");
        }
        if snapshot.schema_fingerprint.as_deref() != Some(cache_schema_fingerprint()) {
            return CacheLookupOutcome::Miss("schema_fingerprint_mismatch");
        }
        if snapshot.root != root {
            return CacheLookupOutcome::Miss("root_mismatch");
        }
        if snapshot.include_dirs != include_dirs {
            return CacheLookupOutcome::Miss("include_dirs_mismatch");
        }
        if snapshot.excluded_dirs != excluded_dirs {
            return CacheLookupOutcome::Miss("excluded_dirs_mismatch");
        }
        if snapshot.fingerprint != *fingerprint {
            return CacheLookupOutcome::Miss("content_fingerprint_mismatch");
        }
        CacheLookupOutcome::Hit(snapshot.into_index())
    }

    fn load_cached_index_from_valkey(
        runtime: &LinkGraphCacheRuntimeConfig,
        slot_key: &str,
        root: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
        fingerprint: &LinkGraphFingerprint,
    ) -> Result<CacheLookupOutcome, String> {
        let cache_key = valkey_cache_key(slot_key, &runtime.key_prefix);
        let client = redis::Client::open(runtime.valkey_url.as_str())
            .map_err(|e| format!("invalid valkey url for link-graph cache: {e}"))?;
        let mut conn = client
            .get_connection()
            .map_err(|e| format!("failed to connect valkey for link-graph cache: {e}"))?;
        let raw = redis::cmd("GET")
            .arg(&cache_key)
            .query::<Option<String>>(&mut conn)
            .map_err(|e| format!("failed to GET link-graph cache from valkey: {e}"))?;
        let Some(payload) = raw else {
            return Ok(CacheLookupOutcome::Miss("key_not_found"));
        };
        Ok(Self::decode_cached_index_payload(
            &payload,
            root,
            include_dirs,
            excluded_dirs,
            fingerprint,
        ))
    }

    fn save_cached_index_to_valkey(
        &self,
        runtime: &LinkGraphCacheRuntimeConfig,
        slot_key: &str,
        fingerprint: LinkGraphFingerprint,
    ) -> Result<(), String> {
        let cache_key = valkey_cache_key(slot_key, &runtime.key_prefix);
        let payload = LinkGraphIndexSnapshot::from_index(self, fingerprint);
        let encoded = serde_json::to_string(&payload)
            .map_err(|e| format!("failed to serialize link-graph cache payload: {e}"))?;
        let client = redis::Client::open(runtime.valkey_url.as_str())
            .map_err(|e| format!("invalid valkey url for link-graph cache: {e}"))?;
        let mut conn = client
            .get_connection()
            .map_err(|e| format!("failed to connect valkey for link-graph cache: {e}"))?;
        if let Some(ttl_seconds) = runtime.ttl_seconds {
            redis::cmd("SETEX")
                .arg(&cache_key)
                .arg(ttl_seconds)
                .arg(&encoded)
                .query::<()>(&mut conn)
                .map_err(|e| format!("failed to SETEX link-graph cache to valkey: {e}"))?;
        } else {
            redis::cmd("SET")
                .arg(&cache_key)
                .arg(&encoded)
                .query::<()>(&mut conn)
                .map_err(|e| format!("failed to SET link-graph cache to valkey: {e}"))?;
        }
        Ok(())
    }

    fn sync_graphmem_state_to_valkey(
        &self,
        runtime: &LinkGraphCacheRuntimeConfig,
    ) -> Result<(), String> {
        let client = redis::Client::open(runtime.valkey_url.as_str())
            .map_err(|e| format!("invalid valkey url for link-graph graphmem sync: {e}"))?;
        let mut conn = client
            .get_connection()
            .map_err(|e| format!("failed to connect valkey for link-graph graphmem sync: {e}"))?;

        let now_unix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_or(0, |delta| delta.as_secs() as i64);
        let now_unix_f64 = now_unix as f64;
        let policy = LinkGraphSaliencyPolicy::default();

        let mut score_by_doc: HashMap<String, f64> = HashMap::with_capacity(self.docs_by_id.len());
        for doc in self.docs_by_id.values() {
            let node_id = doc.id.as_str();
            let state_key = saliency_key(node_id, &runtime.key_prefix);
            let existing_raw = redis::cmd("GET")
                .arg(&state_key)
                .query::<Option<String>>(&mut conn)
                .map_err(|e| format!("failed to GET saliency seed for '{node_id}': {e}"))?;

            let existing_score = existing_raw
                .as_deref()
                .and_then(|raw| serde_json::from_str::<LinkGraphSaliencyState>(raw).ok())
                .filter(|state| {
                    state.schema == LINK_GRAPH_SALIENCY_SCHEMA_VERSION && state.node_id == node_id
                })
                .map(|state| state.current_saliency);

            if let Some(score) = existing_score {
                score_by_doc.insert(node_id.to_string(), score);
                continue;
            }

            let seeded_score =
                compute_link_graph_saliency(doc.saliency_base, doc.decay_rate, 0, 0.0, policy);
            let seeded_state = LinkGraphSaliencyState {
                schema: LINK_GRAPH_SALIENCY_SCHEMA_VERSION.to_string(),
                node_id: node_id.to_string(),
                saliency_base: seeded_score,
                decay_rate: doc.decay_rate,
                activation_count: 0,
                last_accessed_unix: now_unix,
                current_saliency: seeded_score,
                updated_at_unix: now_unix_f64,
            };
            let encoded = serde_json::to_string(&seeded_state)
                .map_err(|e| format!("failed to serialize seeded saliency for '{node_id}': {e}"))?;
            redis::cmd("SET")
                .arg(&state_key)
                .arg(encoded)
                .query::<()>(&mut conn)
                .map_err(|e| format!("failed to SET seeded saliency for '{node_id}': {e}"))?;
            score_by_doc.insert(node_id.to_string(), seeded_score);
        }

        let in_pattern = format!("{}:kg:edge:in:*", runtime.key_prefix);
        let out_pattern = format!("{}:kg:edge:out:*", runtime.key_prefix);
        let stale_in_keys = redis::cmd("KEYS")
            .arg(&in_pattern)
            .query::<Vec<String>>(&mut conn)
            .unwrap_or_default();
        if !stale_in_keys.is_empty() {
            let _ = redis::cmd("DEL").arg(stale_in_keys).query::<i64>(&mut conn);
        }
        let stale_out_keys = redis::cmd("KEYS")
            .arg(&out_pattern)
            .query::<Vec<String>>(&mut conn)
            .unwrap_or_default();
        if !stale_out_keys.is_empty() {
            let _ = redis::cmd("DEL")
                .arg(stale_out_keys)
                .query::<i64>(&mut conn);
        }

        for (from, targets) in &self.outgoing {
            let out_key = edge_out_key(from, &runtime.key_prefix);
            for to in targets {
                let in_key = edge_in_key(to, &runtime.key_prefix);
                let _ = redis::cmd("SADD")
                    .arg(&in_key)
                    .arg(from)
                    .query::<i64>(&mut conn);
                let score = score_by_doc
                    .get(to)
                    .copied()
                    .unwrap_or(DEFAULT_SALIENCY_BASE);
                let _ = redis::cmd("ZADD")
                    .arg(&out_key)
                    .arg(score)
                    .arg(to)
                    .query::<i64>(&mut conn);
            }
        }

        Ok(())
    }

    fn sync_graphmem_state_best_effort(&self) {
        let Ok(runtime) = resolve_link_graph_cache_runtime() else {
            return;
        };
        let _ = self.sync_graphmem_state_to_valkey(&runtime);
    }

    /// Build index from notebook root directory.
    pub fn build(root_dir: &Path) -> Result<Self, String> {
        let index = Self::build_with_filters(root_dir, &[], &[])?;
        index.sync_graphmem_state_best_effort();
        Ok(index)
    }

    fn build_with_cache_runtime_with_meta(
        root_dir: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
        runtime: &LinkGraphCacheRuntimeConfig,
    ) -> Result<(Self, LinkGraphCacheBuildMeta), String> {
        let root = root_dir
            .canonicalize()
            .map_err(|e| format!("invalid notebook root '{}': {e}", root_dir.display()))?;
        if !root.is_dir() {
            return Err(format!(
                "notebook root is not a directory: {}",
                root.display()
            ));
        }

        let normalized_include_dirs: Vec<String> = include_dirs
            .iter()
            .filter_map(|path| normalize_include_dir(path))
            .collect();
        let normalized_excluded_dirs: Vec<String> = merge_excluded_dirs(excluded_dirs);
        let included: HashSet<String> = normalized_include_dirs.iter().cloned().collect();
        let excluded: HashSet<String> = normalized_excluded_dirs.iter().cloned().collect();
        let slot_key = cache_slot_key(&root, &normalized_include_dirs, &normalized_excluded_dirs);
        let fingerprint = scan_note_fingerprint(&root, &included, &excluded);
        let cache_lookup = Self::load_cached_index_from_valkey(
            runtime,
            &slot_key,
            &root,
            &normalized_include_dirs,
            &normalized_excluded_dirs,
            &fingerprint,
        )?;
        let miss_reason = match cache_lookup {
            CacheLookupOutcome::Hit(index) => {
                let _ = index.sync_graphmem_state_to_valkey(runtime);
                let meta = LinkGraphCacheBuildMeta {
                    backend: "valkey".to_string(),
                    status: "hit".to_string(),
                    miss_reason: None,
                    schema_version: LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION.to_string(),
                    schema_fingerprint: cache_schema_fingerprint().to_string(),
                };
                return Ok((index, meta));
            }
            CacheLookupOutcome::Miss(reason) => Some(reason.to_string()),
        };

        let index =
            Self::build_with_filters(&root, &normalized_include_dirs, &normalized_excluded_dirs)?;
        let _ = index.sync_graphmem_state_to_valkey(runtime);
        index.save_cached_index_to_valkey(runtime, &slot_key, fingerprint)?;
        let meta = LinkGraphCacheBuildMeta {
            backend: "valkey".to_string(),
            status: "miss".to_string(),
            miss_reason,
            schema_version: LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION.to_string(),
            schema_fingerprint: cache_schema_fingerprint().to_string(),
        };
        Ok((index, meta))
    }

    /// Build index with cache fast-path.
    ///
    /// Uses a fingerprint-validated snapshot in Valkey.
    /// Rebuilds when cache key is missing/stale, then writes snapshot back to Valkey.
    pub fn build_with_cache(
        root_dir: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
    ) -> Result<Self, String> {
        let runtime = resolve_link_graph_cache_runtime()?;
        let (index, _) = Self::build_with_cache_runtime_with_meta(
            root_dir,
            include_dirs,
            excluded_dirs,
            &runtime,
        )?;
        Ok(index)
    }

    /// Build index with cache fast-path and return cache build metadata.
    pub fn build_with_cache_with_meta(
        root_dir: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
    ) -> Result<(Self, LinkGraphCacheBuildMeta), String> {
        let runtime = resolve_link_graph_cache_runtime()?;
        Self::build_with_cache_runtime_with_meta(root_dir, include_dirs, excluded_dirs, &runtime)
    }

    /// Build index with an explicit Valkey cache runtime.
    ///
    /// Intended for tests and controlled runners that pass cache config directly.
    pub fn build_with_cache_with_valkey(
        root_dir: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
        valkey_url: &str,
        key_prefix: Option<&str>,
        ttl_seconds: Option<u64>,
    ) -> Result<Self, String> {
        if valkey_url.trim().is_empty() {
            return Err("link_graph cache valkey_url must be non-empty".to_string());
        }
        let runtime = LinkGraphCacheRuntimeConfig::from_parts(valkey_url, key_prefix, ttl_seconds);
        let (index, _) = Self::build_with_cache_runtime_with_meta(
            root_dir,
            include_dirs,
            excluded_dirs,
            &runtime,
        )?;
        Ok(index)
    }

    /// Build index with explicit Valkey runtime and return cache build metadata.
    pub fn build_with_cache_with_valkey_with_meta(
        root_dir: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
        valkey_url: &str,
        key_prefix: Option<&str>,
        ttl_seconds: Option<u64>,
    ) -> Result<(Self, LinkGraphCacheBuildMeta), String> {
        if valkey_url.trim().is_empty() {
            return Err("link_graph cache valkey_url must be non-empty".to_string());
        }
        let runtime = LinkGraphCacheRuntimeConfig::from_parts(valkey_url, key_prefix, ttl_seconds);
        Self::build_with_cache_runtime_with_meta(root_dir, include_dirs, excluded_dirs, &runtime)
    }

    /// Return the schema version used by LinkGraph Valkey cache snapshots.
    #[must_use]
    pub fn valkey_cache_schema_version() -> &'static str {
        LINK_GRAPH_VALKEY_CACHE_SCHEMA_VERSION
    }

    /// Return the schema fingerprint used by LinkGraph Valkey cache snapshots.
    ///
    /// Fingerprint changes whenever the shared schema JSON changes.
    #[must_use]
    pub fn valkey_cache_schema_fingerprint() -> &'static str {
        cache_schema_fingerprint()
    }

    /// Build index with excluded directory names (e.g. ".cache", ".git").
    pub fn build_with_excluded_dirs(
        root_dir: &Path,
        excluded_dirs: &[String],
    ) -> Result<Self, String> {
        let index = Self::build_with_filters(root_dir, &[], excluded_dirs)?;
        index.sync_graphmem_state_best_effort();
        Ok(index)
    }

    /// Build index with include/exclude directory filters relative to notebook root.
    pub fn build_with_filters(
        root_dir: &Path,
        include_dirs: &[String],
        excluded_dirs: &[String],
    ) -> Result<Self, String> {
        let root = root_dir
            .canonicalize()
            .map_err(|e| format!("invalid notebook root '{}': {e}", root_dir.display()))?;
        if !root.is_dir() {
            return Err(format!(
                "notebook root is not a directory: {}",
                root.display()
            ));
        }

        let normalized_include_dirs: Vec<String> = include_dirs
            .iter()
            .filter_map(|path| normalize_include_dir(path))
            .collect();
        let normalized_excluded_dirs: Vec<String> = merge_excluded_dirs(excluded_dirs);
        let included: HashSet<String> = normalized_include_dirs.iter().cloned().collect();
        let excluded: HashSet<String> = normalized_excluded_dirs.iter().cloned().collect();

        let mut candidate_paths: Vec<PathBuf> = Vec::new();
        for entry in WalkDir::new(&root)
            .follow_links(false)
            .into_iter()
            .filter_entry(|entry| {
                !should_skip_entry(
                    entry.path(),
                    entry.file_type().is_dir(),
                    &root,
                    &included,
                    &excluded,
                )
            })
            .filter_map(Result::ok)
        {
            let path = entry.path();
            if !entry.file_type().is_file() || !is_supported_note(path) {
                continue;
            }
            candidate_paths.push(path.to_path_buf());
        }

        let mut parsed_notes: Vec<ParsedNote> = candidate_paths
            .into_par_iter()
            .filter_map(|path| {
                let content = std::fs::read_to_string(&path).ok()?;
                parse_note(&path, &root, &content)
            })
            .collect();

        parsed_notes.sort_by(|left, right| doc_sort_key(&left.doc).cmp(&doc_sort_key(&right.doc)));

        let mut docs_by_id: HashMap<String, LinkGraphDocument> = HashMap::new();
        let mut sections_by_doc: HashMap<String, Vec<IndexedSection>> = HashMap::new();
        let mut alias_to_doc_id: HashMap<String, String> = HashMap::new();
        for parsed in &parsed_notes {
            let doc = &parsed.doc;
            docs_by_id.insert(doc.id.clone(), doc.clone());
            let indexed_sections = parsed
                .sections
                .iter()
                .map(IndexedSection::from_parsed)
                .collect::<Vec<IndexedSection>>();
            sections_by_doc.insert(doc.id.clone(), indexed_sections);
            for alias in [&doc.id, &doc.path, &doc.stem] {
                let key = normalize_alias(alias);
                if key.is_empty() {
                    continue;
                }
                alias_to_doc_id.entry(key).or_insert_with(|| doc.id.clone());
            }
        }

        let mut outgoing: HashMap<String, HashSet<String>> = HashMap::new();
        let mut incoming: HashMap<String, HashSet<String>> = HashMap::new();
        let mut edge_count = 0usize;

        for parsed in parsed_notes {
            let from_id = parsed.doc.id;
            for raw_target in parsed.link_targets {
                let normalized = normalize_alias(&raw_target);
                if normalized.is_empty() {
                    continue;
                }
                let Some(to_id) = alias_to_doc_id.get(&normalized).cloned() else {
                    continue;
                };
                if to_id == from_id {
                    continue;
                }
                let inserted = outgoing
                    .entry(from_id.clone())
                    .or_default()
                    .insert(to_id.clone());
                if inserted {
                    incoming.entry(to_id).or_default().insert(from_id.clone());
                    edge_count += 1;
                }
            }
        }

        let rank_by_id = Self::compute_rank_by_id(&docs_by_id, &incoming, &outgoing);

        Ok(Self {
            root,
            include_dirs: normalized_include_dirs,
            excluded_dirs: normalized_excluded_dirs,
            docs_by_id,
            sections_by_doc,
            alias_to_doc_id,
            outgoing,
            incoming,
            rank_by_id,
            edge_count,
        })
    }

    fn rebuild_from_current_filters(&self) -> Result<Self, String> {
        Self::build_with_filters(&self.root, &self.include_dirs, &self.excluded_dirs)
    }

    fn recompute_edge_count(&mut self) {
        self.edge_count = self.outgoing.values().map(HashSet::len).sum();
    }

    fn recompute_rank_by_id(&mut self) {
        self.rank_by_id =
            Self::compute_rank_by_id(&self.docs_by_id, &self.incoming, &self.outgoing);
    }

    fn prune_empty_edge_sets(&mut self) {
        self.outgoing.retain(|_, targets| !targets.is_empty());
        self.incoming.retain(|_, sources| !sources.is_empty());
    }

    fn remove_doc_by_id(&mut self, doc_id: &str) {
        self.docs_by_id.remove(doc_id);
        self.sections_by_doc.remove(doc_id);
        self.alias_to_doc_id
            .retain(|_, existing| existing != doc_id);
        self.outgoing.remove(doc_id);
        self.incoming.remove(doc_id);
        for targets in self.outgoing.values_mut() {
            targets.remove(doc_id);
        }
        for sources in self.incoming.values_mut() {
            sources.remove(doc_id);
        }
        self.prune_empty_edge_sets();
    }

    fn insert_doc_no_edges(&mut self, parsed: &ParsedNote) {
        let doc = &parsed.doc;
        self.docs_by_id.insert(doc.id.clone(), doc.clone());
        self.sections_by_doc.insert(
            doc.id.clone(),
            parsed
                .sections
                .iter()
                .map(IndexedSection::from_parsed)
                .collect::<Vec<IndexedSection>>(),
        );
        for alias in [&doc.id, &doc.path, &doc.stem] {
            let key = normalize_alias(alias);
            if key.is_empty() {
                continue;
            }
            self.alias_to_doc_id.insert(key, doc.id.clone());
        }
    }

    fn add_outgoing_links_for_doc(&mut self, parsed: &ParsedNote) {
        let from_id = parsed.doc.id.clone();
        for raw_target in &parsed.link_targets {
            let normalized = normalize_alias(raw_target);
            if normalized.is_empty() {
                continue;
            }
            let Some(to_id) = self.alias_to_doc_id.get(&normalized).cloned() else {
                continue;
            };
            if to_id == from_id {
                continue;
            }
            let inserted = self
                .outgoing
                .entry(from_id.clone())
                .or_default()
                .insert(to_id.clone());
            if inserted {
                self.incoming
                    .entry(to_id)
                    .or_default()
                    .insert(from_id.clone());
            }
        }
    }

    /// Apply incremental updates for changed note files.
    ///
    /// Falls back to full rebuild when change-set is large.
    pub fn refresh_incremental(&mut self, changed_paths: &[PathBuf]) -> Result<(), String> {
        let _ =
            self.refresh_incremental_with_threshold(changed_paths, INCREMENTAL_REBUILD_THRESHOLD)?;
        Ok(())
    }

    /// Apply incremental updates for changed note files with explicit threshold.
    pub fn refresh_incremental_with_threshold(
        &mut self,
        changed_paths: &[PathBuf],
        full_rebuild_threshold: usize,
    ) -> Result<LinkGraphRefreshMode, String> {
        if changed_paths.is_empty() {
            return Ok(LinkGraphRefreshMode::Noop);
        }
        let threshold = full_rebuild_threshold.max(1);
        if changed_paths.len() >= threshold {
            *self = self.rebuild_from_current_filters()?;
            self.sync_graphmem_state_best_effort();
            return Ok(LinkGraphRefreshMode::Full);
        }

        let included: HashSet<String> = self.include_dirs.iter().cloned().collect();
        let excluded: HashSet<String> = self.excluded_dirs.iter().cloned().collect();
        let mut parsed_updates: Vec<ParsedNote> = Vec::new();
        for changed in changed_paths {
            let raw_candidate = if changed.is_absolute() {
                changed.clone()
            } else {
                self.root.join(changed)
            };
            let candidate = if raw_candidate.exists() {
                raw_candidate
                    .canonicalize()
                    .unwrap_or_else(|_| raw_candidate.clone())
            } else {
                raw_candidate
            };
            if should_skip_entry(&candidate, false, &self.root, &included, &excluded) {
                continue;
            }
            if !is_supported_note_candidate(&candidate) {
                continue;
            }

            if let Some(alias) = normalized_relative_note_alias(&candidate, &self.root)
                && let Some(existing_id) = self.resolve_doc_id(&alias).map(str::to_string)
            {
                self.remove_doc_by_id(&existing_id);
            } else if let Some(stem) = candidate.file_stem().and_then(|v| v.to_str()) {
                let stem_alias = normalize_alias(stem);
                if let Some(existing_id) = self.resolve_doc_id(&stem_alias).map(str::to_string) {
                    self.remove_doc_by_id(&existing_id);
                }
            }

            if !candidate.exists() || !candidate.is_file() {
                continue;
            }
            if !is_supported_note(&candidate) {
                continue;
            }
            let content = std::fs::read_to_string(&candidate).map_err(|e| {
                format!("failed to read changed note '{}': {e}", candidate.display())
            })?;
            if let Some(parsed) = parse_note(&candidate, &self.root, &content) {
                parsed_updates.push(parsed);
            }
        }

        for parsed in &parsed_updates {
            self.insert_doc_no_edges(parsed);
        }
        for parsed in &parsed_updates {
            self.add_outgoing_links_for_doc(parsed);
        }
        self.prune_empty_edge_sets();
        self.recompute_edge_count();
        self.recompute_rank_by_id();
        self.sync_graphmem_state_best_effort();
        Ok(LinkGraphRefreshMode::Delta)
    }
}
