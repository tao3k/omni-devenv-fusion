"""Query/read methods for Wendao backend."""

from __future__ import annotations

import json
import time
from typing import Any

from ..codec import decode_json_list, decode_json_object


class QueryMixin:
    """Query surface that delegates work to the Rust engine."""

    _engine_explicit: bool

    @staticmethod
    def _hits_from_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        bounded = max(1, int(limit))
        out: list[dict[str, Any]] = []
        for row in rows:
            stem = str(row.get("stem") or row.get("id") or "").strip()
            if not stem:
                continue
            try:
                score = float(row.get("score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            out.append(
                {
                    "stem": stem,
                    "score": max(0.0, score),
                    "title": str(row.get("title") or ""),
                    "path": str(row.get("path") or ""),
                    "best_section": str(row.get("best_section") or ""),
                    "match_reason": str(row.get("match_reason") or ""),
                }
            )
        return out[:bounded]

    async def search_planned(
        self,
        query: str,
        limit: int = 20,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Search and return effective parsed query/options from Rust plan."""
        engine = self._require_engine()
        bounded = max(1, int(limit))
        options_json = json.dumps(dict(options or {}), sort_keys=True)
        query_text = str(query)
        started_at = time.perf_counter()

        try:
            payload = decode_json_object(engine.search_planned(str(query), bounded, options_json))
        except Exception as exc:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            self._record_phase(
                "link_graph.search_planned",
                duration_ms,
                success=False,
                limit=bounded,
                query_len=len(query_text.strip()),
                error=str(exc),
            )
            raise RuntimeError(f"Wendao rust planned search failed: {exc}") from exc

        planned_query_raw = payload.get("query")
        planned_query = (
            str(planned_query_raw).strip() if planned_query_raw is not None else str(query)
        )

        planned_options_raw = payload.get("options")
        planned_options = planned_options_raw if isinstance(planned_options_raw, dict) else {}

        raw_hits = payload.get("hits")
        if isinstance(raw_hits, list):
            hits = [row for row in raw_hits if isinstance(row, dict)][:bounded]
        else:
            raw_rows = payload.get("results")
            rows = decode_json_list(raw_rows)
            hits = self._hits_from_rows(rows, bounded)

        try:
            section_hit_count = max(0, int(payload.get("section_hit_count", 0) or 0))
        except (TypeError, ValueError):
            section_hit_count = sum(1 for hit in hits if str(hit.get("best_section") or "").strip())

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self._record_phase(
            "link_graph.search_planned",
            duration_ms,
            success=True,
            limit=bounded,
            query_len=len(query_text.strip()),
            parsed_query_len=len(planned_query),
            hit_count=len(hits),
            match_strategy=str(planned_options.get("match_strategy", "")),
        )
        if section_hit_count > 0:
            self._record_phase(
                "link_graph.search.section_score",
                0.0,
                hit_count=len(hits),
                section_hit_count=section_hit_count,
            )
        if str(planned_options.get("match_strategy", "")).strip() == "path_fuzzy":
            self._record_phase(
                "link_graph.search.path_fuzzy",
                0.0,
                hit_count=len(hits),
            )
        self._record_phase(
            "link_graph.search.rank_fusion",
            0.0,
            hit_count=len(hits),
            section_hit_count=section_hit_count,
        )

        return {
            "query": planned_query,
            "search_options": planned_options,
            "hits": hits,
        }

    async def neighbors(
        self,
        stem: str,
        *,
        direction: str = "both",
        hops: int = 1,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        engine = self._require_engine()
        bounded_limit = max(1, int(limit))
        bounded_hops = max(1, int(hops))
        try:
            rows = decode_json_list(
                engine.neighbors(
                    str(stem),
                    str(direction),
                    bounded_hops,
                    bounded_limit,
                )
            )
        except Exception as exc:
            raise RuntimeError(f"Wendao rust neighbors failed: {exc}") from exc

        out: list[dict[str, Any]] = []
        for row in rows:
            neigh_stem = str(row.get("stem") or row.get("id") or "").strip()
            if not neigh_stem:
                continue
            raw_dir = str(row.get("direction") or "both").strip().lower()
            if raw_dir in {"incoming", "to"}:
                parsed_dir = "incoming"
            elif raw_dir in {"outgoing", "from"}:
                parsed_dir = "outgoing"
            else:
                parsed_dir = "both"
            try:
                distance = max(1, int(row.get("distance", 1)))
            except (TypeError, ValueError):
                distance = 1
            out.append(
                {
                    "stem": neigh_stem,
                    "direction": parsed_dir,
                    "distance": distance,
                    "title": str(row.get("title") or ""),
                    "path": str(row.get("path") or ""),
                }
            )
        return out[:bounded_limit]

    async def related(
        self,
        stem: str,
        *,
        max_distance: int = 2,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        engine = self._require_engine()
        bounded_limit = max(1, int(limit))
        bounded_distance = max(1, int(max_distance))
        try:
            rows = decode_json_list(engine.related(str(stem), bounded_distance, bounded_limit))
        except Exception as exc:
            raise RuntimeError(f"Wendao rust related failed: {exc}") from exc

        out: list[dict[str, Any]] = []
        for row in rows:
            neigh_stem = str(row.get("stem") or row.get("id") or "").strip()
            if not neigh_stem:
                continue
            try:
                distance = max(1, int(row.get("distance", 1)))
            except (TypeError, ValueError):
                distance = 1
            out.append(
                {
                    "stem": neigh_stem,
                    "direction": "both",
                    "distance": distance,
                    "title": str(row.get("title") or ""),
                    "path": str(row.get("path") or ""),
                }
            )
        return out[:bounded_limit]

    async def metadata(self, stem: str) -> dict[str, Any] | None:
        engine = self._require_engine()
        try:
            payload = decode_json_object(engine.metadata(str(stem)))
        except Exception as exc:
            raise RuntimeError(f"Wendao rust metadata failed: {exc}") from exc
        if not payload:
            return None
        tags_raw = payload.get("tags") or []
        tags = [str(t) for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
        meta_stem = str(payload.get("stem") or stem).strip()
        if not meta_stem:
            return None
        return {
            "stem": meta_stem,
            "tags": tags,
            "title": str(payload.get("title") or ""),
            "path": str(payload.get("path") or ""),
        }

    async def toc(self, limit: int = 1000) -> list[dict[str, object]]:
        """Return ToC rows from Rust engine."""
        engine = self._require_engine()
        try:
            rows = decode_json_list(engine.toc(max(1, int(limit))))
        except Exception as exc:
            raise RuntimeError(f"Wendao rust toc failed: {exc}") from exc
        out: list[dict[str, object]] = []
        for row in rows:
            tags_raw = row.get("tags") or []
            tags = (
                [str(t) for t in tags_raw if str(t).strip()] if isinstance(tags_raw, list) else []
            )
            out.append(
                {
                    "id": str(row.get("id") or row.get("doc_id") or row.get("stem") or ""),
                    "title": str(row.get("title") or ""),
                    "tags": tags,
                    "lead": str(row.get("lead") or "")[:100],
                    "path": str(row.get("path") or ""),
                }
            )
        return out[: max(1, int(limit))]

    async def stats(self) -> dict[str, int]:
        """Return normalized graph stats from Rust engine."""
        if not self._engine_explicit:
            cached = self._load_persistent_stats_cache()
            if cached is not None:
                return cached

        engine = self._require_engine()
        try:
            payload = decode_json_object(engine.stats())
        except Exception as exc:
            raise RuntimeError(f"Wendao rust stats failed: {exc}") from exc

        normalized_engine = self._normalize_engine_stats(payload)
        if normalized_engine is None:
            raise RuntimeError("Wendao rust stats failed: invalid stats payload")

        self._save_persistent_stats_cache(normalized_engine)
        return normalized_engine

    async def create_note(
        self,
        title: str,
        body: str,
        *,
        tags: list[str] | None = None,
    ) -> object | None:
        del title, body, tags
        return None
