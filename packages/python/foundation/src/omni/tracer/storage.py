"""
storage.py - Trace persistence for the execution tracing system

Provides storage and retrieval of execution traces.

Key classes:
- TraceStorage: Store and retrieve traces
- InMemoryTraceStorage: In-memory storage for testing
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from omni.foundation.config.logging import get_logger

from .interfaces import ExecutionTrace, StepType

logger = get_logger("omni.tracer.storage")


class TraceStorage:
    """Storage backend for execution traces.

    Stores traces as JSON files in a configurable directory.

    Usage:
        storage = TraceStorage()
        trace_id = storage.save(trace)
        loaded = storage.load(trace_id)
    """

    def __init__(self, storage_dir: Path | None = None):
        """Initialize the storage.

        Args:
            storage_dir: Directory to store traces. Defaults to PRJ_DATA/traces
        """
        if storage_dir is None:
            from omni.foundation.config.dirs import get_data_dir

            data_dir = get_data_dir()
            if data_dir is not None:
                storage_dir = data_dir / "traces"
            else:
                # Fallback to current directory
                storage_dir = Path(".prj_data/traces")

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.debug("trace_storage_initialized", storage_dir=str(self.storage_dir))

    def save(self, trace: ExecutionTrace) -> str:
        """Save a trace to storage.

        Args:
            trace: The trace to save

        Returns:
            Trace ID
        """
        trace_id = trace.trace_id
        file_path = self.storage_dir / f"{trace_id}.json"

        file_path.write_text(json.dumps(trace.to_dict(), indent=2, ensure_ascii=False))

        logger.info(
            "trace_saved",
            trace_id=trace_id,
            file_path=str(file_path),
            step_count=trace.step_count(),
        )

        return trace_id

    def load(self, trace_id: str) -> ExecutionTrace | None:
        """Load a trace from storage.

        Args:
            trace_id: The trace ID to load

        Returns:
            The loaded trace or None if not found
        """
        file_path = self.storage_dir / f"{trace_id}.json"

        if not file_path.exists():
            logger.debug("trace_not_found", trace_id=trace_id)
            return None

        try:
            data = json.loads(file_path.read_text())
            return ExecutionTrace.from_dict(data)
        except Exception as e:
            logger.error(
                "trace_load_error",
                trace_id=trace_id,
                error=str(e),
            )
            return None

    def list_traces(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List available traces.

        Args:
            limit: Maximum number of traces to return
            offset: Skip this many traces

        Returns:
            List of trace metadata
        """
        trace_files = sorted(
            self.storage_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        traces = []
        for file_path in trace_files[offset : offset + limit]:
            try:
                data = json.loads(file_path.read_text())
                traces.append(
                    {
                        "trace_id": data.get("trace_id"),
                        "start_time": data.get("start_time"),
                        "end_time": data.get("end_time"),
                        "user_query": data.get("user_query"),
                        "success": data.get("success", True),
                        "step_count": len(data.get("steps", {})),
                        "file_path": str(file_path),
                    }
                )
            except Exception as e:
                logger.warning(
                    "trace_parse_error",
                    file_path=str(file_path),
                    error=str(e),
                )

        return traces

    def search(
        self,
        query: str | None = None,
        step_type: StepType | None = None,
        min_duration_ms: float | None = None,
        max_duration_ms: float | None = None,
        success: bool | None = None,
        limit: int = 100,
    ) -> list[ExecutionTrace]:
        """Search traces by various criteria.

        Args:
            query: Search in user_query and step names
            step_type: Filter by step type
            min_duration_ms: Minimum duration
            max_duration_ms: Maximum duration
            success: Filter by success status
            limit: Maximum results

        Returns:
            Matching traces
        """
        results = []
        trace_files = sorted(
            self.storage_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        for file_path in trace_files[: limit * 2]:  # Load more for filtering
            try:
                data = json.loads(file_path.read_text())

                # Filter by query
                if query:
                    query_lower = query.lower()
                    user_query = data.get("user_query", "")
                    if query_lower not in user_query.lower():
                        # Also check step names
                        step_names = [s.get("name") for s in data.get("steps", {}).values()]
                        if not any(query_lower in name.lower() for name in step_names if name):
                            continue

                # Filter by step type
                if step_type:
                    step_types = [s.get("step_type") for s in data.get("steps", {}).values()]
                    if step_type.value not in step_types:
                        continue

                # Filter by duration
                start_time = data.get("start_time")
                end_time = data.get("end_time")
                if start_time and end_time:
                    start = datetime.fromisoformat(start_time)
                    end = datetime.fromisoformat(end_time)
                    duration_ms = (end - start).total_seconds() * 1000

                    if min_duration_ms is not None and duration_ms < min_duration_ms:
                        continue
                    if max_duration_ms is not None and duration_ms > max_duration_ms:
                        continue

                # Filter by success
                if success is not None:
                    if data.get("success", True) != success:
                        continue

                results.append(ExecutionTrace.from_dict(data))

                if len(results) >= limit:
                    break

            except Exception as e:
                logger.warning(
                    "trace_search_error",
                    file_path=str(file_path),
                    error=str(e),
                )

        return results

    def delete(self, trace_id: str) -> bool:
        """Delete a trace.

        Args:
            trace_id: Trace ID to delete

        Returns:
            True if deleted, False if not found
        """
        file_path = self.storage_dir / f"{trace_id}.json"

        if not file_path.exists():
            return False

        file_path.unlink()
        logger.info("trace_deleted", trace_id=trace_id)
        return True

    def cleanup(self, keep_count: int = 100) -> int:
        """Remove old traces, keeping the most recent ones.

        Args:
            keep_count: Number of traces to keep

        Returns:
            Number of traces deleted
        """
        trace_files = sorted(
            self.storage_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
        )

        deleted = 0
        for file_path in trace_files[:-keep_count]:
            file_path.unlink()
            deleted += 1

        if deleted > 0:
            logger.info(
                "trace_cleanup",
                deleted=deleted,
                kept=keep_count,
            )

        return deleted

    @property
    def trace_count(self) -> int:
        """Get the total number of stored traces."""
        return len(list(self.storage_dir.glob("*.json")))


class InMemoryTraceStorage:
    """In-memory storage for testing and development.

    Does not persist traces to disk.
    """

    def __init__(self):
        self._traces: dict[str, ExecutionTrace] = {}

    def save(self, trace: ExecutionTrace) -> str:
        """Save a trace."""
        self._traces[trace.trace_id] = trace
        return trace.trace_id

    def load(self, trace_id: str) -> ExecutionTrace | None:
        """Load a trace."""
        return self._traces.get(trace_id)

    def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        """List traces."""
        traces = list(self._traces.values())[:limit]
        return [
            {
                "trace_id": t.trace_id,
                "start_time": t.start_time.isoformat(),
                "user_query": t.user_query,
                "success": t.success,
                "step_count": t.step_count(),
            }
            for t in sorted(traces, key=lambda x: x.start_time, reverse=True)
        ]

    def delete(self, trace_id: str) -> bool:
        """Delete a trace."""
        if trace_id in self._traces:
            del self._traces[trace_id]
            return True
        return False

    def clear(self) -> None:
        """Clear all traces."""
        self._traces.clear()


__all__ = [
    "InMemoryTraceStorage",
    "TraceStorage",
]
