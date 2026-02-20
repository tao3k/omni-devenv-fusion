"""
Semantic vector search.

Query embedding (timeout) and Rust search (IPC/JSON path) with cache.
Raises EmbeddingUnavailableError when embedding HTTP service is unavailable.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import ValidationError

from omni.foundation.runtime.skills_monitor.phase import (
    build_memory_delta_fields as _memory_fields,
)
from omni.foundation.runtime.skills_monitor.phase import (
    phase_scope as _phase_scope,
)
from omni.foundation.runtime.skills_monitor.phase import (
    sample_memory as _sample_memory,
)
from omni.foundation.services.embedding import EmbeddingUnavailableError
from omni.foundation.services.vector_schema import (
    VectorPayload,
    build_search_options_json,
    parse_vector_payload,
)

from .constants import (
    ERROR_BINDING_API_MISSING,
    ERROR_PAYLOAD_VALIDATION,
    ERROR_REQUEST_VALIDATION,
    ERROR_RUNTIME,
    ERROR_TABLE_NOT_FOUND,
)
from .models import SearchResult

logger = structlog.get_logger(__name__)

# --- Query embedding (used by semantic and hybrid search) ---
SEARCH_EMBED_TIMEOUT = 5
_FALLBACK_MCP_EMBED_PORTS = (3002, 3001, 3000)
_DEFAULT_RESULT_PROJECTION = ("id", "content", "_distance", "metadata")
_SCANNER_PROFILE_SMALL = {"batch_size": 256, "fragment_readahead": 2, "batch_readahead": 4}
_SCANNER_PROFILE_MEDIUM = {"batch_size": 1024, "fragment_readahead": 4, "batch_readahead": 16}
_SCANNER_PROFILE_LARGE = {"batch_size": 2048, "fragment_readahead": 8, "batch_readahead": 32}
_QUERY_EMBED_PERSIST_SCHEMA = 1
_QUERY_EMBED_PERSIST_FILENAME = "query-embed-last.json"
_LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT: tuple[int, str] | None = None
_MCP_EMBED_ENDPOINT_LOCK = threading.Lock()
_QUERY_EMBED_CACHE_MAX = 32
_QUERY_EMBED_CACHE: OrderedDict[str, tuple[float, ...]] = OrderedDict()
_QUERY_EMBED_CACHE_LOCK = threading.Lock()
_QUERY_EMBED_PERSIST_LOCK = threading.Lock()
_QUERY_EMBED_PERSIST_LOADED = False
_QUERY_EMBED_PERSIST_RECORD: dict[str, Any] | None = None
_MCP_EMBED_FAILURE_TTL_S = 3.0
_HTTP_EMBED_FAILURE_TTL_S = 3.0
_MCP_EMBED_FAILURE_UNTIL: dict[tuple[int, str], float] = {}
_MCP_EMBED_FAILURE_LOCK = threading.Lock()
_HTTP_EMBED_FAILURE_UNTIL: dict[str, float] = {}
_HTTP_EMBED_FAILURE_LOCK = threading.Lock()


def _default_mcp_embed_ports() -> tuple[int, ...]:
    """Resolve MCP embed ports from config; fallback list only when not configured."""
    try:
        from omni.foundation.config.settings import get_setting

        preferred = get_setting("mcp.preferred_embed_port")
        if preferred is not None:
            preferred_port = (
                int(preferred)
                if isinstance(preferred, (int, float))
                else int(str(preferred).strip())
            )
            if 0 < preferred_port < 65536:
                return (preferred_port,)
    except Exception:
        pass
    return _FALLBACK_MCP_EMBED_PORTS


def _mcp_embed_paths_for_port(port: int) -> tuple[str, ...]:
    """Return MCP JSON-RPC endpoint probe order for a given port."""
    resolved_port = int(port)
    if resolved_port == 3001:
        return ("/message", "/messages/")
    if resolved_port == 3000:
        return ("/messages/", "/message", "/mcp", "/")
    return ("/messages/", "/mcp", "/")


def _build_default_mcp_probe_targets() -> list[tuple[int, str]]:
    """Return canonical MCP embedding endpoint probe order."""
    return [
        (port, path)
        for port in _default_mcp_embed_ports()
        for path in _mcp_embed_paths_for_port(port)
    ]


def _default_scanner_profile(
    n_results: int,
) -> tuple[str, dict[str, int]]:
    """Return adaptive scanner profile defaults based on requested result window."""
    if n_results <= 20:
        return "small", dict(_SCANNER_PROFILE_SMALL)
    if n_results <= 200:
        return "medium", dict(_SCANNER_PROFILE_MEDIUM)
    return "large", dict(_SCANNER_PROFILE_LARGE)


def _resolve_scanner_tuning(
    *,
    n_results: int,
    batch_size: int | None,
    fragment_readahead: int | None,
    batch_readahead: int | None,
) -> tuple[str, int, int, int, bool]:
    """Resolve effective scanner tuning and whether adaptive defaults were applied."""
    profile_name, defaults = _default_scanner_profile(n_results)
    defaults_applied = False

    effective_batch_size = batch_size
    if effective_batch_size is None:
        effective_batch_size = defaults["batch_size"]
        defaults_applied = True

    effective_fragment_readahead = fragment_readahead
    if effective_fragment_readahead is None:
        effective_fragment_readahead = defaults["fragment_readahead"]
        defaults_applied = True

    effective_batch_readahead = batch_readahead
    if effective_batch_readahead is None:
        effective_batch_readahead = defaults["batch_readahead"]
        defaults_applied = True

    return (
        profile_name,
        int(effective_batch_size),
        int(effective_fragment_readahead),
        int(effective_batch_readahead),
        defaults_applied,
    )


def _get_cached_mcp_probe_target() -> tuple[int, str] | None:
    """Get last successful MCP endpoint probe target."""
    with _MCP_EMBED_ENDPOINT_LOCK:
        return _LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT


def _remember_mcp_probe_target(port: int, path: str) -> None:
    """Persist successful MCP endpoint so next query can probe it first."""
    global _LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT
    with _MCP_EMBED_ENDPOINT_LOCK:
        _LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT = (int(port), str(path))


def _ordered_mcp_probe_targets() -> list[tuple[int, str]]:
    """Build probe order, prioritizing the last successful endpoint."""
    default_targets = _build_default_mcp_probe_targets()
    cached_target = _get_cached_mcp_probe_target()
    if cached_target is None:
        return default_targets
    return [cached_target] + [target for target in default_targets if target != cached_target]


def _query_embed_cache_size() -> int:
    with _QUERY_EMBED_CACHE_LOCK:
        return len(_QUERY_EMBED_CACHE)


def _query_embed_persist_path() -> Path:
    """Path for persisted last-query embedding cache."""
    from omni.foundation.config.dirs import PRJ_CACHE

    path = PRJ_CACHE("omni-vector", _QUERY_EMBED_PERSIST_FILENAME)
    return path if isinstance(path, Path) else Path(path)


def _query_embed_signature() -> str:
    """Build signature to avoid reusing vectors across embedding config changes."""
    try:
        from omni.foundation.config.settings import get_setting

        parts = {
            "provider": str(get_setting("embedding.provider") or ""),
            "client_url": str(get_setting("embedding.client_url") or ""),
            "http_port": str(get_setting("embedding.http_port") or ""),
            "litellm_model": str(get_setting("embedding.litellm_model") or ""),
            "dimension": str(get_setting("embedding.dimension") or ""),
            "truncate_dim": str(get_setting("embedding.truncate_dim") or ""),
            "preferred_mcp_port": str(get_setting("mcp.preferred_embed_port") or ""),
        }
        return "|".join(f"{k}={parts[k]}" for k in sorted(parts))
    except Exception:
        return "signature-unavailable"


def _query_embed_cache_key(query: str, signature: str) -> str:
    digest = hashlib.sha256()
    digest.update(signature.encode("utf-8"))
    digest.update(b"\n")
    digest.update(query.encode("utf-8"))
    return digest.hexdigest()


def _load_persisted_query_vector_record() -> None:
    """Best-effort load of persisted last-query embedding record."""
    global _QUERY_EMBED_PERSIST_LOADED, _QUERY_EMBED_PERSIST_RECORD
    with _QUERY_EMBED_PERSIST_LOCK:
        if _QUERY_EMBED_PERSIST_LOADED:
            return
        _QUERY_EMBED_PERSIST_LOADED = True
        _QUERY_EMBED_PERSIST_RECORD = None

        path = _query_embed_persist_path()
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, dict):
            return
        if int(raw.get("schema", 0) or 0) != _QUERY_EMBED_PERSIST_SCHEMA:
            return
        vector_raw = raw.get("vector")
        if not isinstance(vector_raw, list):
            return
        try:
            vector = [float(v) for v in vector_raw]
        except Exception:
            return
        _QUERY_EMBED_PERSIST_RECORD = {
            "schema": _QUERY_EMBED_PERSIST_SCHEMA,
            "signature": str(raw.get("signature") or ""),
            "key": str(raw.get("key") or ""),
            "vector": vector,
        }


def _get_persisted_query_vector(query: str) -> list[float] | None:
    """Return persisted embedding for this query when signature+key match."""
    _load_persisted_query_vector_record()
    signature = _query_embed_signature()
    key = _query_embed_cache_key(query, signature)
    with _QUERY_EMBED_PERSIST_LOCK:
        rec = _QUERY_EMBED_PERSIST_RECORD
        if not isinstance(rec, dict):
            return None
        if rec.get("signature") != signature or rec.get("key") != key:
            return None
        vector = rec.get("vector")
        if not isinstance(vector, list):
            return None
        try:
            return [float(v) for v in vector]
        except Exception:
            return None


def _remember_persisted_query_vector(query: str, vector: list[float]) -> None:
    """Persist last query embedding for cross-process warm-start."""
    if not vector:
        return
    signature = _query_embed_signature()
    key = _query_embed_cache_key(query, signature)
    payload = {
        "schema": _QUERY_EMBED_PERSIST_SCHEMA,
        "signature": signature,
        "key": key,
        "vector": [float(v) for v in vector],
    }

    global _QUERY_EMBED_PERSIST_RECORD, _QUERY_EMBED_PERSIST_LOADED
    with _QUERY_EMBED_PERSIST_LOCK:
        _QUERY_EMBED_PERSIST_RECORD = payload
        _QUERY_EMBED_PERSIST_LOADED = True

    path = _query_embed_persist_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        tmp_path.replace(path)
    except Exception:
        return


def _get_cached_query_vector(query: str) -> tuple[list[float] | None, str]:
    """Get cached embedding for a query and refresh LRU order."""
    with _QUERY_EMBED_CACHE_LOCK:
        cached = _QUERY_EMBED_CACHE.get(query)
        if cached is None:
            pass
        else:
            _QUERY_EMBED_CACHE.move_to_end(query, last=True)
            return [float(v) for v in cached], "memory"

    persisted = _get_persisted_query_vector(query)
    if persisted is None:
        return None, "none"

    with _QUERY_EMBED_CACHE_LOCK:
        _QUERY_EMBED_CACHE[query] = tuple(float(v) for v in persisted)
        _QUERY_EMBED_CACHE.move_to_end(query, last=True)
        while len(_QUERY_EMBED_CACHE) > _QUERY_EMBED_CACHE_MAX:
            _QUERY_EMBED_CACHE.popitem(last=False)
    return persisted, "persistent"


def _remember_query_vector(query: str, vector: list[float]) -> None:
    """Store query embedding in bounded LRU cache."""
    if not vector:
        return
    with _QUERY_EMBED_CACHE_LOCK:
        _QUERY_EMBED_CACHE[query] = tuple(float(v) for v in vector)
        _QUERY_EMBED_CACHE.move_to_end(query, last=True)
        while len(_QUERY_EMBED_CACHE) > _QUERY_EMBED_CACHE_MAX:
            _QUERY_EMBED_CACHE.popitem(last=False)
    _remember_persisted_query_vector(query, vector)


def _cleanup_mcp_failure_cache(now: float | None = None) -> int:
    """Remove expired MCP endpoint backoff entries and return active count."""
    ts = time.monotonic() if now is None else now
    with _MCP_EMBED_FAILURE_LOCK:
        expired = [k for k, until in _MCP_EMBED_FAILURE_UNTIL.items() if until <= ts]
        for key in expired:
            _MCP_EMBED_FAILURE_UNTIL.pop(key, None)
        return len(_MCP_EMBED_FAILURE_UNTIL)


def _is_mcp_target_in_backoff(port: int, path: str) -> bool:
    """Return True if this MCP endpoint recently failed and is under backoff."""
    ts = time.monotonic()
    with _MCP_EMBED_FAILURE_LOCK:
        until = _MCP_EMBED_FAILURE_UNTIL.get((int(port), str(path)))
        if until is None:
            return False
        if until <= ts:
            _MCP_EMBED_FAILURE_UNTIL.pop((int(port), str(path)), None)
            return False
        return True


def _remember_mcp_target_failure(port: int, path: str) -> None:
    """Mark endpoint unavailable briefly to avoid repeated timeout-heavy probes."""
    with _MCP_EMBED_FAILURE_LOCK:
        _MCP_EMBED_FAILURE_UNTIL[(int(port), str(path))] = (
            time.monotonic() + _MCP_EMBED_FAILURE_TTL_S
        )


def _clear_mcp_target_failure(port: int, path: str) -> None:
    """Clear endpoint backoff after a successful probe."""
    with _MCP_EMBED_FAILURE_LOCK:
        _MCP_EMBED_FAILURE_UNTIL.pop((int(port), str(path)), None)


def _cleanup_http_failure_cache(now: float | None = None) -> int:
    """Remove expired HTTP endpoint backoff entries and return active count."""
    ts = time.monotonic() if now is None else now
    with _HTTP_EMBED_FAILURE_LOCK:
        expired = [k for k, until in _HTTP_EMBED_FAILURE_UNTIL.items() if until <= ts]
        for key in expired:
            _HTTP_EMBED_FAILURE_UNTIL.pop(key, None)
        return len(_HTTP_EMBED_FAILURE_UNTIL)


def _is_http_endpoint_in_backoff(base_url: str) -> bool:
    """Return True if HTTP embedding endpoint recently failed in this process."""
    ts = time.monotonic()
    key = str(base_url).strip()
    with _HTTP_EMBED_FAILURE_LOCK:
        until = _HTTP_EMBED_FAILURE_UNTIL.get(key)
        if until is None:
            return False
        if until <= ts:
            _HTTP_EMBED_FAILURE_UNTIL.pop(key, None)
            return False
        return True


def _remember_http_endpoint_failure(base_url: str) -> None:
    """Mark HTTP endpoint unavailable briefly after connection/timeouts."""
    key = str(base_url).strip()
    with _HTTP_EMBED_FAILURE_LOCK:
        _HTTP_EMBED_FAILURE_UNTIL[key] = time.monotonic() + _HTTP_EMBED_FAILURE_TTL_S


def _clear_http_endpoint_failure(base_url: str) -> None:
    """Clear HTTP endpoint backoff after successful embedding."""
    key = str(base_url).strip()
    with _HTTP_EMBED_FAILURE_LOCK:
        _HTTP_EMBED_FAILURE_UNTIL.pop(key, None)


def search_embed_timeout() -> int:
    """Timeout (seconds) for embedding the query during search."""
    try:
        from omni.foundation.config.settings import get_setting

        return int(get_setting("knowledge.recall_embed_timeout_seconds", 5))
    except Exception:
        return 5


def _record_phase(phase: str, duration_ms: float, **extra: Any) -> None:
    """Record monitor phase when skills monitor is active."""
    try:
        from omni.foundation.runtime.skills_monitor import record_phase

        record_phase(phase, duration_ms, **extra)
    except Exception:
        pass


# --- Semantic search ---

if TYPE_CHECKING:
    from .store import VectorStoreClient


async def run_semantic_search(
    client: VectorStoreClient,
    query: str,
    n_results: int,
    collection: str,
    use_cache: bool,
    where_filter: str | dict[str, Any] | None = None,
    batch_size: int | None = None,
    fragment_readahead: int | None = None,
    batch_readahead: int | None = None,
    scan_limit: int | None = None,
    projection: list[str] | None = None,
) -> list[SearchResult]:
    """Run semantic search: embed query (async, bounded), then Rust search. Uses client cache and store."""
    from .constants import MAX_SEARCH_RESULTS

    if n_results < 1 or n_results > MAX_SEARCH_RESULTS:
        client._log_error(
            "Search failed",
            error_code=ERROR_REQUEST_VALIDATION,
            cause="request_validation",
            error=f"n_results must be between 1 and {MAX_SEARCH_RESULTS}",
        )
        return []

    store = client._get_store_for_collection(collection)
    if not store:
        logger.warning("VectorStore not available, returning empty results")
        return []

    (
        scanner_profile,
        effective_batch_size,
        effective_fragment_readahead,
        effective_batch_readahead,
        scanner_defaults_applied,
    ) = _resolve_scanner_tuning(
        n_results=n_results,
        batch_size=batch_size,
        fragment_readahead=fragment_readahead,
        batch_readahead=batch_readahead,
    )

    options_cache = {
        "where_filter": where_filter,
        "batch_size": effective_batch_size,
        "fragment_readahead": effective_fragment_readahead,
        "batch_readahead": effective_batch_readahead,
        "scan_limit": scan_limit,
        "projection": projection,
    }
    cache_key = (
        f"{collection}:{query}:{n_results}:{json.dumps(options_cache, sort_keys=True, default=str)}"
    )
    if use_cache:
        cached = client._search_cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for query: %s...", query[:50])
            return cached

    embed_timeout = search_embed_timeout()
    vector: list[float] | None = None
    cache_source = "none"
    cached_vector, cache_source = _get_cached_query_vector(query)
    if cached_vector is not None:
        vector = cached_vector
        _record_phase(
            "vector.embed.cache",
            0.0,
            hit=True,
            source=cache_source,
            cache_size=_query_embed_cache_size(),
        )
    else:
        _record_phase(
            "vector.embed.cache",
            0.0,
            hit=False,
            source=cache_source,
            cache_size=_query_embed_cache_size(),
        )

    if vector is None:
        # Try MCP embedding first (ports 3002, 3001, 3000), then fallback to HTTP
        mcp_started = time.perf_counter()
        mcp_rss_before, mcp_peak_before = _sample_memory()
        _cleanup_mcp_failure_cache()
        ordered_targets = _ordered_mcp_probe_targets()
        mcp_probe_targets: list[tuple[int, str]] = []
        mcp_skipped_backoff = 0
        for target_port, target_path in ordered_targets:
            if _is_mcp_target_in_backoff(target_port, target_path):
                mcp_skipped_backoff += 1
                continue
            mcp_probe_targets.append((target_port, target_path))
        mcp_cached_target = _get_cached_mcp_probe_target()
        mcp_success = False
        mcp_port = None
        mcp_path_used: str | None = None
        mcp_attempts = 0
        mcp_budget_s = max(0.5, float(embed_timeout))
        mcp_budget_exhausted = False
        for mcp_port, mcp_path in mcp_probe_targets:
            elapsed_s = time.perf_counter() - mcp_started
            remaining_s = mcp_budget_s - elapsed_s
            if remaining_s <= 0:
                mcp_budget_exhausted = True
                break
            attempt_timeout = min(float(embed_timeout), remaining_s)
            try:
                mcp_attempts += 1
                from omni.agent.cli.mcp_embed import embed_via_mcp

                vectors = await asyncio.wait_for(
                    embed_via_mcp(
                        [query],
                        port=mcp_port,
                        path=mcp_path,
                        request_timeout_s=attempt_timeout,
                    ),
                    timeout=attempt_timeout,
                )
                if vectors and len(vectors) > 0:
                    vector = vectors[0]
                    mcp_success = True
                    mcp_path_used = mcp_path
                    _clear_mcp_target_failure(mcp_port, mcp_path)
                    _remember_mcp_probe_target(mcp_port, mcp_path)
                    logger.info(f"MCP embedding succeeded on port {mcp_port}, path {mcp_path}")
                    break
                _remember_mcp_target_failure(mcp_port, mcp_path)
            except Exception as e:
                _remember_mcp_target_failure(mcp_port, mcp_path)
                logger.debug(f"MCP embedding failed on port {mcp_port}, path {mcp_path}: {e}")
                continue
        mcp_rss_after, mcp_peak_after = _sample_memory()
        mcp_failure_cache_size = _cleanup_mcp_failure_cache()
        _record_phase(
            "vector.embed.mcp",
            (time.perf_counter() - mcp_started) * 1000,
            success=mcp_success,
            port=mcp_port if mcp_success else None,
            path=mcp_path_used if mcp_success else None,
            cached_target_hit=(
                mcp_success
                and mcp_cached_target is not None
                and mcp_path_used is not None
                and (mcp_port, mcp_path_used) == mcp_cached_target
            ),
            cached_target_present=mcp_cached_target is not None,
            attempts=mcp_attempts,
            candidate_count=len(ordered_targets),
            skipped_backoff=mcp_skipped_backoff,
            negative_cache_size=mcp_failure_cache_size,
            budget_ms=round(mcp_budget_s * 1000, 2),
            budget_exhausted=mcp_budget_exhausted,
            **_memory_fields(mcp_rss_before, mcp_peak_before, mcp_rss_after, mcp_peak_after),
        )

        if not mcp_success:
            logger.warning("MCP embedding not available, falling back to HTTP embedding")
            from omni.foundation.config.settings import get_setting
            from omni.foundation.embedding_client import get_embedding_client

            base_url = get_setting("embedding.client_url") or (
                f"http://127.0.0.1:{int(get_setting('embedding.http_port', 18501))}"
            )
            http_started = time.perf_counter()
            http_rss_before, http_peak_before = _sample_memory()
            http_success = False
            http_skipped_backoff = False
            try:
                _cleanup_http_failure_cache()
                if _is_http_endpoint_in_backoff(base_url):
                    http_skipped_backoff = True
                    raise EmbeddingUnavailableError(
                        "Embedding HTTP endpoint is temporarily in backoff."
                    )
                emb_client = get_embedding_client(base_url)
                embed_task = asyncio.create_task(
                    emb_client.embed_batch([query], timeout_seconds=embed_timeout),
                )
                sleep_task = asyncio.create_task(asyncio.sleep(embed_timeout))
                done, pending = await asyncio.wait(
                    [embed_task, sleep_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for t in pending:
                    t.cancel()
                if embed_task in done and not embed_task.cancelled():
                    try:
                        vectors = embed_task.result()
                        if vectors and len(vectors) > 0:
                            vector = vectors[0]
                            _clear_http_endpoint_failure(base_url)
                            http_success = True
                    except Exception as e:
                        _remember_http_endpoint_failure(base_url)
                        raise EmbeddingUnavailableError(
                            f"Embedding HTTP service unavailable: {e}"
                        ) from e
                elif vector is None:
                    _remember_http_endpoint_failure(base_url)
                    raise EmbeddingUnavailableError(
                        f"Embedding timed out after {embed_timeout}s. "
                        "Ensure MCP embedding service is running and responsive."
                    )
            except EmbeddingUnavailableError:
                raise
            except Exception as e:
                _remember_http_endpoint_failure(base_url)
                raise EmbeddingUnavailableError(f"Embedding failed: {e}") from e
            finally:
                http_rss_after, http_peak_after = _sample_memory()
                _record_phase(
                    "vector.embed.http",
                    (time.perf_counter() - http_started) * 1000,
                    success=http_success,
                    skipped=http_skipped_backoff,
                    skipped_backoff=http_skipped_backoff,
                    negative_cache_size=_cleanup_http_failure_cache(),
                    **_memory_fields(
                        http_rss_before, http_peak_before, http_rss_after, http_peak_after
                    ),
                )

    if vector is not None and cache_source == "none":
        _remember_query_vector(query, vector)
    if vector is None:
        raise EmbeddingUnavailableError(
            "Embedding returned no vector. Ensure MCP embedding service is running."
        )

    search_started = time.perf_counter()
    search_rss_before, search_peak_before = _sample_memory()
    search_success = False
    try:
        with _phase_scope(
            "vector.search.options",
            {"collection": collection, "n_results": n_results},
        ) as options_phase:
            effective_projection = (
                projection if projection is not None else list(_DEFAULT_RESULT_PROJECTION)
            )
            options: dict[str, Any] = {}
            options_phase["scanner_profile"] = scanner_profile
            options_phase["scanner_defaults_applied"] = scanner_defaults_applied
            options_phase["batch_size"] = effective_batch_size
            options_phase["fragment_readahead"] = effective_fragment_readahead
            options_phase["batch_readahead"] = effective_batch_readahead
            if where_filter is not None:
                options["where_filter"] = (
                    json.dumps(where_filter) if isinstance(where_filter, dict) else where_filter
                )
            options["batch_size"] = effective_batch_size
            options["fragment_readahead"] = effective_fragment_readahead
            options["batch_readahead"] = effective_batch_readahead
            if scan_limit is not None:
                options["scan_limit"] = int(scan_limit)
            options["projection"] = effective_projection

        if not hasattr(store, "search_optimized"):
            client._log_error(
                "VectorStore binding missing required API: search_optimized",
                error_code=ERROR_BINDING_API_MISSING,
                cause="binding_contract",
                error="search_optimized unavailable",
                collection=collection,
            )
            return []

        with _phase_scope(
            "vector.search.options.encode",
            {"collection": collection, "n_results": n_results},
        ):
            options_json = build_search_options_json(options)
        results: list[SearchResult] = []
        _search_timeout = 6
        _IPC_BATCH_PROJECTION_THRESHOLD = 50
        ipc_enabled = n_results >= _IPC_BATCH_PROJECTION_THRESHOLD
        ipc_projection: list[str] | None = effective_projection if ipc_enabled else None

        if ipc_enabled and hasattr(store, "search_optimized_ipc"):
            try:
                import io

                import pyarrow.ipc

                with _phase_scope(
                    "vector.search.ipc.query",
                    {"collection": collection, "n_results": n_results, "success": False},
                ) as ipc_query_phase:
                    ipc_bytes = await asyncio.wait_for(
                        asyncio.to_thread(
                            store.search_optimized_ipc,
                            collection,
                            vector,
                            n_results,
                            options_json,
                            projection=ipc_projection,
                        ),
                        timeout=_search_timeout,
                    )
                    ipc_query_phase["success"] = True
                    ipc_query_phase["bytes"] = len(ipc_bytes)

                with _phase_scope(
                    "vector.search.ipc.decode",
                    {"collection": collection, "n_results": n_results},
                ) as ipc_decode_phase:
                    table = pyarrow.ipc.open_stream(io.BytesIO(ipc_bytes)).read_all()
                    payloads = VectorPayload.from_arrow_table(table)
                    ipc_decode_phase["rows"] = len(payloads)
                    for p in payloads:
                        score = (
                            p.score if p.score is not None else 1.0 / (1.0 + max(p.distance, 0.0))
                        )
                        results.append(
                            SearchResult(
                                content=p.content,
                                metadata=p.metadata,
                                distance=p.distance,
                                score=score,
                                id=p.id,
                            )
                        )
            except TimeoutError:
                logger.warning("Vector search (IPC) timed out", timeout_s=_search_timeout)
                results = []
            except Exception as ipc_err:
                logger.debug(
                    "search_optimized_ipc failed, falling back to JSON path", error=str(ipc_err)
                )
                results = []

        if not results and hasattr(store, "search_optimized"):
            with _phase_scope(
                "vector.search.json.query",
                {"collection": collection, "n_results": n_results, "success": False},
            ) as json_query_phase:
                try:
                    results_json = await asyncio.wait_for(
                        asyncio.to_thread(
                            store.search_optimized,
                            collection,
                            vector,
                            n_results,
                            options_json,
                        ),
                        timeout=_search_timeout,
                    )
                    json_query_phase["success"] = True
                except TimeoutError:
                    logger.warning("Vector search (JSON) timed out", timeout_s=_search_timeout)
                    results_json = []
                    json_query_phase["timeout"] = True
                json_query_phase["rows"] = len(results_json)

            with _phase_scope(
                "vector.search.json.parse",
                {"collection": collection, "n_results": n_results, "rows": len(results_json)},
            ) as json_parse_phase:
                for raw in results_json:
                    payload = parse_vector_payload(raw)
                    result_id, content, metadata, distance = payload.to_search_result_fields()
                    score = payload.score
                    if score is None:
                        score = 1.0 / (1.0 + max(distance, 0.0))
                    results.append(
                        SearchResult(
                            content=content,
                            metadata=metadata,
                            distance=distance,
                            score=score,
                            id=result_id,
                        )
                    )
                json_parse_phase["parsed"] = len(results)

        if use_cache:
            with _phase_scope(
                "vector.search.cache.set",
                {"collection": collection, "n_results": len(results)},
            ):
                client._search_cache.set(cache_key, results)
        search_success = True
        return results
    except EmbeddingUnavailableError:
        raise
    except (ValidationError, ValueError) as e:
        client._log_error(
            "Search failed",
            error_code=ERROR_PAYLOAD_VALIDATION,
            cause="payload_validation",
            error=str(e),
            collection=collection,
        )
        return []
    except Exception as e:
        if client._is_table_not_found(e):
            logger.debug(
                "VectorStore collection not found",
                collection=collection,
                error_code=ERROR_TABLE_NOT_FOUND,
            )
            return []
        client._log_error(
            "Search failed",
            error_code=ERROR_RUNTIME,
            cause="runtime",
            error=str(e),
            collection=collection,
        )
        return []
    finally:
        search_rss_after, search_peak_after = _sample_memory()
        _record_phase(
            "vector.search",
            (time.perf_counter() - search_started) * 1000,
            collection=collection,
            n_results=n_results,
            success=search_success,
            **_memory_fields(
                search_rss_before,
                search_peak_before,
                search_rss_after,
                search_peak_after,
            ),
        )
