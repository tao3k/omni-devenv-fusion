"""Shared aggregation helpers for skills-monitor machine-readable signals."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_retrieval_signals(phases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build retrieval row-budget summary from monitor phase events."""
    if not phases:
        return None

    row_events = [p for p in phases if str(p.get("phase", "")).startswith("retrieval.rows.")]
    if not row_events:
        return None
    query_events = [p for p in row_events if str(p.get("phase", "")) == "retrieval.rows.query"]
    backend_events = [p for p in row_events if str(p.get("phase", "")) != "retrieval.rows.query"]

    total_fetched = 0
    total_parsed = 0
    total_input = 0
    total_returned = 0
    total_capped = 0
    total_parse_dropped = 0
    memory_observed_count = 0
    rss_delta_values: list[float] = []
    rss_peak_delta_values: list[float] = []
    modes: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "count": 0,
            "rows_returned": 0,
            "rows_capped": 0,
        }
    )

    mode_events = query_events if query_events else row_events
    for event in mode_events:
        mode = str(event.get("mode", "unknown") or "unknown")
        modes[mode]["count"] += 1

    for event in backend_events:
        fetched = event.get("rows_fetched")
        if isinstance(fetched, int | float):
            total_fetched += max(0, int(fetched))
        parsed = event.get("rows_parsed")
        if isinstance(parsed, int | float):
            total_parsed += max(0, int(parsed))
        parse_dropped = event.get("rows_parse_dropped")
        if isinstance(parse_dropped, int | float):
            total_parse_dropped += max(0, int(parse_dropped))

    for event in row_events:
        has_memory = False
        rss_delta = event.get("rss_delta_mb")
        if isinstance(rss_delta, int | float):
            rss_delta_values.append(float(rss_delta))
            has_memory = True
        rss_peak_delta = event.get("rss_peak_delta_mb")
        if isinstance(rss_peak_delta, int | float):
            rss_peak_delta_values.append(float(rss_peak_delta))
            has_memory = True
        if has_memory:
            memory_observed_count += 1

    effective_return_events = query_events if query_events else backend_events
    for event in effective_return_events:
        mode = str(event.get("mode", "unknown") or "unknown")
        rows_input = event.get("rows_input")
        if isinstance(rows_input, int | float):
            total_input += max(0, int(rows_input))
        returned = event.get("rows_returned")
        if isinstance(returned, int | float):
            returned_n = max(0, int(returned))
            total_returned += returned_n
            modes[mode]["rows_returned"] += returned_n
        capped = event.get("rows_capped")
        if isinstance(capped, int | float):
            capped_n = max(0, int(capped))
            total_capped += capped_n
            modes[mode]["rows_capped"] += capped_n

    latest = row_events[-1]
    return {
        "row_budget": {
            "count": len(row_events),
            "query_count": len(query_events),
            "backend_count": len(backend_events),
            "rows_fetched_sum": total_fetched,
            "rows_parsed_sum": total_parsed,
            "rows_input_sum": total_input,
            "rows_returned_sum": total_returned,
            "rows_capped_sum": total_capped,
            "rows_parse_dropped_sum": total_parse_dropped,
            "memory": {
                "observed_count": memory_observed_count,
                "rss_delta_sum": (round(sum(rss_delta_values), 2) if rss_delta_values else None),
                "rss_peak_delta_sum": (
                    round(sum(rss_peak_delta_values), 2) if rss_peak_delta_values else None
                ),
                "rss_delta_max": (round(max(rss_delta_values), 2) if rss_delta_values else None),
                "rss_peak_delta_max": (
                    round(max(rss_peak_delta_values), 2) if rss_peak_delta_values else None
                ),
            },
            "modes": dict(sorted(modes.items(), key=lambda kv: kv[0])),
            "latest": {
                "phase": latest.get("phase"),
                "mode": latest.get("mode"),
                "collection": latest.get("collection"),
                "fetch_limit": latest.get("fetch_limit"),
                "rows_fetched": latest.get("rows_fetched"),
                "rows_parsed": latest.get("rows_parsed"),
                "rows_input": latest.get("rows_input"),
                "rows_returned": latest.get("rows_returned"),
                "rows_capped": latest.get("rows_capped"),
                "rows_parse_dropped": latest.get("rows_parse_dropped"),
            },
        }
    }


