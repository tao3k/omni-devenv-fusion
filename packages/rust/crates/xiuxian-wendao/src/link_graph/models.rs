//! Shared models for markdown link-graph indexing and retrieval.

use serde::{Deserialize, Serialize};

/// Neighbor direction relative to the queried note.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LinkGraphDirection {
    /// Points to current note.
    Incoming,
    /// Referenced by current note.
    Outgoing,
    /// Reachable from both sides.
    Both,
}

impl LinkGraphDirection {
    /// Parse direction aliases from user/runtime input.
    #[must_use]
    pub fn from_alias(raw: &str) -> Self {
        match raw.trim().to_lowercase().as_str() {
            "to" | "incoming" => Self::Incoming,
            "from" | "outgoing" => Self::Outgoing,
            _ => Self::Both,
        }
    }
}

/// Search strategy used by link-graph search.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LinkGraphMatchStrategy {
    /// Default lexical ranking (token/substring aware).
    Fts,
    /// Path + heading fuzzy ranking (structure-aware).
    #[serde(rename = "path_fuzzy")]
    PathFuzzy,
    /// Exact match on id/stem/title/path/tag.
    Exact,
    /// Regex match on id/stem/title/path/tag.
    Re,
}

impl LinkGraphMatchStrategy {
    /// Parse strategy aliases from user/runtime input.
    #[must_use]
    pub fn from_alias(raw: &str) -> Self {
        match raw.trim().to_lowercase().as_str() {
            "path_fuzzy" | "path-fuzzy" | "pathfuzzy" | "fuzzy" => Self::PathFuzzy,
            "exact" => Self::Exact,
            "re" | "regex" => Self::Re,
            _ => Self::Fts,
        }
    }
}

/// Schema-first sort field.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LinkGraphSortField {
    Score,
    Path,
    Title,
    Stem,
    Created,
    Modified,
    Random,
    WordCount,
}

/// Schema-first sort order.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum LinkGraphSortOrder {
    Asc,
    Desc,
}

/// One sort term (field + order).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphSortTerm {
    pub field: LinkGraphSortField,
    pub order: LinkGraphSortOrder,
}

impl Default for LinkGraphSortTerm {
    fn default() -> Self {
        Self {
            field: LinkGraphSortField::Score,
            order: LinkGraphSortOrder::Desc,
        }
    }
}

/// Boolean tag filter.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphTagFilter {
    #[serde(default)]
    pub all: Vec<String>,
    #[serde(default)]
    pub any: Vec<String>,
    #[serde(default, rename = "not")]
    pub not_tags: Vec<String>,
}

/// Link filter for link_to/linked_by.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphLinkFilter {
    #[serde(default)]
    pub seeds: Vec<String>,
    #[serde(default)]
    pub negate: bool,
    #[serde(default)]
    pub recursive: bool,
    #[serde(default)]
    pub max_distance: Option<usize>,
}

/// Related filter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LinkGraphPprSubgraphMode {
    Auto,
    Disabled,
    Force,
}

/// PPR tuning options for related retrieval.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphRelatedPprOptions {
    #[serde(default)]
    pub alpha: Option<f64>,
    #[serde(default)]
    pub max_iter: Option<usize>,
    #[serde(default)]
    pub tol: Option<f64>,
    #[serde(default)]
    pub subgraph_mode: Option<LinkGraphPprSubgraphMode>,
}

/// Related filter.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphRelatedFilter {
    #[serde(default)]
    pub seeds: Vec<String>,
    #[serde(default)]
    pub max_distance: Option<usize>,
    #[serde(default)]
    pub ppr: Option<LinkGraphRelatedPprOptions>,
}

/// Result scope for doc/section level retrieval.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LinkGraphScope {
    DocOnly,
    SectionOnly,
    Mixed,
}

/// Edge type filters for tree-aware traversal/ranking.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LinkGraphEdgeType {
    Structural,
    Semantic,
    Provisional,
    Verified,
}

