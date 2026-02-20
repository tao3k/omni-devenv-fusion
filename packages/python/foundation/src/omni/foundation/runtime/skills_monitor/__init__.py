"""
Skills Monitor - Observability for skill execution.

Modular package for monitoring:
- Execution time (total + per-phase)
- Process memory (RSS) and CPU
- Rust ↔ DB / Python ↔ Rust bridge events
- Structured logs for debugging skill tools and knowledge injection

Usage:
  from omni.foundation.runtime.skills_monitor import skills_monitor_scope

  async with skills_monitor_scope("knowledge.recall", verbose=True):
      result = await run_skill("knowledge", "recall", {...})

  # Sync callers:
  from omni.foundation.runtime.skills_monitor import run_with_monitor
  result = run_with_monitor("knowledge.recall", lambda: run_skill(...), verbose=True)
"""

from __future__ import annotations

from .context import (
    get_current_monitor,
    record_phase,
    record_rust_db,
    suppress_skill_command_phase_events,
)
from .monitor import SkillsMonitor
from .perf_gate import (
    RecallPerfRun,
    RecallPerfSummary,
    evaluate_gate,
    extract_status_and_error,
    percentile_nearest_rank,
    summarize_runs,
)
from .phase import (
    build_memory_delta_fields,
    phase_scope,
    record_phase_with_memory,
    sample_memory,
    start_phase_sample,
)
from .scope import run_with_monitor, skills_monitor_scope
from .signals import (
    build_link_graph_index_refresh_signals,
    build_link_graph_signals,
    build_retrieval_signals,
)
from .types import MonitorReport, PhaseEvent, RustDbEvent, Sample

__all__ = [
    "MonitorReport",
    "PhaseEvent",
    "RecallPerfRun",
    "RecallPerfSummary",
    "RustDbEvent",
    "Sample",
    "SkillsMonitor",
    "build_link_graph_index_refresh_signals",
    "build_link_graph_signals",
    "build_memory_delta_fields",
    "build_retrieval_signals",
    "evaluate_gate",
    "extract_status_and_error",
    "get_current_monitor",
    "percentile_nearest_rank",
    "phase_scope",
    "record_phase",
    "record_phase_with_memory",
    "record_rust_db",
    "run_with_monitor",
    "sample_memory",
    "skills_monitor_scope",
    "start_phase_sample",
    "summarize_runs",
    "suppress_skill_command_phase_events",
]