def build_link_graph_index_refresh_signals(phases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build index refresh summary from LinkGraph index phase events."""
    if not phases:
        return None
    index_plan_events = [
        p for p in phases if str(p.get("phase", "")) == "link_graph.index.delta.plan"
    ]
    index_delta_events = [
        p for p in phases if str(p.get("phase", "")) == "link_graph.index.delta.apply"
    ]
    index_full_events = [
        p for p in phases if str(p.get("phase", "")) == "link_graph.index.rebuild.full"
    ]
    if not index_plan_events and not index_delta_events and not index_full_events:
        return None

    strategies: dict[str, int] = defaultdict(int)
    reasons: dict[str, int] = defaultdict(int)
    plan_force_full_true = 0
    plan_changed_sum = 0
    plan_threshold_values: list[int] = []
    for event in index_plan_events:
        strategy = str(event.get("strategy", "unknown") or "unknown")
        strategies[strategy] += 1
        reason = str(event.get("reason", "unknown") or "unknown")
        reasons[reason] += 1
        if bool(event.get("force_full")):
            plan_force_full_true += 1
        changed_raw = event.get("changed_count")
        if isinstance(changed_raw, int | float):
            plan_changed_sum += max(0, int(changed_raw))
        threshold_raw = event.get("threshold")
        if isinstance(threshold_raw, int | float):
            plan_threshold_values.append(max(0, int(threshold_raw)))

    delta_success = 0
    delta_changed_sum = 0
    for event in index_delta_events:
        if bool(event.get("success")):
            delta_success += 1
        changed_raw = event.get("changed_count")
        if isinstance(changed_raw, int | float):
            delta_changed_sum += max(0, int(changed_raw))

    full_success = 0
    full_reasons: dict[str, int] = defaultdict(int)
    full_changed_sum = 0
    for event in index_full_events:
        if bool(event.get("success")):
            full_success += 1
        reason = str(event.get("reason", "unknown") or "unknown")
        full_reasons[reason] += 1
        changed_raw = event.get("changed_count")
        if isinstance(changed_raw, int | float):
            full_changed_sum += max(0, int(changed_raw))

    latest_plan = (
        max(index_plan_events, key=lambda p: float(p.get("timestamp_s", 0.0) or 0.0))
        if index_plan_events
        else None
    )
    latest_delta = (
        max(index_delta_events, key=lambda p: float(p.get("timestamp_s", 0.0) or 0.0))
        if index_delta_events
        else None
    )
    latest_full = (
        max(index_full_events, key=lambda p: float(p.get("timestamp_s", 0.0) or 0.0))
        if index_full_events
        else None
    )

    return {
        "observed": {
            "total": len(index_plan_events) + len(index_delta_events) + len(index_full_events),
            "plan": len(index_plan_events),
            "delta_apply": len(index_delta_events),
            "full_rebuild": len(index_full_events),
        },
        "plan": {
            "count": len(index_plan_events),
            "strategies": dict(sorted(strategies.items(), key=lambda kv: kv[0])),
            "reasons": dict(sorted(reasons.items(), key=lambda kv: kv[0])),
            "force_full_true": plan_force_full_true,
            "changed_count_sum": plan_changed_sum,
            "threshold": {
                "max": (max(plan_threshold_values) if plan_threshold_values else None),
            },
            "latest": (
                {
                    "strategy": latest_plan.get("strategy"),
                    "reason": latest_plan.get("reason"),
                    "changed_count": latest_plan.get("changed_count"),
                    "threshold": latest_plan.get("threshold"),
                    "force_full": bool(latest_plan.get("force_full")),
                }
                if latest_plan is not None
                else None
            ),
        },
        "delta_apply": {
            "count": len(index_delta_events),
            "success": delta_success,
            "failed": len(index_delta_events) - delta_success,
            "changed_count_sum": delta_changed_sum,
            "latest": (
                {
                    "success": bool(latest_delta.get("success")),
                    "changed_count": latest_delta.get("changed_count"),
                }
                if latest_delta is not None
                else None
            ),
        },
        "full_rebuild": {
            "count": len(index_full_events),
            "success": full_success,
            "failed": len(index_full_events) - full_success,
            "reasons": dict(sorted(full_reasons.items(), key=lambda kv: kv[0])),
            "changed_count_sum": full_changed_sum,
            "latest": (
                {
                    "success": bool(latest_full.get("success")),
                    "reason": latest_full.get("reason"),
                    "changed_count": latest_full.get("changed_count"),
                }
                if latest_full is not None
                else None
            ),
        },
    }


def build_link_graph_signals(phases: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Build machine-readable LinkGraph signal summary from phase events."""
    if not phases:
        return None
    policy_events = [p for p in phases if str(p.get("phase", "")) == "link_graph.policy.search"]
    proximity_events = [
        p for p in phases if str(p.get("phase", "")) == "link_graph.proximity.fetch"
    ]
    index_refresh_signals = build_link_graph_index_refresh_signals(phases)
    graph_stats_events = [
        p
        for p in phases
        if str(p.get("phase", "")) == "skill_command.execute"
        and isinstance(p.get("graph_stats_source"), str)
        and str(p.get("graph_stats_source", "")).strip()
    ]
    if (
        not policy_events
        and not proximity_events
        and not graph_stats_events
        and not index_refresh_signals
    ):
        return None

    payload: dict[str, Any] = {}

    if policy_events:
        buckets: dict[str, int] = defaultdict(int)
        timeout_count = 0
        for event in policy_events:
            bucket = str(event.get("timeout_bucket", "unknown") or "unknown")
            buckets[bucket] += 1
            if bool(event.get("timed_out")):
                timeout_count += 1

        latest_policy = max(policy_events, key=lambda p: float(p.get("timestamp_s", 0.0) or 0.0))
        payload["policy_search"] = {
            "count": len(policy_events),
            "timeouts": timeout_count,
            "buckets": dict(sorted(buckets.items(), key=lambda kv: kv[0])),
            "latest": {
                "timeout_s": latest_policy.get("timeout_s"),
                "timeout_bucket": latest_policy.get("timeout_bucket"),
                "backend": latest_policy.get("backend"),
                "timed_out": bool(latest_policy.get("timed_out")),
            },
        }

    if proximity_events:
        reasons: dict[str, int] = defaultdict(int)
        skipped_count = 0
        timed_out_count = 0
        for event in proximity_events:
            if bool(event.get("skipped")):
                skipped_count += 1
            if bool(event.get("timed_out")):
                timed_out_count += 1
            reason = event.get("reason")
            if isinstance(reason, str) and reason:
                reasons[reason] += 1

        payload["proximity_fetch"] = {
            "count": len(proximity_events),
            "skipped": skipped_count,
            "timed_out": timed_out_count,
            "reasons": dict(sorted(reasons.items(), key=lambda kv: kv[0])),
        }

    if index_refresh_signals:
        payload["index_refresh"] = index_refresh_signals

    if graph_stats_events:
        source_counts: dict[str, int] = defaultdict(int)
        cache_hit_true = 0
        fresh_true = 0
        refresh_scheduled_count = 0
        age_values: list[int] = []
        for event in graph_stats_events:
            source = str(event.get("graph_stats_source", "")).strip() or "unknown"
            source_counts[source] += 1
            if bool(event.get("graph_stats_cache_hit")):
                cache_hit_true += 1
            if bool(event.get("graph_stats_fresh")):
                fresh_true += 1
            if bool(event.get("graph_stats_refresh_scheduled")):
                refresh_scheduled_count += 1
            age_raw = event.get("graph_stats_age_ms")
            if isinstance(age_raw, int | float):
                age_values.append(max(0, int(age_raw)))

        latest = max(graph_stats_events, key=lambda p: float(p.get("timestamp_s", 0.0) or 0.0))
        payload["graph_stats"] = {
            "count": len(graph_stats_events),
            "sources": dict(sorted(source_counts.items(), key=lambda kv: kv[0])),
            "cache_hit_true": cache_hit_true,
            "fresh_true": fresh_true,
            "refresh_scheduled": refresh_scheduled_count,
            "age_ms": {
                "avg": (round(sum(age_values) / len(age_values), 1) if age_values else None),
                "max": (max(age_values) if age_values else None),
            },
            "latest": {
                "source": latest.get("graph_stats_source"),
                "cache_hit": bool(latest.get("graph_stats_cache_hit")),
                "fresh": bool(latest.get("graph_stats_fresh")),
                "age_ms": latest.get("graph_stats_age_ms"),
                "refresh_scheduled": bool(latest.get("graph_stats_refresh_scheduled")),
                "total_notes": latest.get("graph_stats_total_notes"),
            },
        }

    return payload if payload else None


__all__ = [
    "build_link_graph_index_refresh_signals",
    "build_link_graph_signals",
    "build_retrieval_signals",
]