/// Structured search filters.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphSearchFilters {
    #[serde(default)]
    pub include_paths: Vec<String>,
    #[serde(default)]
    pub exclude_paths: Vec<String>,
    #[serde(default)]
    pub tags: Option<LinkGraphTagFilter>,
    #[serde(default)]
    pub link_to: Option<LinkGraphLinkFilter>,
    #[serde(default)]
    pub linked_by: Option<LinkGraphLinkFilter>,
    #[serde(default)]
    pub related: Option<LinkGraphRelatedFilter>,
    #[serde(default)]
    pub mentions_of: Vec<String>,
    #[serde(default)]
    pub mentioned_by_notes: Vec<String>,
    #[serde(default)]
    pub orphan: bool,
    #[serde(default)]
    pub tagless: bool,
    #[serde(default)]
    pub missing_backlink: bool,
    #[serde(default)]
    pub scope: Option<LinkGraphScope>,
    #[serde(default)]
    pub max_heading_level: Option<usize>,
    #[serde(default)]
    pub max_tree_hops: Option<usize>,
    #[serde(default)]
    pub collapse_to_doc: Option<bool>,
    #[serde(default)]
    pub edge_types: Vec<LinkGraphEdgeType>,
    #[serde(default)]
    pub per_doc_section_cap: Option<usize>,
    #[serde(default)]
    pub min_section_words: Option<usize>,
}

/// Search options for link-graph index retrieval.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LinkGraphSearchOptions {
    /// Matching strategy (fts/exact/re).
    pub match_strategy: LinkGraphMatchStrategy,
    /// Whether matching is case-sensitive.
    pub case_sensitive: bool,
    /// Result ordering terms (priority order).
    #[serde(default)]
    pub sort_terms: Vec<LinkGraphSortTerm>,
    /// Structured filters.
    #[serde(default)]
    pub filters: LinkGraphSearchFilters,
    /// Keep rows with `created_ts >= created_after`.
    #[serde(default)]
    pub created_after: Option<i64>,
    /// Keep rows with `created_ts <= created_before`.
    #[serde(default)]
    pub created_before: Option<i64>,
    /// Keep rows with `modified_ts >= modified_after`.
    #[serde(default)]
    pub modified_after: Option<i64>,
    /// Keep rows with `modified_ts <= modified_before`.
    #[serde(default)]
    pub modified_before: Option<i64>,
}

impl Default for LinkGraphSearchOptions {
    fn default() -> Self {
        Self {
            match_strategy: LinkGraphMatchStrategy::Fts,
            case_sensitive: false,
            sort_terms: vec![LinkGraphSortTerm::default()],
            filters: LinkGraphSearchFilters::default(),
            created_after: None,
            created_before: None,
            modified_after: None,
            modified_before: None,
        }
    }
}

