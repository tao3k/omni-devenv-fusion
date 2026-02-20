//! Core index build + query algorithms for markdown link graph.

use super::models::{
    LinkGraphDirection, LinkGraphDocument, LinkGraphEdgeType, LinkGraphHit, LinkGraphLinkFilter,
    LinkGraphMatchStrategy, LinkGraphMetadata, LinkGraphNeighbor, LinkGraphPprSubgraphMode,
    LinkGraphRelatedFilter, LinkGraphRelatedPprDiagnostics, LinkGraphRelatedPprOptions,
    LinkGraphScope, LinkGraphSearchFilters, LinkGraphSearchOptions, LinkGraphSortField,
    LinkGraphSortOrder, LinkGraphSortTerm, LinkGraphStats,
};
use super::parser::{ParsedNote, ParsedSection, is_supported_note, normalize_alias, parse_note};
use super::query::{ParsedLinkGraphQuery, parse_search_query};
use serde::{Deserialize, Serialize};
mod build;
mod ppr;
mod scoring;
mod search;
mod shared;
mod traversal;
use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

const INCOMING_RANK_FACTOR: f64 = 2.0;
const OUTGOING_RANK_FACTOR: f64 = 1.0;
const MAX_GRAPH_RANK_BOOST: f64 = 0.35;
const WEIGHT_FTS_LEXICAL: f64 = 0.62;
const WEIGHT_FTS_SECTION: f64 = 0.23;
const WEIGHT_FTS_PATH: f64 = 0.15;
const WEIGHT_PATH_FUZZY_PATH: f64 = 0.70;
const WEIGHT_PATH_FUZZY_SECTION: f64 = 0.30;
const INCREMENTAL_REBUILD_THRESHOLD: usize = 256;
const DEFAULT_PER_DOC_SECTION_CAP: usize = 3;
const DEFAULT_MIN_SECTION_WORDS: usize = 24;
const SECTION_AGGREGATION_BETA: f64 = 0.15;

use scoring::{
    normalize_with_case, score_document, score_document_exact, score_document_regex,
    score_path_fields, section_tree_distance, token_match_ratio, tokenize,
};
use shared::{
    ScoredSearchRow, deterministic_random_key, doc_contains_phrase, doc_sort_key,
    normalize_path_filter, path_matches_filter, sort_hits,
};

#[derive(Debug, Clone, Serialize, Deserialize)]
struct IndexedSection {
    heading_path: String,
    heading_path_lower: String,
    heading_level: usize,
    section_text: String,
    section_text_lower: String,
}

impl IndexedSection {
    fn from_parsed(value: &ParsedSection) -> Self {
        Self {
            heading_path: value.heading_path.clone(),
            heading_path_lower: value.heading_path_lower.clone(),
            heading_level: value.heading_level,
            section_text: value.section_text.clone(),
            section_text_lower: value.section_text_lower.clone(),
        }
    }
}

#[derive(Debug, Clone)]
struct SectionMatch {
    score: f64,
    heading_path: Option<String>,
    reason: &'static str,
}

#[derive(Debug, Clone)]
struct SectionCandidate {
    heading_path: String,
    score: f64,
    reason: &'static str,
}

/// Cache build metadata emitted by the Valkey-backed LinkGraph bootstrap.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphCacheBuildMeta {
    /// Cache backend name.
    pub backend: String,
    /// Cache status (`hit` or `miss`).
    pub status: String,
    /// Miss reason when status is `miss`.
    pub miss_reason: Option<String>,
    /// Cache schema version string.
    pub schema_version: String,
    /// Cache schema fingerprint (derived from schema JSON content).
    pub schema_fingerprint: String,
}

/// Fast in-memory markdown link graph index.
#[derive(Debug, Clone)]
pub struct LinkGraphIndex {
    root: PathBuf,
    include_dirs: Vec<String>,
    excluded_dirs: Vec<String>,
    docs_by_id: HashMap<String, LinkGraphDocument>,
    sections_by_doc: HashMap<String, Vec<IndexedSection>>,
    alias_to_doc_id: HashMap<String, String>,
    outgoing: HashMap<String, HashSet<String>>,
    incoming: HashMap<String, HashSet<String>>,
    rank_by_id: HashMap<String, f64>,
    edge_count: usize,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
/// Refresh execution mode selected by LinkGraph incremental refresh logic.
pub enum LinkGraphRefreshMode {
    /// No-op (no changed paths provided).
    Noop,
    /// Apply incremental delta updates.
    Delta,
    /// Run full index rebuild.
    Full,
}

impl LinkGraphIndex {
    /// Default threshold where delta refresh switches to full rebuild.
    #[must_use]
    pub const fn incremental_rebuild_threshold() -> usize {
        INCREMENTAL_REBUILD_THRESHOLD
    }

    /// Notebook root used by this index.
    #[must_use]
    pub fn root(&self) -> &Path {
        &self.root
    }

    fn resolve_doc_id(&self, stem_or_id: &str) -> Option<&str> {
        let key = normalize_alias(stem_or_id);
        self.alias_to_doc_id.get(&key).map(String::as_str)
    }

    fn resolve_doc_ids(&self, values: &[String]) -> HashSet<String> {
        values
            .iter()
            .filter_map(|value| self.resolve_doc_id(value))
            .map(str::to_string)
            .collect()
    }

    fn all_doc_ids(&self) -> HashSet<String> {
        self.docs_by_id.keys().cloned().collect()
    }

    fn compute_rank_by_id(
        docs_by_id: &HashMap<String, LinkGraphDocument>,
        incoming: &HashMap<String, HashSet<String>>,
        outgoing: &HashMap<String, HashSet<String>>,
    ) -> HashMap<String, f64> {
        let mut raw_scores: HashMap<String, f64> = HashMap::with_capacity(docs_by_id.len());
        let mut max_raw = 0.0_f64;

        for doc_id in docs_by_id.keys() {
            let incoming_degree = incoming.get(doc_id).map_or(0_usize, HashSet::len) as f64;
            let outgoing_degree = outgoing.get(doc_id).map_or(0_usize, HashSet::len) as f64;
            let raw = (incoming_degree * INCOMING_RANK_FACTOR
                + outgoing_degree * OUTGOING_RANK_FACTOR)
                .ln_1p();
            max_raw = max_raw.max(raw);
            raw_scores.insert(doc_id.clone(), raw);
        }

        if max_raw > 0.0 {
            for value in raw_scores.values_mut() {
                *value /= max_raw;
            }
        }

        raw_scores
    }

    fn graph_rank(&self, doc_id: &str) -> f64 {
        self.rank_by_id.get(doc_id).copied().unwrap_or(0.0)
    }

    fn apply_graph_rank_boost(&self, doc_id: &str, score: f64) -> f64 {
        let rank = self.graph_rank(doc_id);
        if rank <= 0.0 {
            return score.clamp(0.0, 1.0);
        }
        let bounded = score.clamp(0.0, 1.0);
        (bounded + (1.0 - bounded) * rank * MAX_GRAPH_RANK_BOOST).clamp(0.0, 1.0)
    }
}
