"""Common link-graph engine contract and adapters."""

from .backend import (
    LinkGraphBackend,
)
from .factory import get_link_graph_backend, reset_link_graph_backend_cache
from .models import (
    LinkGraphDirection,
    LinkGraphHit,
    LinkGraphMatchStrategy,
    LinkGraphMetadata,
    LinkGraphNeighbor,
    LinkGraphSearchOptions,
)
from .policy import (
    LinkGraphConfidenceLevel,
    LinkGraphPolicyConfig,
    LinkGraphRetrievalBudget,
    LinkGraphRetrievalMode,
    LinkGraphRetrievalPlan,
    LinkGraphSourceHint,
    fetch_graph_rows_by_policy,
    get_link_graph_retrieval_plan_schema_id,
    note_recent_graph_search_timeout,
    plan_link_graph_retrieval,
    resolve_link_graph_policy_config,
    serialize_link_graph_retrieval_plan,
    take_recent_graph_search_timeout,
)
from .proximity import apply_link_graph_proximity_boost
from .recall_policy import LinkGraphRecallPolicyDecision, evaluate_link_graph_recall_policy
from .search_results import (
    link_graph_hits_to_hybrid_results,
    link_graph_hits_to_search_results,
    merge_hybrid_results,
    neighbors_to_link_rows,
    normalize_link_graph_direction,
    vector_rows_to_hybrid_results,
)
from .stats_cache import (
    clear_link_graph_stats_cache,
    get_cached_link_graph_stats,
    get_link_graph_stats_for_response,
    schedule_link_graph_stats_refresh,
)
from .wendao_backend import WendaoLinkGraphBackend

__all__ = [
    "LinkGraphBackend",
    "LinkGraphConfidenceLevel",
    "LinkGraphDirection",
    "LinkGraphHit",
    "LinkGraphMatchStrategy",
    "LinkGraphMetadata",
    "LinkGraphNeighbor",
    "LinkGraphPolicyConfig",
    "LinkGraphRecallPolicyDecision",
    "LinkGraphRetrievalBudget",
    "LinkGraphRetrievalMode",
    "LinkGraphRetrievalPlan",
    "LinkGraphSearchOptions",
    "LinkGraphSourceHint",
    "WendaoLinkGraphBackend",
    "apply_link_graph_proximity_boost",
    "clear_link_graph_stats_cache",
    "evaluate_link_graph_recall_policy",
    "fetch_graph_rows_by_policy",
    "get_cached_link_graph_stats",
    "get_link_graph_backend",
    "get_link_graph_retrieval_plan_schema_id",
    "get_link_graph_stats_for_response",
    "link_graph_hits_to_hybrid_results",
    "link_graph_hits_to_search_results",
    "merge_hybrid_results",
    "neighbors_to_link_rows",
    "normalize_link_graph_direction",
    "note_recent_graph_search_timeout",
    "plan_link_graph_retrieval",
    "reset_link_graph_backend_cache",
    "resolve_link_graph_policy_config",
    "schedule_link_graph_stats_refresh",
    "serialize_link_graph_retrieval_plan",
    "take_recent_graph_search_timeout",
    "vector_rows_to_hybrid_results",
]