impl LinkGraphSearchOptions {
    /// Validate schema-equivalent constraints for runtime safety.
    pub fn validate(&self) -> Result<(), String> {
        if let Some(filter) = &self.filters.link_to
            && filter.max_distance.is_some_and(|distance| distance == 0)
        {
            return Err(
                "link_graph search options schema violation at filters.link_to.max_distance: must be >= 1"
                    .to_string(),
            );
        }
        if let Some(filter) = &self.filters.linked_by
            && filter.max_distance.is_some_and(|distance| distance == 0)
        {
            return Err(
                "link_graph search options schema violation at filters.linked_by.max_distance: must be >= 1"
                    .to_string(),
            );
        }
        if let Some(filter) = &self.filters.related
            && filter.max_distance.is_some_and(|distance| distance == 0)
        {
            return Err(
                "link_graph search options schema violation at filters.related.max_distance: must be >= 1"
                    .to_string(),
            );
        }
        if let Some(filter) = &self.filters.related
            && let Some(ppr) = &filter.ppr
        {
            if let Some(alpha) = ppr.alpha
                && !(0.0..=1.0).contains(&alpha)
            {
                return Err(
                    "link_graph search options schema violation at filters.related.ppr.alpha: must be between 0 and 1"
                        .to_string(),
                );
            }
            if let Some(max_iter) = ppr.max_iter
                && max_iter == 0
            {
                return Err(
                    "link_graph search options schema violation at filters.related.ppr.max_iter: must be >= 1"
                        .to_string(),
                );
            }
            if let Some(tol) = ppr.tol
                && tol <= 0.0
            {
                return Err(
                    "link_graph search options schema violation at filters.related.ppr.tol: must be > 0"
                        .to_string(),
                );
            }
        }
        if let Some(level) = self.filters.max_heading_level
            && !(1..=6).contains(&level)
        {
            return Err(
                "link_graph search options schema violation at filters.max_heading_level: must be between 1 and 6"
                    .to_string(),
            );
        }
        if let Some(cap) = self.filters.per_doc_section_cap
            && cap == 0
        {
            return Err(
                "link_graph search options schema violation at filters.per_doc_section_cap: must be >= 1"
                    .to_string(),
            );
        }
        Ok(())
    }
}

fn default_doc_saliency_base() -> f64 {
    crate::link_graph::saliency::DEFAULT_SALIENCY_BASE
}

fn default_doc_decay_rate() -> f64 {
    crate::link_graph::saliency::DEFAULT_DECAY_RATE
}

/// Indexed document row.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphDocument {
    /// Canonical ID (relative path without extension, '/' separator).
    pub id: String,
    /// Lowercased canonical ID for case-insensitive matching.
    #[serde(skip_serializing, default)]
    pub id_lower: String,
    /// File stem (basename without extension).
    pub stem: String,
    /// Lowercased file stem for case-insensitive matching.
    #[serde(skip_serializing, default)]
    pub stem_lower: String,
    /// Relative path with extension.
    pub path: String,
    /// Lowercased relative path for case-insensitive matching.
    #[serde(skip_serializing, default)]
    pub path_lower: String,
    /// Best-effort title.
    pub title: String,
    /// Lowercased title for case-insensitive matching.
    #[serde(skip_serializing, default)]
    pub title_lower: String,
    /// Best-effort tags.
    pub tags: Vec<String>,
    /// Lowercased tags for case-insensitive matching.
    #[serde(skip_serializing, default)]
    pub tags_lower: Vec<String>,
    /// Best-effort leading content snippet.
    pub lead: String,
    /// Best-effort word count of body.
    #[serde(default)]
    pub word_count: usize,
    /// Searchable markdown content without frontmatter.
    #[serde(skip_serializing, default)]
    pub search_text: String,
    /// Lowercased searchable content for case-insensitive matching.
    #[serde(skip_serializing, default)]
    pub search_text_lower: String,
    /// Initial saliency baseline extracted from frontmatter (`saliency_base`).
    #[serde(default = "default_doc_saliency_base")]
    pub saliency_base: f64,
    /// Initial saliency decay rate extracted from frontmatter (`decay_rate`).
    #[serde(default = "default_doc_decay_rate")]
    pub decay_rate: f64,
    /// Best-effort created timestamp in Unix seconds.
    pub created_ts: Option<i64>,
    /// Best-effort modified timestamp in Unix seconds.
    pub modified_ts: Option<i64>,
}

/// Search hit.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphHit {
    /// Stem identifier.
    pub stem: String,
    /// Optional title.
    pub title: String,
    /// Relative path.
    pub path: String,
    /// Relevance score (0-1).
    pub score: f64,
    /// Best-matching section/heading path when available.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub best_section: Option<String>,
    /// Human-readable match reason for debugging/observability.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub match_reason: Option<String>,
}

