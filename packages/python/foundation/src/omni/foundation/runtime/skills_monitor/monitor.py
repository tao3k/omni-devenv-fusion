"""Core SkillsMonitor orchestrator."""

from __future__ import annotations

import asyncio
import threading
import time
from contextlib import suppress
from typing import Any

from .metrics import get_rss_mb, get_rss_peak_mb, take_sample
from .reporters import JsonReporter, SummaryReporter
from .signals import build_link_graph_signals, build_retrieval_signals
from .types import MonitorReport, PhaseEvent, RustDbEvent


class SkillsMonitor:
    """Collects metrics and events during skill execution."""

    def __init__(
        self,
        skill_command: str,
        *,
        sample_interval_s: float = 1.0,
        verbose: bool = False,
    ):
        self.skill_command = skill_command
        self.sample_interval_s = sample_interval_s
        self.verbose = verbose
        self.start_time = time.perf_counter()
        self.phases: list[PhaseEvent] = []
        self.rust_db_events: list[RustDbEvent] = []
        self.samples: list[Any] = []
        self._sampler_task: asyncio.Task | None = None
        self._sampler_stop: asyncio.Event | None = None
        self._lock = threading.Lock()

    def record_phase(self, phase: str, duration_ms: float, **extra: Any) -> None:
        """Record a phase event (embed, vector_search, dual_core, etc.)."""
        with self._lock:
            self.phases.append(
                PhaseEvent(
                    phase=phase,
                    duration_ms=duration_ms,
                    timestamp=time.perf_counter() - self.start_time,
                    extra=dict(extra),
                )
            )
        if self.verbose:
            import sys

            key_order = (
                "tool",
                "function",
                "success",
                "source",
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
                "rss_before_mb",
                "rss_after_mb",
                "rss_delta_mb",
                "rss_peak_before_mb",
                "rss_peak_after_mb",
                "rss_peak_delta_mb",
                "source_hint_count",
                "rows_per_source",
                "total_cap",
                "command_count",
                "module",
                "reused",
                "target",
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
            details: list[str] = []
            for key in key_order:
                value = extra.get(key)
                if value is None:
                    continue
                if isinstance(value, str) and not value:
                    continue
                details.append(f"{key}={value}")
            detail_str = f" {' '.join(details)}" if details else ""
            print(
                f"  [monitor] phase={phase} duration_ms={duration_ms:.0f}{detail_str}",
                file=sys.stderr,
                flush=True,
            )

    def record_rust_db(self, op: str, duration_ms: float, **extra: Any) -> None:
        """Record a Rust/DB bridge event."""
        with self._lock:
            self.rust_db_events.append(RustDbEvent(op=op, duration_ms=duration_ms, **extra))
        if self.verbose:
            import sys

            print(
                f"  [monitor] rust_db op={op} duration_ms={duration_ms:.0f}",
                file=sys.stderr,
                flush=True,
            )

    def _take_sample(self) -> None:
        elapsed = time.perf_counter() - self.start_time
        with self._lock:
            self.samples.append(take_sample(elapsed))

    async def _sampler_loop(self) -> None:
        """Background task to sample RSS/CPU periodically."""
        stop = self._sampler_stop
        if stop is None:
            return
        while not stop.is_set():
            await asyncio.sleep(self.sample_interval_s)
            if stop.is_set():
                break
            self._take_sample()
            if self.verbose:
                import sys

                s = self.samples[-1]
                cpu_str = f" cpu={s.cpu_percent}%" if s.cpu_percent is not None else ""
                print(
                    f"  [monitor] sample t={s.elapsed_s:.1f}s rss={s.rss_mb:.0f} MiB{cpu_str}",
                    file=sys.stderr,
                    flush=True,
                )

    def start_sampler(self) -> None:
        """Start background metric sampling."""
        self._sampler_stop = asyncio.Event()
        self._take_sample()
        self._sampler_task = asyncio.create_task(self._sampler_loop())

    def stop_sampler(self) -> None:
        """Stop background sampling."""
        if self._sampler_stop is not None:
            self._sampler_stop.set()
        task = self._sampler_task
        self._sampler_task = None
        if task is not None:
            task.cancel()
            if task.done():
                try:
                    task.result()
                except asyncio.CancelledError:
                    pass
                except Exception:
                    # Best-effort cleanup only; never fail monitored command flow.
                    pass
        with suppress(Exception):
            self._take_sample()

    def build_report(self) -> MonitorReport:
        """Build the final report from collected data."""
        elapsed = time.perf_counter() - self.start_time
        rss_end = get_rss_mb()
        rss_peak_end = get_rss_peak_mb()
        rss_start = self.samples[0].rss_mb if self.samples else rss_end
        rss_peak_start = self.samples[0].rss_peak_mb if self.samples else rss_peak_end
        rss_delta = rss_end - rss_start
        rss_peak_delta = rss_peak_end - rss_peak_start

        cpu_avg: float | None = None
        if self.samples and any(s.cpu_percent is not None for s in self.samples):
            cpus = [s.cpu_percent for s in self.samples if s.cpu_percent is not None]
            cpu_avg = round(sum(cpus) / len(cpus), 1) if cpus else None

        phases_dict = [
            {
                "phase": p.phase,
                "duration_ms": round(p.duration_ms, 2),
                "timestamp_s": round(p.timestamp, 2),
                **p.extra,
            }
            for p in self.phases
        ]
        rust_dict = [
            {
                "op": e.op,
                "duration_ms": round(e.duration_ms, 2),
                "collection": e.collection,
                "n_results": e.n_results,
                **e.extra,
            }
            for e in self.rust_db_events
        ]
        link_graph_signals = self._build_link_graph_signals(phases_dict)
        retrieval_signals = self._build_retrieval_signals(phases_dict)

        return MonitorReport(
            skill_command=self.skill_command,
            elapsed_sec=elapsed,
            rss_start_mb=rss_start,
            rss_end_mb=rss_end,
            rss_delta_mb=rss_delta,
            rss_peak_start_mb=rss_peak_start,
            rss_peak_end_mb=rss_peak_end,
            rss_peak_delta_mb=rss_peak_delta,
            cpu_avg_percent=cpu_avg,
            phases=phases_dict,
            rust_db_events=rust_dict,
            samples_count=len(self.samples),
            link_graph_signals=link_graph_signals,
            retrieval_signals=retrieval_signals,
        )

    def report(self, output_json: bool = False) -> MonitorReport:
        """Build report and emit via configured reporter."""
        report = self.build_report()
        if output_json:
            JsonReporter().emit(report)
        else:
            SummaryReporter().emit(report)
        return report

    @staticmethod
    def _build_link_graph_signals(phases: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Build machine-readable LinkGraph signal summary from phase events."""
        return build_link_graph_signals(phases)

    @staticmethod
    def _build_retrieval_signals(phases: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Build machine-readable retrieval row-budget summary from phase events."""
        return build_retrieval_signals(phases)
