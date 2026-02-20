//! Markdown link graph index + retrieval algorithms.

mod index;
mod models;
mod parser;
mod query;
mod runtime_config;
pub mod saliency;
mod stats_cache;

pub use index::{LinkGraphCacheBuildMeta, LinkGraphIndex, LinkGraphRefreshMode};
pub use models::{
    LinkGraphDirection, LinkGraphDisplayHit, LinkGraphDocument, LinkGraphEdgeType, LinkGraphHit,
    LinkGraphLinkFilter, LinkGraphMatchStrategy, LinkGraphMetadata, LinkGraphNeighbor,
    LinkGraphPlannedSearchPayload, LinkGraphPprSubgraphMode, LinkGraphRelatedFilter,
    LinkGraphRelatedPprDiagnostics, LinkGraphRelatedPprOptions, LinkGraphScope,
    LinkGraphSearchFilters, LinkGraphSearchOptions, LinkGraphSortField, LinkGraphSortOrder,
    LinkGraphSortTerm, LinkGraphStats, LinkGraphTagFilter,
};
pub use query::{ParsedLinkGraphQuery, parse_search_query};
pub use runtime_config::{
    LinkGraphIndexRuntimeConfig, resolve_link_graph_index_runtime,
    set_link_graph_config_home_override, set_link_graph_wendao_config_override,
};
pub use saliency::{
    LINK_GRAPH_SALIENCY_SCHEMA_VERSION, LinkGraphSaliencyPolicy, LinkGraphSaliencyState,
    LinkGraphSaliencyTouchRequest, compute_link_graph_saliency, valkey_saliency_del,
    valkey_saliency_get, valkey_saliency_get_with_valkey, valkey_saliency_touch,
    valkey_saliency_touch_with_valkey,
};
pub use stats_cache::{
    LINK_GRAPH_STATS_CACHE_SCHEMA_VERSION, valkey_stats_cache_del, valkey_stats_cache_get,
    valkey_stats_cache_set,
};