/// Display-friendly search hit for external payload contracts.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphDisplayHit {
    /// Stem identifier.
    pub stem: String,
    /// Optional title.
    pub title: String,
    /// Relative path.
    pub path: String,
    /// Relevance score (0-1).
    pub score: f64,
    /// Best-matching section/heading path (empty when unavailable).
    pub best_section: String,
    /// Human-readable match reason (empty when unavailable).
    pub match_reason: String,
}

impl From<&LinkGraphHit> for LinkGraphDisplayHit {
    fn from(value: &LinkGraphHit) -> Self {
        Self {
            stem: value.stem.clone(),
            title: value.title.clone(),
            path: value.path.clone(),
            score: value.score.max(0.0),
            best_section: value.best_section.clone().unwrap_or_default(),
            match_reason: value.match_reason.clone().unwrap_or_default(),
        }
    }
}

/// Canonical planned-search payload used by CLI/bindings.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphPlannedSearchPayload {
    /// Parsed/normalized query after directive extraction.
    pub query: String,
    /// Effective search options used during execution.
    pub options: LinkGraphSearchOptions,
    /// Display-ready hits.
    pub hits: Vec<LinkGraphDisplayHit>,
    /// Number of matched rows before external truncation.
    pub hit_count: usize,
    /// Number of hits that matched at section/heading level.
    pub section_hit_count: usize,
    /// Raw hit rows for backward compatibility.
    pub results: Vec<LinkGraphHit>,
}

/// Neighbor row for link traversal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphNeighbor {
    /// Stem identifier.
    pub stem: String,
    /// Relative direction to queried note.
    pub direction: LinkGraphDirection,
    /// Hop distance from queried note.
    pub distance: usize,
    /// Optional title.
    pub title: String,
    /// Relative path.
    pub path: String,
}

/// Debug/observability diagnostics for related PPR retrieval.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct LinkGraphRelatedPprDiagnostics {
    /// Effective restart probability for PPR walk.
    pub alpha: f64,
    /// Effective max iteration cap.
    pub max_iter: usize,
    /// Effective convergence tolerance.
    pub tol: f64,
    /// Iterations actually executed.
    pub iteration_count: usize,
    /// Final L1 residual at convergence stop.
    pub final_residual: f64,
    /// Candidate count in bounded horizon (excluding seed notes).
    pub candidate_count: usize,
    /// Graph node count used by the PPR computation.
    pub graph_node_count: usize,
    /// Number of subgraph kernels executed before score fusion.
    pub subgraph_count: usize,
    /// Largest partition node count used by the subgraph kernels.
    pub partition_max_node_count: usize,
    /// Smallest partition node count used by the subgraph kernels.
    pub partition_min_node_count: usize,
    /// Average partition node count used by the subgraph kernels.
    pub partition_avg_node_count: f64,
    /// End-to-end related PPR compute duration in milliseconds.
    pub total_duration_ms: f64,
    /// Subgraph partition build duration in milliseconds.
    pub partition_duration_ms: f64,
    /// PPR kernel execution duration in milliseconds.
    pub kernel_duration_ms: f64,
    /// Score fusion duration in milliseconds.
    pub fusion_duration_ms: f64,
    /// Effective subgraph mode used by runtime.
    pub subgraph_mode: LinkGraphPprSubgraphMode,
    /// Whether computation restricted to bounded horizon subgraph.
    pub horizon_restricted: bool,
}

/// Metadata row.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LinkGraphMetadata {
    /// Stem identifier.
    pub stem: String,
    /// Optional title.
    pub title: String,
    /// Relative path.
    pub path: String,
    /// Tag list.
    pub tags: Vec<String>,
}

/// Summary stats.
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct LinkGraphStats {
    /// Total indexed notes.
    pub total_notes: usize,
    /// Notes with no incoming/outgoing links.
    pub orphans: usize,
    /// Total directed links.
    pub links_in_graph: usize,
    /// Total graph nodes.
    pub nodes_in_graph: usize,
}
