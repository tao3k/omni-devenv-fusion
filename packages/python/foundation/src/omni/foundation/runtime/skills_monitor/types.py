"""Data types for skills monitor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PhaseEvent:
    """A single phase/event during skill execution (embed, vector_search, dual_core, etc.)."""

    phase: str
    duration_ms: float
    timestamp: float
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RustDbEvent:
    """Rust ↔ DB or Python ↔ Rust bridge event."""

    op: str
    duration_ms: float
    collection: str | None = None
    n_results: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Sample:
    """Process metric sample (RSS, CPU at a point in time)."""

    elapsed_s: float
    rss_mb: float
    rss_peak_mb: float
    cpu_percent: float | None


@dataclass
class MonitorReport:
    """Final report structure for a monitored skill run."""

    skill_command: str
    elapsed_sec: float
    rss_start_mb: float
    rss_end_mb: float
    rss_delta_mb: float
    rss_peak_start_mb: float
    rss_peak_end_mb: float
    rss_peak_delta_mb: float
    cpu_avg_percent: float | None
    phases: list[dict[str, Any]]
    rust_db_events: list[dict[str, Any]]
    samples_count: int
    link_graph_signals: dict[str, Any] | None = None
    retrieval_signals: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        from omni.foundation.api.skills_monitor_signals_schema import validate_signals

        validate_signals(
            retrieval_signals=self.retrieval_signals,
            link_graph_signals=self.link_graph_signals,
        )
        return {
            "skill_command": self.skill_command,
            "elapsed_sec": round(self.elapsed_sec, 2),
            "rss_mb": {
                "start": self.rss_start_mb,
                "end": self.rss_end_mb,
                "delta": round(self.rss_delta_mb, 2),
            },
            "rss_peak_mb": {
                "start": self.rss_peak_start_mb,
                "end": self.rss_peak_end_mb,
                "delta": round(self.rss_peak_delta_mb, 2),
            },
            "cpu_avg_percent": self.cpu_avg_percent,
            "phases": self.phases,
            "rust_db_events": self.rust_db_events,
            "samples_count": self.samples_count,
            "link_graph_signals": self.link_graph_signals,
            "retrieval_signals": self.retrieval_signals,
        }
