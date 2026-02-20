"""Common graph-first retrieval policy for LinkGraph + vector stores."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from omni.foundation.api.link_graph_policy_schema import build_plan_record
from omni.foundation.config.link_graph_runtime import (
    get_link_graph_candidate_multiplier,
    get_link_graph_graph_rows_per_source,
    get_link_graph_hybrid_min_hits,
    get_link_graph_hybrid_min_top_score,
    get_link_graph_max_sources,
    get_link_graph_policy_cache_ttl_seconds,
    get_link_graph_policy_search_timeout_scale,
    get_link_graph_policy_search_timeout_seconds,
    get_link_graph_policy_timeout_marker_ttl_seconds,
    get_link_graph_retrieval_mode,
)
from omni.foundation.config.settings import get_setting
from omni.foundation.runtime.skills_monitor.phase import (
    build_memory_delta_fields,
    sample_memory,
    start_phase_sample,
)

from .factory import get_link_graph_backend

if TYPE_CHECKING:
    from .models import LinkGraphHit

LinkGraphRetrievalMode = Literal["graph_only", "hybrid", "vector_only"]
LinkGraphConfidenceLevel = Literal["none", "low", "medium", "high"]
_VALID_MODES = {"graph_only", "hybrid", "vector_only"}
_PLAN_CACHE: dict[
    tuple[str, str, int, int, int, float, int, int, str], tuple[LinkGraphRetrievalPlan, float]
] = {}
_RECENT_GRAPH_SEARCH_TIMEOUTS: dict[str, float] = {}
_SLUG_LIKE_QUERY_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_WORD_RE = re.compile(r"[a-zA-Z\u4e00-\u9fff0-9]+")


@dataclass(frozen=True, slots=True)
class LinkGraphPolicyConfig:
    """Policy thresholds and limits shared across skills."""

    mode: LinkGraphRetrievalMode = "hybrid"
    candidate_multiplier: int = 4
    max_sources: int = 8
    min_graph_hits: int = 2
    min_graph_score: float = 0.25
    graph_rows_per_source: int = 8


@dataclass(frozen=True, slots=True)
class LinkGraphSourceHint:
    """Source filter candidate derived from one graph hit."""

    source_filter: str
    stem: str
    graph_score: float


@dataclass(frozen=True, slots=True)
class LinkGraphRetrievalBudget:
    """Budget constraints applied while planning retrieval."""

    candidate_limit: int
    max_sources: int
    rows_per_source: int

    def to_record(self) -> dict[str, int]:
        return {
            "candidate_limit": max(1, int(self.candidate_limit)),
            "max_sources": max(1, int(self.max_sources)),
            "rows_per_source": max(1, int(self.rows_per_source)),
        }


def _default_retrieval_budget() -> LinkGraphRetrievalBudget:
    return LinkGraphRetrievalBudget(candidate_limit=1, max_sources=1, rows_per_source=1)


@dataclass(frozen=True, slots=True)
class LinkGraphRetrievalPlan:
    """Decision made by graph/vector policy router."""

    requested_mode: LinkGraphRetrievalMode
    selected_mode: LinkGraphRetrievalMode
    reason: str
    backend_name: str = "unknown"
    graph_hits: tuple[LinkGraphHit, ...] = ()
    source_hints: tuple[LinkGraphSourceHint, ...] = ()
    graph_confidence_score: float = 0.0
    graph_confidence_level: LinkGraphConfidenceLevel = "none"
    budget: LinkGraphRetrievalBudget = field(default_factory=_default_retrieval_budget)

    def to_record(self) -> dict[str, Any]:
        """Convert to canonical shared-schema retrieval plan payload."""
        budget = self.budget.to_record()
        return build_plan_record(
            requested_mode=self.requested_mode,
            selected_mode=self.selected_mode,
            reason=self.reason,
            backend_name=self.backend_name or "unknown",
            graph_hit_count=len(self.graph_hits),
            source_hint_count=len(self.source_hints),
            graph_confidence_score=max(0.0, min(1.0, float(self.graph_confidence_score))),
            graph_confidence_level=self.graph_confidence_level,
            budget_candidate_limit=budget["candidate_limit"],
            budget_max_sources=budget["max_sources"],
            budget_rows_per_source=budget["rows_per_source"],
        )


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record monitor phase when skills monitor is active."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        return None


def _parse_mode(raw: Any, *, default: LinkGraphRetrievalMode) -> LinkGraphRetrievalMode:
    value = str(raw or "").strip().lower()
    return cast("LinkGraphRetrievalMode", value) if value in _VALID_MODES else default


def _parse_int(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _parse_float(raw: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _policy_cache_ttl_seconds() -> float:
    return get_link_graph_policy_cache_ttl_seconds(
        setting_reader=get_setting,
    )


def _query_timeout_bucket(query: str) -> str:
    text = str(query or "").strip()
    if not text:
        return "empty"
    lowered = text.lower()
    words = _WORD_RE.findall(lowered)
    digit_count = sum(1 for c in lowered if c.isdigit())
    punct_count = sum(1 for c in lowered if not c.isalnum() and not c.isspace())

    if _SLUG_LIKE_QUERY_RE.fullmatch(lowered):
        segment_count = len([seg for seg in re.split(r"[_-]+", lowered) if seg])
        if digit_count > 0 or segment_count >= 4 or len(lowered) >= 24:
            return "machine_like"

    if words and len(words) <= 2 and len(lowered) <= 16:
        return "short"

    if len(lowered) >= 80 or len(words) >= 10:
        return "long_natural"

    if punct_count > max(3, len(lowered) // 4):
        return "symbol_heavy"

    return "normal"


def _policy_search_timeout_scale(query: str, backend_name: str) -> tuple[float, str]:
    del backend_name
    bucket = _query_timeout_bucket(query)
    if bucket == "empty":
        return 0.2, bucket
    scale = get_link_graph_policy_search_timeout_scale(
        bucket,
        setting_reader=get_setting,
    )
    return scale, bucket


def _policy_search_timeout_seconds(backend_name: str, query: str) -> tuple[float, str]:
    base_timeout = get_link_graph_policy_search_timeout_seconds(
        setting_reader=get_setting,
    )
    scale, bucket = _policy_search_timeout_scale(query, backend_name)
    timeout_s = max(0.02, min(30.0, float(base_timeout) * float(scale)))
    return timeout_s, bucket


def _looks_path_like_query(query: str) -> bool:
    lowered = str(query or "").strip().lower()
    if not lowered:
        return False
    if "/" in lowered or "\\" in lowered:
        return True
    return lowered.endswith(".md") or lowered.endswith(".mdx") or lowered.endswith(".markdown")


def _policy_search_options_for_bucket(query_bucket: str, query: str):
    from .models import LinkGraphSearchOptions

    if _looks_path_like_query(query):
        return LinkGraphSearchOptions(
            match_strategy="path_fuzzy",
            case_sensitive=False,
        )
    if query_bucket == "machine_like":
        return LinkGraphSearchOptions(
            match_strategy="exact",
            case_sensitive=False,
        )
    return LinkGraphSearchOptions(
        match_strategy="fts",
        case_sensitive=False,
    )


async def _search_planned(
    backend_obj: Any,
    *,
    query: str,
    limit: int,
    options: Any,
) -> dict[str, Any]:
    payload = await backend_obj.search_planned(query, limit=limit, options=options)
    if not isinstance(payload, dict):
        raise RuntimeError("link_graph policy search contract violation: expected object payload")
    hits = payload.get("hits")
    if not isinstance(hits, list):
        raise RuntimeError("link_graph policy search contract violation: expected `hits` list")
    return payload


def _graph_timeout_marker_ttl_seconds() -> float:
    return get_link_graph_policy_timeout_marker_ttl_seconds(
        setting_reader=get_setting,
    )


def _normalize_timeout_query(query: str) -> str:
    return str(query or "").strip().lower()


def _cleanup_graph_timeout_markers() -> None:
    if not _RECENT_GRAPH_SEARCH_TIMEOUTS:
        return
    now = time.monotonic()
    expired_keys = [k for k, expires in _RECENT_GRAPH_SEARCH_TIMEOUTS.items() if now >= expires]
    for key in expired_keys:
        _RECENT_GRAPH_SEARCH_TIMEOUTS.pop(key, None)


def note_recent_graph_search_timeout(query: str) -> None:
    """Record a recent graph search timeout for same-query fallback coordination."""
    key = _normalize_timeout_query(query)
    if not key:
        return
    ttl_s = _graph_timeout_marker_ttl_seconds()
    if ttl_s <= 0:
        return
    _cleanup_graph_timeout_markers()
    _RECENT_GRAPH_SEARCH_TIMEOUTS[key] = time.monotonic() + ttl_s


def take_recent_graph_search_timeout(query: str) -> bool:
    """Consume one timeout marker for query, if still valid."""
    key = _normalize_timeout_query(query)
    if not key:
        return False
    expires_at = _RECENT_GRAPH_SEARCH_TIMEOUTS.get(key)
    if expires_at is None:
        return False
    if time.monotonic() >= expires_at:
        _RECENT_GRAPH_SEARCH_TIMEOUTS.pop(key, None)
        return False
    _RECENT_GRAPH_SEARCH_TIMEOUTS.pop(key, None)
    return True


def _cache_key(
    *,
    backend_name: str,
    limit: int,
    config: LinkGraphPolicyConfig,
) -> tuple[str, str, int, int, int, float, int, int]:
    return (
        str(backend_name or "unknown"),
        str(config.mode),
        max(1, int(limit)),
        max(1, int(config.candidate_multiplier)),
        max(1, int(config.min_graph_hits)),
        max(0.0, float(config.min_graph_score)),
        max(1, int(config.max_sources)),
        max(1, int(config.graph_rows_per_source)),
    )


def _cache_query(query: str) -> str:
    return str(query or "").strip().lower()


def _cache_get(
    key: tuple[str, str, int, int, int, float, int, int],
    *,
    query: str,
) -> LinkGraphRetrievalPlan | None:
    ttl_s = _policy_cache_ttl_seconds()
    if ttl_s <= 0:
        return None
    now = time.monotonic()
    cache_key = (
        key[0],
        key[1],
        key[2],
        key[3],
        key[4],
        key[5],
        key[6],
        key[7],
        _cache_query(query),
    )
    cached = _PLAN_CACHE.get(cache_key)
    if not cached:
        _record_phase("link_graph.policy.cache", 0.0, hit=False, size=len(_PLAN_CACHE))
        return None
    plan, expires_at = cached
    if now >= expires_at:
        _PLAN_CACHE.pop(cache_key, None)
        _record_phase(
            "link_graph.policy.cache", 0.0, hit=False, expired=True, size=len(_PLAN_CACHE)
        )
        return None
    _record_phase("link_graph.policy.cache", 0.0, hit=True, size=len(_PLAN_CACHE))
    return plan


def _cache_put(
    key: tuple[str, str, int, int, int, float, int, int],
    *,
    query: str,
    plan: LinkGraphRetrievalPlan,
) -> None:
    ttl_s = _policy_cache_ttl_seconds()
    if ttl_s <= 0:
        return
    cache_key = (
        key[0],
        key[1],
        key[2],
        key[3],
        key[4],
        key[5],
        key[6],
        key[7],
        _cache_query(query),
    )
    _PLAN_CACHE[cache_key] = (plan, time.monotonic() + ttl_s)


def resolve_link_graph_policy_config(
    *,
    mode: str | None = None,
) -> LinkGraphPolicyConfig:
    """Load graph retrieval policy from explicit mode + settings."""
    configured_mode = _parse_mode(
        get_link_graph_retrieval_mode(mode, setting_reader=get_setting),
        default="hybrid",
    )
    return LinkGraphPolicyConfig(
        mode=configured_mode,
        candidate_multiplier=get_link_graph_candidate_multiplier(
            setting_reader=get_setting,
        ),
        max_sources=get_link_graph_max_sources(
            setting_reader=get_setting,
        ),
        min_graph_hits=get_link_graph_hybrid_min_hits(
            setting_reader=get_setting,
        ),
        min_graph_score=get_link_graph_hybrid_min_top_score(
            setting_reader=get_setting,
        ),
        graph_rows_per_source=get_link_graph_graph_rows_per_source(
            setting_reader=get_setting,
        ),
    )


def _build_source_hints(
    hits: list[LinkGraphHit],
    *,
    max_sources: int,
) -> list[LinkGraphSourceHint]:
    hints: list[LinkGraphSourceHint] = []
    seen: set[tuple[str, str]] = set()
    for hit in hits:
        stem = str(hit.stem).strip()
        if not stem:
            continue
        score = max(0.0, float(hit.score))
        path = str(hit.path or "").strip()
        source_candidates = []
        if path:
            basename = Path(path).name
            if basename:
                source_candidates.append(basename)
            if path not in source_candidates:
                source_candidates.append(path)
        if stem not in source_candidates:
            source_candidates.append(stem)

        for source_filter in source_candidates:
            key = (source_filter, stem)
            if key in seen:
                continue
            seen.add(key)
            hints.append(
                LinkGraphSourceHint(
                    source_filter=source_filter,
                    stem=stem,
                    graph_score=score,
                )
            )
            if len(hints) >= max_sources:
                return hints
    return hints


def _graph_is_sufficient(
    hits: list[LinkGraphHit],
    *,
    min_hits: int,
    min_top_score: float,
) -> bool:
    if not hits:
        return False
    if len(hits) < min_hits:
        return False
    top_score = max(float(h.score) for h in hits)
    return top_score >= min_top_score


def _confidence_level_from_score(score: float) -> LinkGraphConfidenceLevel:
    bounded = max(0.0, min(1.0, float(score)))
    if bounded <= 0.0:
        return "none"
    if bounded < 0.35:
        return "low"
    if bounded < 0.7:
        return "medium"
    return "high"


def _compute_graph_confidence(
    hits: list[LinkGraphHit],
    *,
    min_hits: int,
    min_top_score: float,
) -> tuple[float, LinkGraphConfidenceLevel]:
    if not hits:
        return 0.0, "none"

    count_score = min(1.0, len(hits) / max(1, min_hits))
    top_score = max(0.0, min(1.0, max(float(h.score) for h in hits)))
    threshold_score = min(1.0, top_score / min_top_score) if min_top_score > 0 else top_score
    confidence = max(0.0, min(1.0, 0.45 * count_score + 0.35 * top_score + 0.2 * threshold_score))
    return confidence, _confidence_level_from_score(confidence)


def _build_plan(
    *,
    requested_mode: LinkGraphRetrievalMode,
    selected_mode: LinkGraphRetrievalMode,
    reason: str,
    backend_name: str,
    graph_hits: list[LinkGraphHit] | tuple[LinkGraphHit, ...],
    source_hints: list[LinkGraphSourceHint] | tuple[LinkGraphSourceHint, ...],
    graph_confidence_score: float,
    graph_confidence_level: LinkGraphConfidenceLevel,
    budget: LinkGraphRetrievalBudget,
) -> LinkGraphRetrievalPlan:
    plan = LinkGraphRetrievalPlan(
        requested_mode=requested_mode,
        selected_mode=selected_mode,
        reason=reason,
        backend_name=backend_name or "unknown",
        graph_hits=tuple(graph_hits),
        source_hints=tuple(source_hints),
        graph_confidence_score=max(0.0, min(1.0, float(graph_confidence_score))),
        graph_confidence_level=graph_confidence_level,
        budget=budget,
    )
    # Contract freeze: every plan must conform to shared schema.
    plan.to_record()
    return plan


async def plan_link_graph_retrieval(
    query: str,
    *,
    limit: int,
    mode: str | None = None,
    backend: Any | None = None,
    config: LinkGraphPolicyConfig | None = None,
) -> LinkGraphRetrievalPlan:
    """Plan whether this query should run graph-only or vector fallback."""
    cfg = config or resolve_link_graph_policy_config(mode=mode)
    requested = cfg.mode
    candidate_limit = max(1, int(limit)) * max(1, int(cfg.candidate_multiplier))
    budget = LinkGraphRetrievalBudget(
        candidate_limit=candidate_limit,
        max_sources=max(1, int(cfg.max_sources)),
        rows_per_source=max(1, int(cfg.graph_rows_per_source)),
    )
    if requested == "vector_only":
        return _build_plan(
            requested_mode=requested,
            selected_mode="vector_only",
            reason="vector_only_requested",
            backend_name="policy",
            graph_hits=(),
            source_hints=(),
            graph_confidence_score=0.0,
            graph_confidence_level="none",
            budget=budget,
        )

    started_at, rss_before, rss_peak_before = start_phase_sample()
    backend_obj = backend
    if backend_obj is None:
        try:
            backend_obj = get_link_graph_backend()
        except Exception:
            return _build_plan(
                requested_mode=requested,
                selected_mode="vector_only" if requested == "hybrid" else requested,
                reason="backend_unavailable",
                backend_name="unavailable",
                graph_hits=(),
                source_hints=(),
                graph_confidence_score=0.0,
                graph_confidence_level="none",
                budget=budget,
            )

    backend_name = str(getattr(backend_obj, "backend_name", "unknown") or "unknown")
    cache_key = _cache_key(backend_name=backend_name, limit=limit, config=cfg)
    cached_plan = _cache_get(cache_key, query=query)
    if cached_plan is not None:
        return cached_plan

    search_limit = candidate_limit
    search_timeout_s, query_bucket = _policy_search_timeout_seconds(backend_name, query)
    search_options = _policy_search_options_for_bucket(query_bucket, query)
    search_timed_out = False
    search_payload: dict[str, Any] = {}
    try:
        search_payload = await asyncio.wait_for(
            _search_planned(
                backend_obj,
                query=query,
                limit=search_limit,
                options=search_options,
            ),
            timeout=search_timeout_s,
        )
    except TimeoutError:
        search_payload = {}
        search_timed_out = True
        note_recent_graph_search_timeout(query)
    except Exception:
        search_payload = {}

    raw_hits = search_payload.get("hits")
    hits = raw_hits if isinstance(raw_hits, list) else []
    payload_search_options = search_payload.get("search_options")
    effective_search_options = (
        payload_search_options if isinstance(payload_search_options, dict) else {}
    )
    effective_match_strategy = str(
        effective_search_options.get("match_strategy")
        or getattr(search_options, "match_strategy", "fts")
    )
    parsed_query = str(search_payload.get("query") or query)

    rss_after, rss_peak_after = sample_memory()
    _record_phase(
        "link_graph.policy.search",
        (time.perf_counter() - started_at) * 1000,
        backend=backend_name,
        hits=len(hits),
        timed_out=search_timed_out,
        timeout_s=round(search_timeout_s, 3),
        timeout_bucket=query_bucket,
        match_strategy=effective_match_strategy,
        parsed_query_len=len(parsed_query.strip()),
        requested_mode=requested,
        **build_memory_delta_fields(rss_before, rss_peak_before, rss_after, rss_peak_after),
    )

    source_hints = _build_source_hints(hits, max_sources=max(1, cfg.max_sources))
    confidence_score, confidence_level = _compute_graph_confidence(
        hits,
        min_hits=max(1, cfg.min_graph_hits),
        min_top_score=max(0.0, cfg.min_graph_score),
    )

    if requested == "graph_only":
        if search_timed_out:
            reason = "graph_only_search_timeout"
        else:
            reason = "graph_only_requested" if hits else "graph_only_requested_empty"
        plan = _build_plan(
            requested_mode=requested,
            selected_mode="graph_only",
            reason=reason,
            backend_name=backend_name,
            graph_hits=hits,
            source_hints=source_hints,
            graph_confidence_score=confidence_score,
            graph_confidence_level=confidence_level,
            budget=budget,
        )
        _cache_put(cache_key, query=query, plan=plan)
        return plan

    if _graph_is_sufficient(
        hits,
        min_hits=max(1, cfg.min_graph_hits),
        min_top_score=max(0.0, cfg.min_graph_score),
    ):
        plan = _build_plan(
            requested_mode=requested,
            selected_mode="graph_only",
            reason="graph_sufficient",
            backend_name=backend_name,
            graph_hits=hits,
            source_hints=source_hints,
            graph_confidence_score=confidence_score,
            graph_confidence_level=confidence_level,
            budget=budget,
        )
        _cache_put(cache_key, query=query, plan=plan)
        return plan

    plan = _build_plan(
        requested_mode=requested,
        selected_mode="vector_only",
        reason="graph_search_timeout" if search_timed_out else "graph_insufficient",
        backend_name=backend_name,
        graph_hits=hits,
        source_hints=source_hints,
        graph_confidence_score=confidence_score,
        graph_confidence_level=confidence_level,
        budget=budget,
    )
    _cache_put(cache_key, query=query, plan=plan)
    return plan


def _parse_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    metadata = entry.get("metadata") or {}
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str):
        try:
            obj = json.loads(metadata)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            return {}
    return {}


async def fetch_graph_rows_by_policy(
    *,
    store: Any,
    collection: str,
    source_hints: list[LinkGraphSourceHint],
    limit: int,
    rows_per_source: int,
) -> list[dict[str, Any]]:
    """Fetch chunk rows by graph-derived source candidates."""
    started_at, rss_before, rss_peak_before = start_phase_sample()
    fetch_limit = max(int(limit), 1)
    if not source_hints or not hasattr(store, "list_all"):
        rss_after, rss_peak_after = sample_memory()
        _record_phase(
            "retrieval.rows.graph",
            (time.perf_counter() - started_at) * 1000,
            mode="graph",
            collection=collection,
            fetch_limit=fetch_limit,
            rows_fetched=0,
            rows_parsed=0,
            rows_returned=0,
            rows_capped=0,
            source_hint_count=len(source_hints),
            rows_per_source=max(1, int(rows_per_source)),
            total_cap=max(fetch_limit, 1) * 4,
            **build_memory_delta_fields(rss_before, rss_peak_before, rss_after, rss_peak_after),
        )
        return []

    total_cap = fetch_limit * 4
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    fetched_total = 0
    parsed_total = 0

    for hint in source_hints:
        phase_started = time.perf_counter()
        try:
            entries = await store.list_all(collection, source_filter=hint.source_filter)
        except Exception:
            entries = []
        fetched_total += len(entries)
        _record_phase(
            "link_graph.policy.list_all",
            (time.perf_counter() - phase_started) * 1000,
            source_filter=hint.source_filter,
            rows=len(entries),
        )
        if not entries:
            continue

        accepted = 0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            metadata = _parse_metadata(entry)
            source = str(metadata.get("source") or entry.get("id") or "").strip()
            if not source:
                continue
            stem = Path(source).stem
            if hint.source_filter not in source and stem != hint.stem:
                continue

            raw_chunk_index = metadata.get("chunk_index", -1)
            try:
                chunk_index = int(raw_chunk_index)
            except (TypeError, ValueError):
                chunk_index = -1
            key = (source, chunk_index)
            if key in seen:
                continue
            seen.add(key)
            parsed_total += 1

            out.append(
                {
                    "content": str(entry.get("content", "")),
                    "source": source,
                    "score": max(0.0, hint.graph_score - max(chunk_index, 0) * 0.0001),
                    "title": str(metadata.get("title", "")),
                    "section": str(metadata.get("section", "")),
                }
            )
            accepted += 1
            if accepted >= max(1, rows_per_source):
                break
            if len(out) >= total_cap:
                break

        if len(out) >= total_cap:
            break

    out.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
    final_rows = out[:total_cap]
    rss_after, rss_peak_after = sample_memory()
    _record_phase(
        "retrieval.rows.graph",
        (time.perf_counter() - started_at) * 1000,
        mode="graph",
        collection=collection,
        fetch_limit=fetch_limit,
        rows_fetched=fetched_total,
        rows_parsed=parsed_total,
        rows_returned=len(final_rows),
        rows_capped=max(0, len(out) - len(final_rows)),
        source_hint_count=len(source_hints),
        rows_per_source=max(1, int(rows_per_source)),
        total_cap=total_cap,
        **build_memory_delta_fields(rss_before, rss_peak_before, rss_after, rss_peak_after),
    )
    return final_rows


def _normalize_confidence_level(raw: Any) -> LinkGraphConfidenceLevel:
    value = str(raw or "").strip().lower()
    return (
        cast("LinkGraphConfidenceLevel", value)
        if value in {"none", "low", "medium", "high"}
        else "none"
    )


def get_link_graph_retrieval_plan_schema_id() -> str:
    """Return shared schema `$id` for retrieval-plan payloads."""
    from omni.foundation.api.link_graph_policy_schema import get_schema_id

    return get_schema_id()


def serialize_link_graph_retrieval_plan(plan: Any) -> dict[str, Any] | None:
    """Serialize a retrieval plan object into canonical schema payload."""
    if plan is None:
        return None

    to_record = getattr(plan, "to_record", None)
    if callable(to_record):
        try:
            payload = to_record()
            if isinstance(payload, dict):
                return payload
        except Exception:
            return None

    try:
        requested = _parse_mode(getattr(plan, "requested_mode", None), default="hybrid")
        selected = _parse_mode(getattr(plan, "selected_mode", None), default="vector_only")
        reason = str(getattr(plan, "reason", "unknown") or "unknown")
        backend_name = str(getattr(plan, "backend_name", "unknown") or "unknown")
        graph_hits = tuple(getattr(plan, "graph_hits", ()) or ())
        source_hints = tuple(getattr(plan, "source_hints", ()) or ())
        confidence_score = max(
            0.0,
            min(1.0, float(getattr(plan, "graph_confidence_score", 0.0) or 0.0)),
        )
        confidence_level = _normalize_confidence_level(
            getattr(plan, "graph_confidence_level", "none")
        )

        budget_obj = getattr(plan, "budget", None)
        candidate_limit = _parse_int(
            getattr(budget_obj, "candidate_limit", 1),
            default=1,
            minimum=1,
            maximum=100000,
        )
        max_sources = _parse_int(
            getattr(budget_obj, "max_sources", 1),
            default=1,
            minimum=1,
            maximum=100000,
        )
        rows_per_source = _parse_int(
            getattr(budget_obj, "rows_per_source", 1),
            default=1,
            minimum=1,
            maximum=100000,
        )

        return build_plan_record(
            requested_mode=requested,
            selected_mode=selected,
            reason=reason,
            backend_name=backend_name,
            graph_hit_count=len(graph_hits),
            source_hint_count=len(source_hints),
            graph_confidence_score=confidence_score,
            graph_confidence_level=confidence_level,
            budget_candidate_limit=candidate_limit,
            budget_max_sources=max_sources,
            budget_rows_per_source=rows_per_source,
        )
    except Exception:
        return None


__all__ = [
    "LinkGraphConfidenceLevel",
    "LinkGraphPolicyConfig",
    "LinkGraphRetrievalBudget",
    "LinkGraphRetrievalMode",
    "LinkGraphRetrievalPlan",
    "LinkGraphSourceHint",
    "fetch_graph_rows_by_policy",
    "get_link_graph_retrieval_plan_schema_id",
    "note_recent_graph_search_timeout",
    "plan_link_graph_retrieval",
    "resolve_link_graph_policy_config",
    "serialize_link_graph_retrieval_plan",
    "take_recent_graph_search_timeout",
]
