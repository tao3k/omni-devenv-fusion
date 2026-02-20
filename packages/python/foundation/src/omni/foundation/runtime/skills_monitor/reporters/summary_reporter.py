"""Human-readable summary reporter (stderr)."""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from typing import Any

from .base import Reporter


class SummaryReporter(Reporter):
    """Prints a human-readable summary to stderr."""

    _PHASE_COL_WIDTH = 32
    _TOP_EVENT_DETAIL_KEYS = (
        "function",
        "success",
        "status",
        "reason",
        "source",
        "backend",
        "port",
        "path",
        "attempts",
        "candidate_count",
        "cached_target_present",
        "cached_target_hit",
        "skipped_backoff",
        "negative_cache_size",
        "budget_ms",
        "budget_exhausted",
        "collection",
        "n_results",
        "fetch_limit",
        "rows_fetched",
        "rows_parsed",
        "rows_input",
        "rows_returned",
        "rows_capped",
        "rows_parse_dropped",
        "source_hint_count",
        "rows_per_source",
        "total_cap",
        "command_count",
        "module",
        "reused",
        "target",
        "strategy",
        "changed_count",
        "threshold",
        "force_full",
        "allow_module_reuse",
        "cleared_modules",
        "extension_count",
        "extension_present",
        "active",
        "mode",
        "hit",
        "skipped",
        "scan_duration_ms",
        "workflow",
        "step_index",
        "batch_index",
        "batch_count",
        "timeout_s",
        "timeout_bucket",
        "fetched",
        "stems",
        "max_parallel",
        "neighbor_limit",
        "graph_stats_source",
        "graph_stats_cache_hit",
        "graph_stats_fresh",
        "graph_stats_age_ms",
        "graph_stats_refresh_scheduled",
        "graph_stats_total_notes",
        "cache_schema_version",
        "cache_schema_fingerprint",
        "cache_schema_source",
        "cache_status",
        "cache_miss_reason",
        "schema_version",
        "schema_fingerprint",
        "schema_source",
    )

    def __init__(self, stream: object = sys.stderr) -> None:
        self._stream = stream

    @staticmethod
    def _as_float(value: Any) -> float | None:
        if isinstance(value, int | float):
            return float(value)
        return None

    @staticmethod
    def _fmt_signed(value: float | None) -> str:
        if value is None or math.isnan(value):
            return "-"
        return f"{value:+.1f}"

    @staticmethod
    def _fmt_detail_value(value: Any) -> str:
        if isinstance(value, bool):
            return "True" if value else "False"
        return str(value)

    def _event_details(self, event: dict[str, Any], *, include_tool: bool = False) -> list[str]:
        details: list[str] = []
        if include_tool:
            tool = event.get("tool")
            if isinstance(tool, str) and tool:
                details.append(f"tool={tool}")
        for key in self._TOP_EVENT_DETAIL_KEYS:
            value = event.get(key)
            if value is None:
                continue
            if isinstance(value, str) and not value:
                continue
            details.append(f"{key}={self._fmt_detail_value(value)}")
        return details

    def _emit_overview(self, d: dict[str, Any], *, stream: object) -> None:
        print("Overview:", file=stream)
        print(f"  Command:   {d['skill_command']}", file=stream)
        print(f"  Elapsed:   {d['elapsed_sec']:.2f}s", file=stream)
        rss = d["rss_mb"]
        print(
            f"  RSS(cur):  {rss['start']:.1f} → {rss['end']:.1f} MiB (Δ{rss['delta']:+.1f})",
            file=stream,
        )
        rss_peak = d.get("rss_peak_mb")
        if isinstance(rss_peak, dict):
            print(
                f"  RSS(peak): {rss_peak['start']:.1f} → {rss_peak['end']:.1f} MiB "
                f"(Δ{rss_peak['delta']:+.1f})",
                file=stream,
            )
        if d.get("cpu_avg_percent") is not None:
            print(f"  CPU avg:   {d['cpu_avg_percent']}%", file=stream)

    def _emit_bottlenecks(self, phases: list[dict[str, Any]], *, stream: object) -> None:
        if not phases:
            return
        slowest = max(phases, key=lambda p: float(p.get("duration_ms", 0.0) or 0.0))
        mem_sorted = sorted(
            phases,
            key=lambda p: (
                self._as_float(p.get("rss_delta_mb")) or float("-inf"),
                self._as_float(p.get("rss_peak_delta_mb")) or float("-inf"),
            ),
            reverse=True,
        )
        mem_top = mem_sorted[0]
        print("-" * 60, file=stream)
        print("Bottlenecks:", file=stream)
        print(
            f"  Slowest phase: {slowest['phase']} ({float(slowest.get('duration_ms', 0.0)):.0f}ms)",
            file=stream,
        )
        print(
            "  Largest memory delta: "
            f"{mem_top['phase']} "
            f"(rssΔ={self._fmt_signed(self._as_float(mem_top.get('rss_delta_mb')))} MiB, "
            f"peakΔ={self._fmt_signed(self._as_float(mem_top.get('rss_peak_delta_mb')))} MiB)",
            file=stream,
        )

    def _emit_phase_groups(self, phases: list[dict[str, Any]], *, stream: object) -> None:
        if not phases:
            return
        grouped: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "count": 0.0,
                "total_ms": 0.0,
                "max_ms": 0.0,
                "rss_delta_sum": 0.0,
                "rss_peak_delta_sum": 0.0,
                "has_rss_delta": 0.0,
                "has_rss_peak_delta": 0.0,
            }
        )
        for p in phases:
            phase = str(p.get("phase", "unknown"))
            duration = float(p.get("duration_ms", 0.0) or 0.0)
            g = grouped[phase]
            g["count"] += 1.0
            g["total_ms"] += duration
            g["max_ms"] = max(g["max_ms"], duration)
            rss_delta = self._as_float(p.get("rss_delta_mb"))
            if rss_delta is not None:
                g["rss_delta_sum"] += rss_delta
                g["has_rss_delta"] = 1.0
            peak_delta = self._as_float(p.get("rss_peak_delta_mb"))
            if peak_delta is not None:
                g["rss_peak_delta_sum"] += peak_delta
                g["has_rss_peak_delta"] = 1.0

        groups = sorted(grouped.items(), key=lambda item: item[1]["total_ms"], reverse=True)
        print("-" * 60, file=stream)
        print("Phases (grouped):", file=stream)
        print(
            f"  {'phase':{self._PHASE_COL_WIDTH}}  count  total(ms)  max(ms)  rssΔsum  peakΔsum",
            file=stream,
        )
        for phase, g in groups[:8]:
            rss_sum = g["rss_delta_sum"] if g["has_rss_delta"] else None
            peak_sum = g["rss_peak_delta_sum"] if g["has_rss_peak_delta"] else None
            print(
                f"  {phase[: self._PHASE_COL_WIDTH]:{self._PHASE_COL_WIDTH}}  "
                f"{int(g['count']):5d}  {g['total_ms']:9.0f}  "
                f"{g['max_ms']:7.0f}  {self._fmt_signed(rss_sum):>7}  "
                f"{self._fmt_signed(peak_sum):>8}",
                file=stream,
            )

    def _emit_top_events(self, phases: list[dict[str, Any]], *, stream: object) -> None:
        if not phases:
            return
        top = sorted(phases, key=lambda p: float(p.get("duration_ms", 0.0) or 0.0), reverse=True)
        print("-" * 60, file=stream)
        print("Top Events:", file=stream)
        for p in top[:6]:
            rss_delta = self._as_float(p.get("rss_delta_mb"))
            peak_delta = self._as_float(p.get("rss_peak_delta_mb"))
            details = []
            if rss_delta is not None:
                details.append(f"rssΔ={rss_delta:+.1f}")
            if peak_delta is not None:
                details.append(f"peakΔ={peak_delta:+.1f}")
            details.extend(self._event_details(p, include_tool=True))
            detail_str = f" ({', '.join(details)})" if details else ""
            print(
                f"  {float(p.get('duration_ms', 0.0) or 0.0):7.0f}ms  {p.get('phase', 'unknown')}"
                f"{detail_str}",
                file=stream,
            )

    def _emit_rust_events(self, events: list[dict[str, Any]], *, stream: object) -> None:
        if not events:
            return
        print("-" * 60, file=stream)
        print("Rust/DB events:", file=stream)
        for e in sorted(events, key=lambda x: float(x.get("duration_ms", 0.0)), reverse=True)[:8]:
            coll = f" coll={e.get('collection')}" if e.get("collection") else ""
            n = f" n={e.get('n_results')}" if e.get("n_results") is not None else ""
            print(f"  {e['op']:25} {e['duration_ms']:8.0f}ms{coll}{n}", file=stream)

    @staticmethod
    def _resolve_link_graph_signals(report_payload: dict[str, Any]) -> dict[str, Any] | None:
        signals = report_payload.get("link_graph_signals")
        if isinstance(signals, dict):
            return signals
        return None

    def _emit_link_graph_signals(
        self,
        report_payload: dict[str, Any],
        *,
        stream: object,
    ) -> None:
        signals = self._resolve_link_graph_signals(report_payload)
        if not isinstance(signals, dict):
            return
        policy = signals.get("policy_search")
        proximity = signals.get("proximity_fetch")
        if not isinstance(policy, dict) and not isinstance(proximity, dict):
            return

        print("-" * 60, file=stream)
        print("LinkGraph Signals:", file=stream)

        if isinstance(policy, dict):
            print(
                f"  policy.search: count={policy.get('count', 0)} "
                f"timeouts={policy.get('timeouts', 0)}",
                file=stream,
            )
            buckets = policy.get("buckets")
            if isinstance(buckets, dict) and buckets:
                bucket_summary = ", ".join(
                    f"{bucket}={count}"
                    for bucket, count in sorted(buckets.items(), key=lambda kv: kv[0])
                )
                print(f"  policy.buckets: {bucket_summary}", file=stream)
            latest = policy.get("latest")
            if isinstance(latest, dict):
                latest_timeout = latest.get("timeout_s")
                latest_bucket = latest.get("timeout_bucket")
                if latest_timeout is not None or latest_bucket is not None:
                    timeout_part = (
                        f"{float(latest_timeout):.3f}s"
                        if isinstance(latest_timeout, int | float)
                        else str(latest_timeout)
                    )
                    print(
                        f"  policy.latest: timeout={timeout_part} bucket={latest_bucket}",
                        file=stream,
                    )

        if isinstance(proximity, dict):
            print(
                f"  proximity.fetch: count={proximity.get('count', 0)} "
                f"skipped={proximity.get('skipped', 0)} "
                f"timed_out={proximity.get('timed_out', 0)}",
                file=stream,
            )
            reasons = proximity.get("reasons")
            if isinstance(reasons, dict) and reasons:
                reason_summary = ", ".join(
                    f"{reason}={count}"
                    for reason, count in sorted(reasons.items(), key=lambda kv: kv[0])
                )
                print(f"  proximity.reasons: {reason_summary}", file=stream)

    def _emit_graph_stats_signals(
        self,
        report_payload: dict[str, Any],
        *,
        stream: object,
    ) -> None:
        signals = self._resolve_link_graph_signals(report_payload)
        if not isinstance(signals, dict):
            return
        graph_stats = signals.get("graph_stats")
        if not isinstance(graph_stats, dict):
            return

        print("-" * 60, file=stream)
        print("Graph Stats Signals:", file=stream)
        print(
            f"  observed: count={graph_stats.get('count', 0)} "
            f"refresh_scheduled={graph_stats.get('refresh_scheduled', 0)}",
            file=stream,
        )
        sources = graph_stats.get("sources")
        if isinstance(sources, dict) and sources:
            source_summary = ", ".join(
                f"{source}={count}"
                for source, count in sorted(sources.items(), key=lambda kv: kv[0])
            )
            print(f"  sources: {source_summary}", file=stream)
        count = int(graph_stats.get("count", 0) or 0)
        cache_hit_true = int(graph_stats.get("cache_hit_true", 0) or 0)
        fresh_true = int(graph_stats.get("fresh_true", 0) or 0)
        print(
            f"  cache_hit: true={cache_hit_true} false={max(0, count - cache_hit_true)}",
            file=stream,
        )
        print(
            f"  fresh: true={fresh_true} false={max(0, count - fresh_true)}",
            file=stream,
        )
        age_ms = graph_stats.get("age_ms")
        if isinstance(age_ms, dict) and age_ms.get("avg") is not None:
            print(
                f"  age_ms: avg={age_ms.get('avg')} max={age_ms.get('max')}",
                file=stream,
            )
        latest = graph_stats.get("latest")
        if isinstance(latest, dict):
            print(
                "  latest: "
                f"source={latest.get('source')} "
                f"cache_hit={bool(latest.get('cache_hit'))} "
                f"fresh={bool(latest.get('fresh'))} "
                f"age_ms={latest.get('age_ms')} "
                f"refresh_scheduled={bool(latest.get('refresh_scheduled'))} "
                f"total_notes={latest.get('total_notes')}",
                file=stream,
            )

    def _emit_link_graph_index_signals(
        self,
        report_payload: dict[str, Any],
        *,
        stream: object,
    ) -> None:
        signals = self._resolve_link_graph_signals(report_payload)
        if not isinstance(signals, dict):
            return
        index_signals = signals.get("index_refresh")
        if not isinstance(index_signals, dict):
            return

        observed = index_signals.get("observed")
        plan = index_signals.get("plan")
        delta_apply = index_signals.get("delta_apply")
        full_rebuild = index_signals.get("full_rebuild")

        print("-" * 60, file=stream)
        print("LinkGraph Index Signals:", file=stream)
        if isinstance(observed, dict):
            print(
                "  observed: "
                f"total={observed.get('total', 0)} "
                f"plan={observed.get('plan', 0)} "
                f"delta_apply={observed.get('delta_apply', 0)} "
                f"full_rebuild={observed.get('full_rebuild', 0)}",
                file=stream,
            )

        if isinstance(plan, dict):
            strategies = plan.get("strategies")
            reasons = plan.get("reasons")
            if isinstance(strategies, dict) and strategies:
                strategy_summary = ", ".join(
                    f"{key}={value}"
                    for key, value in sorted(strategies.items(), key=lambda kv: kv[0])
                )
                print(f"  plan.strategies: {strategy_summary}", file=stream)
            if isinstance(reasons, dict) and reasons:
                reason_summary = ", ".join(
                    f"{key}={value}" for key, value in sorted(reasons.items(), key=lambda kv: kv[0])
                )
                print(f"  plan.reasons: {reason_summary}", file=stream)
            print(
                f"  plan.force_full: true={plan.get('force_full_true', 0)}",
                file=stream,
            )
            latest = plan.get("latest")
            if isinstance(latest, dict):
                print(
                    "  plan.latest: "
                    f"strategy={latest.get('strategy')} "
                    f"reason={latest.get('reason')} "
                    f"changed={latest.get('changed_count')} "
                    f"threshold={latest.get('threshold')} "
                    f"force_full={latest.get('force_full')}",
                    file=stream,
                )

        if isinstance(delta_apply, dict):
            print(
                "  delta.apply: "
                f"count={delta_apply.get('count', 0)} "
                f"success={delta_apply.get('success', 0)} "
                f"failed={delta_apply.get('failed', 0)}",
                file=stream,
            )
            latest = delta_apply.get("latest")
            if isinstance(latest, dict):
                print(
                    "  delta.latest: "
                    f"success={latest.get('success')} "
                    f"changed={latest.get('changed_count')}",
                    file=stream,
                )

        if isinstance(full_rebuild, dict):
            print(
                "  full.rebuild: "
                f"count={full_rebuild.get('count', 0)} "
                f"success={full_rebuild.get('success', 0)} "
                f"failed={full_rebuild.get('failed', 0)}",
                file=stream,
            )
            reasons = full_rebuild.get("reasons")
            if isinstance(reasons, dict) and reasons:
                reason_summary = ", ".join(
                    f"{key}={value}" for key, value in sorted(reasons.items(), key=lambda kv: kv[0])
                )
                print(f"  full.reasons: {reason_summary}", file=stream)
            latest = full_rebuild.get("latest")
            if isinstance(latest, dict):
                print(
                    "  full.latest: "
                    f"success={latest.get('success')} "
                    f"reason={latest.get('reason')} "
                    f"changed={latest.get('changed_count')}",
                    file=stream,
                )

    def _emit_retrieval_signals(
        self,
        report_payload: dict[str, Any],
        *,
        stream: object,
    ) -> None:
        signals = report_payload.get("retrieval_signals")
        if not isinstance(signals, dict):
            return
        row_budget = signals.get("row_budget")
        if not isinstance(row_budget, dict):
            return

        print("-" * 60, file=stream)
        print("Retrieval Signals:", file=stream)
        print(
            "  row_budget: "
            f"count={row_budget.get('count', 0)} "
            f"query={row_budget.get('query_count', 0)} "
            f"backend={row_budget.get('backend_count', 0)} "
            f"fetched={row_budget.get('rows_fetched_sum', 0)} "
            f"parsed={row_budget.get('rows_parsed_sum', 0)} "
            f"input={row_budget.get('rows_input_sum', 0)} "
            f"returned={row_budget.get('rows_returned_sum', 0)} "
            f"capped={row_budget.get('rows_capped_sum', 0)} "
            f"parse_dropped={row_budget.get('rows_parse_dropped_sum', 0)}",
            file=stream,
        )
        modes = row_budget.get("modes")
        if isinstance(modes, dict) and modes:
            mode_summary = ", ".join(
                f"{mode}={values.get('count', 0)}"
                for mode, values in sorted(modes.items(), key=lambda kv: kv[0])
                if isinstance(values, dict)
            )
            if mode_summary:
                print(f"  row_budget.modes: {mode_summary}", file=stream)
        latest = row_budget.get("latest")
        if isinstance(latest, dict):
            print(
                "  row_budget.latest: "
                f"phase={latest.get('phase')} "
                f"mode={latest.get('mode')} "
                f"limit={latest.get('fetch_limit')} "
                f"fetched={latest.get('rows_fetched')} "
                f"parsed={latest.get('rows_parsed')} "
                f"input={latest.get('rows_input')} "
                f"returned={latest.get('rows_returned')} "
                f"capped={latest.get('rows_capped')} "
                f"parse_dropped={latest.get('rows_parse_dropped')}",
                file=stream,
            )

        memory = row_budget.get("memory")
        if isinstance(memory, dict):
            observed_count = int(memory.get("observed_count", 0) or 0)
            rss_sum = self._as_float(memory.get("rss_delta_sum"))
            peak_sum = self._as_float(memory.get("rss_peak_delta_sum"))
            rss_max = self._as_float(memory.get("rss_delta_max"))
            peak_max = self._as_float(memory.get("rss_peak_delta_max"))
            if observed_count > 0 or any(
                v is not None for v in (rss_sum, peak_sum, rss_max, peak_max)
            ):
                rss_sum_text = self._fmt_signed(rss_sum)
                peak_sum_text = self._fmt_signed(peak_sum)
                print(
                    "  row_budget.memory: "
                    f"observed={observed_count} "
                    f"rssΔsum={rss_sum_text} "
                    f"peakΔsum={peak_sum_text} "
                    f"rssΔmax={self._fmt_signed(rss_max)} "
                    f"peakΔmax={self._fmt_signed(peak_max)}",
                    file=stream,
                )

    def emit(self, report: object) -> None:
        """Print formatted summary."""
        d = report.to_dict() if hasattr(report, "to_dict") else report
        stream = self._stream
        print("=" * 60, file=stream)
        print("skills-monitor dashboard", file=stream)
        print("=" * 60, file=stream)
        phases = list(d.get("phases") or [])
        rust_db_events = list(d.get("rust_db_events") or [])
        self._emit_overview(d, stream=stream)
        self._emit_bottlenecks(phases, stream=stream)
        self._emit_phase_groups(phases, stream=stream)
        self._emit_top_events(phases, stream=stream)
        self._emit_retrieval_signals(d, stream=stream)
        self._emit_link_graph_signals(d, stream=stream)
        self._emit_link_graph_index_signals(d, stream=stream)
        self._emit_graph_stats_signals(d, stream=stream)
        self._emit_rust_events(rust_db_events, stream=stream)
        print("=" * 60, file=stream)
