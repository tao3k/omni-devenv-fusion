"""Refresh orchestration for LinkGraph index updates."""

from __future__ import annotations

import json
import time
from typing import Any

from ..codec import decode_json_object


class RefreshMixin:
    """Handle delta/full rebuild planning and execution."""

    @staticmethod
    def _normalize_mode(value: object) -> str:
        mode = str(value or "").strip().lower()
        if mode in {"noop", "delta", "full"}:
            return mode
        return "noop"

    def _replay_rust_refresh_events(self, raw_events: object) -> None:
        if not isinstance(raw_events, list):
            return None
        for row in raw_events:
            if not isinstance(row, dict):
                continue
            phase = str(row.get("phase") or "").strip()
            if not phase:
                continue
            try:
                duration_ms = max(0.0, float(row.get("duration_ms", 0.0) or 0.0))
            except (TypeError, ValueError):
                duration_ms = 0.0
            extra_raw = row.get("extra")
            extra = dict(extra_raw) if isinstance(extra_raw, dict) else {}
            self._record_phase(phase, duration_ms, **extra)
        return None

    def _refresh_with_rust_planner(
        self,
        engine: Any,
        normalized_paths: list[str],
        *,
        force_full: bool,
        threshold: int,
    ) -> dict[str, object] | None:
        planner = getattr(engine, "refresh_plan_apply", None)
        if not callable(planner):
            return None

        payload = json.dumps(normalized_paths, ensure_ascii=False)
        try:
            result_obj = decode_json_object(planner(payload, bool(force_full), int(threshold)))
        except Exception as exc:
            raise RuntimeError(f"Wendao rust refresh planner failed: {exc}") from exc

        self._replay_rust_refresh_events(result_obj.get("events"))

        mode = self._normalize_mode(result_obj.get("mode"))
        changed_count_default = len(normalized_paths)
        try:
            changed_count = max(0, int(result_obj.get("changed_count", changed_count_default) or 0))
        except (TypeError, ValueError):
            changed_count = changed_count_default
        force_full_result = bool(result_obj.get("force_full", bool(force_full)))
        fallback = bool(result_obj.get("fallback", False))

        result = {
            "mode": mode,
            "changed_count": changed_count,
            "force_full": force_full_result,
            "fallback": fallback,
        }
        if mode != "noop":
            self._invalidate_persistent_stats_cache()
        return result

    @staticmethod
    def _has_engine_delta_refresh(engine: Any) -> bool:
        return callable(getattr(engine, "refresh_with_delta", None))

    @staticmethod
    def _has_engine_full_refresh(engine: Any) -> bool:
        return callable(getattr(engine, "refresh", None))

    @classmethod
    def _engine_refresh_full(cls, engine: Any) -> None:
        refresh_with_delta = getattr(engine, "refresh_with_delta", None)
        if callable(refresh_with_delta):
            refresh_with_delta(None, True)
            return
        refresh = getattr(engine, "refresh", None)
        if callable(refresh):
            refresh()
            return
        raise AttributeError("engine missing refresh API (expected refresh_with_delta or refresh)")

    @classmethod
    def _engine_refresh_delta(cls, engine: Any, payload: str) -> None:
        refresh_with_delta = getattr(engine, "refresh_with_delta", None)
        if not callable(refresh_with_delta):
            raise AttributeError("engine missing refresh_with_delta API")
        refresh_with_delta(payload, False)

    async def refresh_with_delta(
        self,
        changed_paths: list[str] | None = None,
        *,
        force_full: bool = False,
    ) -> dict[str, object]:
        engine = self._require_engine()
        normalized_paths = self._normalize_changed_paths(changed_paths)
        threshold = self._resolve_delta_rebuild_threshold()

        planned = self._refresh_with_rust_planner(
            engine,
            normalized_paths,
            force_full=force_full,
            threshold=threshold,
        )
        if planned is not None:
            return planned

        started_plan = time.perf_counter()
        path_count = len(normalized_paths)
        has_delta_refresh = self._has_engine_delta_refresh(engine)
        has_full_refresh = has_delta_refresh or self._has_engine_full_refresh(engine)

        if not force_full and path_count <= 0:
            duration_ms = (time.perf_counter() - started_plan) * 1000.0
            self._record_phase(
                "link_graph.index.delta.plan",
                duration_ms,
                strategy="noop",
                changed_count=0,
                force_full=False,
                threshold=threshold,
                delta_supported=has_delta_refresh,
                full_refresh_supported=has_full_refresh,
            )
            return {
                "mode": "noop",
                "changed_count": 0,
                "force_full": False,
                "fallback": False,
            }

        if not has_full_refresh:
            duration_ms = (time.perf_counter() - started_plan) * 1000.0
            self._record_phase(
                "link_graph.index.delta.plan",
                duration_ms,
                strategy="error",
                reason="engine_refresh_unavailable",
                changed_count=path_count,
                force_full=bool(force_full),
                threshold=threshold,
                delta_supported=has_delta_refresh,
                full_refresh_supported=has_full_refresh,
            )
            raise RuntimeError("Wendao rust engine missing refresh API")

        strategy = "full" if force_full or path_count >= threshold else "delta"
        plan_reason = (
            "force_full"
            if force_full
            else ("threshold_exceeded" if path_count >= threshold else "delta_requested")
        )
        if strategy == "delta" and not has_delta_refresh:
            strategy = "full"
            plan_reason = "engine_delta_unavailable"
        duration_plan_ms = (time.perf_counter() - started_plan) * 1000.0
        self._record_phase(
            "link_graph.index.delta.plan",
            duration_plan_ms,
            strategy=strategy,
            reason=plan_reason,
            changed_count=path_count,
            force_full=bool(force_full),
            threshold=threshold,
            delta_supported=has_delta_refresh,
            full_refresh_supported=has_full_refresh,
        )

        if strategy == "full":
            started_full = time.perf_counter()
            try:
                self._engine_refresh_full(engine)
            except Exception as exc:
                duration_full_ms = (time.perf_counter() - started_full) * 1000.0
                self._record_phase(
                    "link_graph.index.rebuild.full",
                    duration_full_ms,
                    success=False,
                    reason=plan_reason,
                    changed_count=path_count,
                    error=str(exc),
                )
                raise RuntimeError(f"Wendao rust full rebuild failed: {exc}") from exc

            self._invalidate_persistent_stats_cache()
            duration_full_ms = (time.perf_counter() - started_full) * 1000.0
            self._record_phase(
                "link_graph.index.rebuild.full",
                duration_full_ms,
                success=True,
                reason=plan_reason,
                changed_count=path_count,
            )
            return {
                "mode": "full",
                "changed_count": path_count,
                "force_full": bool(force_full),
                "fallback": False,
            }

        started_delta = time.perf_counter()
        payload = json.dumps(normalized_paths, ensure_ascii=False)
        try:
            self._engine_refresh_delta(engine, payload)
        except Exception as exc:
            duration_delta_ms = (time.perf_counter() - started_delta) * 1000.0
            self._record_phase(
                "link_graph.index.delta.apply",
                duration_delta_ms,
                success=False,
                changed_count=path_count,
                error=str(exc),
            )

            started_full = time.perf_counter()
            try:
                self._engine_refresh_full(engine)
            except Exception as full_exc:
                duration_full_ms = (time.perf_counter() - started_full) * 1000.0
                self._record_phase(
                    "link_graph.index.rebuild.full",
                    duration_full_ms,
                    success=False,
                    reason="delta_failed_fallback",
                    changed_count=path_count,
                    error=str(full_exc),
                )
                raise RuntimeError(
                    f"Wendao rust delta refresh failed: {exc}; full fallback failed: {full_exc}"
                ) from full_exc

            self._invalidate_persistent_stats_cache()
            duration_full_ms = (time.perf_counter() - started_full) * 1000.0
            self._record_phase(
                "link_graph.index.rebuild.full",
                duration_full_ms,
                success=True,
                reason="delta_failed_fallback",
                changed_count=path_count,
            )
            return {
                "mode": "full",
                "changed_count": path_count,
                "force_full": False,
                "fallback": True,
            }

        self._invalidate_persistent_stats_cache()
        duration_delta_ms = (time.perf_counter() - started_delta) * 1000.0
        self._record_phase(
            "link_graph.index.delta.apply",
            duration_delta_ms,
            success=True,
            changed_count=path_count,
        )
        return {
            "mode": "delta",
            "changed_count": path_count,
            "force_full": False,
            "fallback": False,
        }
