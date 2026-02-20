"""Tests for semantic search embedding path selection (MCP vs HTTP fallback)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest


def _reset_vector_search_caches(monkeypatch) -> None:
    from omni.foundation.services.vector import search as vector_search

    isolated_path = Path(f"/tmp/omni-query-embed-test-{uuid4().hex}.json")
    monkeypatch.setattr(vector_search, "_LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT", None)
    monkeypatch.setattr(vector_search, "_QUERY_EMBED_CACHE", vector_search.OrderedDict())
    monkeypatch.setattr(vector_search, "_QUERY_EMBED_PERSIST_LOADED", False)
    monkeypatch.setattr(vector_search, "_QUERY_EMBED_PERSIST_RECORD", None)
    monkeypatch.setattr(vector_search, "_query_embed_persist_path", lambda: isolated_path)
    monkeypatch.setattr(vector_search, "_MCP_EMBED_FAILURE_UNTIL", {})
    monkeypatch.setattr(vector_search, "_HTTP_EMBED_FAILURE_UNTIL", {})
    # Keep test probe order deterministic regardless of local user config overrides.
    monkeypatch.setattr(vector_search, "_default_mcp_embed_ports", lambda: (3002, 3001, 3000))


def test_default_mcp_embed_ports_prefers_configured_port(monkeypatch):
    from omni.foundation.services.vector import search as vector_search

    monkeypatch.setattr(
        "omni.foundation.config.settings.get_setting",
        lambda key, default=None: 3302 if key == "mcp.preferred_embed_port" else default,
    )
    ports = vector_search._default_mcp_embed_ports()
    assert ports == (3302,)


def test_build_default_mcp_probe_targets_use_modern_paths_for_non_legacy_ports(monkeypatch):
    from omni.foundation.services.vector import search as vector_search

    monkeypatch.setattr(vector_search, "_default_mcp_embed_ports", lambda: (3302, 3001))
    targets = vector_search._build_default_mcp_probe_targets()
    assert (3302, "/messages/") in targets
    assert (3302, "/mcp") in targets
    assert (3302, "/") in targets
    assert (3302, "/message") not in targets
    assert (3001, "/message") in targets


class _DummyCache:
    def get(self, _key: str):
        return None

    def set(self, _key: str, _value) -> None:
        return None


class _DummyStore:
    def __init__(self) -> None:
        self.search_optimized_calls = 0
        self.last_options_json = ""

    def search_optimized(self, _collection, _vector, _limit, _options_json):
        self.search_optimized_calls += 1
        self.last_options_json = _options_json
        return []


class _DummyStoreWithIpc(_DummyStore):
    def __init__(self) -> None:
        super().__init__()
        self.search_optimized_ipc_calls = 0

    def search_optimized_ipc(self, *_args, **_kwargs):
        self.search_optimized_ipc_calls += 1
        return b""


@pytest.mark.asyncio
async def test_run_semantic_search_skips_http_fallback_when_mcp_succeeds(monkeypatch):
    """When MCP embedding succeeds, HTTP embedding fallback must not run."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)

    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return [[0.1, 0.2, 0.3]]

    http_called = {"value": False}

    def _fail_get_embedding_client(*_args, **_kwargs):
        http_called["value"] = True
        raise AssertionError("HTTP fallback should not be called when MCP embedding succeeds")

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)
    monkeypatch.setattr(
        "omni.foundation.embedding_client.get_embedding_client",
        _fail_get_embedding_client,
    )

    results = await run_semantic_search(
        client=client,
        query="hello",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )

    assert results == []
    assert dummy_store.search_optimized_calls == 1
    assert http_called["value"] is False


@pytest.mark.asyncio
async def test_run_semantic_search_records_mcp_phase_memory(monkeypatch):
    """MCP embedding phase should include RSS/peak fields for memory attribution."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)

    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return [[0.1, 0.2, 0.3]]

    captured: list[tuple[str, dict[str, object]]] = []

    def _fake_record_phase(phase: str, _duration_ms: float, **extra: object) -> None:
        captured.append((phase, extra))

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)
    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.record_phase",
        _fake_record_phase,
    )
    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.metrics.get_rss_mb",
        lambda: 100.0,
    )
    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.metrics.get_rss_peak_mb",
        lambda: 120.0,
    )

    _ = await run_semantic_search(
        client=client,
        query="hello",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )

    phase_names = [phase for phase, _extra in captured]
    assert "vector.search.options" in phase_names
    assert "vector.search.options.encode" in phase_names
    assert "vector.search.json.query" in phase_names
    assert "vector.search.json.parse" in phase_names

    json_query_phase = [extra for phase, extra in captured if phase == "vector.search.json.query"][
        -1
    ]
    assert json_query_phase["success"] is True
    assert json_query_phase["rows"] == 0

    mcp_phase = [extra for phase, extra in captured if phase == "vector.embed.mcp"][-1]
    assert mcp_phase["rss_before_mb"] == 100.0
    assert mcp_phase["rss_after_mb"] == 100.0
    assert mcp_phase["rss_delta_mb"] == 0.0
    assert mcp_phase["rss_peak_before_mb"] == 120.0
    assert mcp_phase["rss_peak_after_mb"] == 120.0
    assert mcp_phase["rss_peak_delta_mb"] == 0.0


@pytest.mark.asyncio
async def test_run_semantic_search_skips_ipc_path_for_small_n_results(monkeypatch):
    """Small result windows should bypass IPC path to avoid pyarrow cold-load overhead."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)

    dummy_store = _DummyStoreWithIpc()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    results = await run_semantic_search(
        client=client,
        query="hello",
        n_results=5,
        collection="knowledge_chunks",
        use_cache=False,
    )

    assert results == []
    assert dummy_store.search_optimized_ipc_calls == 0
    assert dummy_store.search_optimized_calls == 1


@pytest.mark.asyncio
async def test_run_semantic_search_prefers_cached_mcp_endpoint(monkeypatch):
    """Second call should probe only the previously successful MCP endpoint first."""
    from omni.foundation.services.vector import search as vector_search
    from omni.foundation.services.vector.search import run_semantic_search

    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    _reset_vector_search_caches(monkeypatch)
    attempts: list[tuple[int, str]] = []

    async def _fake_embed_via_mcp(_texts, *, port: int, path: str, **_kwargs):
        attempts.append((port, path))
        if (port, path) == (3001, "/message"):
            return [[0.1, 0.2, 0.3]]
        raise RuntimeError("unavailable")

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    _ = await run_semantic_search(
        client=client,
        query="first",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    assert (3001, "/message") in attempts
    assert vector_search._LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT == (3001, "/message")

    attempts.clear()
    _ = await run_semantic_search(
        client=client,
        query="second",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    assert attempts == [(3001, "/message")]
    assert dummy_store.search_optimized_calls == 2


@pytest.mark.asyncio
async def test_run_semantic_search_refreshes_cached_endpoint_after_failure(monkeypatch):
    """When cached endpoint fails, semantic search should probe fallback endpoints and refresh cache."""
    from omni.foundation.services.vector import search as vector_search
    from omni.foundation.services.vector.search import run_semantic_search

    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    _reset_vector_search_caches(monkeypatch)
    monkeypatch.setattr(vector_search, "_LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT", (3002, "/messages/"))
    attempts: list[tuple[int, str]] = []

    async def _fake_embed_via_mcp(_texts, *, port: int, path: str, **_kwargs):
        attempts.append((port, path))
        if (port, path) == (3000, "/messages/"):
            return [[0.1, 0.2, 0.3]]
        raise RuntimeError("unavailable")

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    _ = await run_semantic_search(
        client=client,
        query="refresh",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    assert attempts[0] == (3002, "/messages/")
    assert (3000, "/messages/") in attempts
    assert vector_search._LAST_SUCCESSFUL_MCP_EMBED_ENDPOINT == (3000, "/messages/")

    attempts.clear()
    _ = await run_semantic_search(
        client=client,
        query="refresh-again",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    assert attempts == [(3000, "/messages/")]
    assert dummy_store.search_optimized_calls == 2


@pytest.mark.asyncio
async def test_run_semantic_search_reuses_cached_query_embedding(monkeypatch):
    """Same-query calls in one process should reuse embedding vector and skip MCP call."""
    from omni.foundation.services.vector.search import run_semantic_search

    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    _reset_vector_search_caches(monkeypatch)
    mcp_calls = {"count": 0}

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        mcp_calls["count"] += 1
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    _ = await run_semantic_search(
        client=client,
        query="same-query",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    _ = await run_semantic_search(
        client=client,
        query="same-query",
        n_results=5,
        collection="knowledge_chunks",
        use_cache=False,
    )

    assert mcp_calls["count"] == 1
    assert dummy_store.search_optimized_calls == 2


@pytest.mark.asyncio
async def test_run_semantic_search_reuses_persisted_last_query_embedding(monkeypatch, tmp_path):
    """Cross-process warm-start should reuse persisted last query embedding."""
    from omni.foundation.services.vector import search as vector_search
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    monkeypatch.setattr(
        vector_search,
        "_query_embed_persist_path",
        lambda: tmp_path / "query-embed-last.json",
    )

    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    mcp_calls = {"count": 0}

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        mcp_calls["count"] += 1
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    # First call populates both in-memory and persisted cache
    _ = await run_semantic_search(
        client=client,
        query="persisted-query",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    assert mcp_calls["count"] == 1
    assert (tmp_path / "query-embed-last.json").exists()

    # Simulate a fresh process by clearing all in-memory caches/state
    monkeypatch.setattr(vector_search, "_QUERY_EMBED_CACHE", vector_search.OrderedDict())
    monkeypatch.setattr(vector_search, "_QUERY_EMBED_PERSIST_LOADED", False)
    monkeypatch.setattr(vector_search, "_QUERY_EMBED_PERSIST_RECORD", None)

    # Second call should hit persisted cache and skip MCP
    async def _fail_embed_via_mcp(_texts, **_kwargs):
        raise AssertionError("MCP should not be called when persisted cache matches")

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fail_embed_via_mcp)

    captured: list[tuple[str, dict[str, object]]] = []

    def _fake_record_phase(phase: str, _duration_ms: float, **extra: object) -> None:
        captured.append((phase, extra))

    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.record_phase",
        _fake_record_phase,
    )

    _ = await run_semantic_search(
        client=client,
        query="persisted-query",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )
    assert dummy_store.search_optimized_calls == 2
    embed_cache_phase = [extra for phase, extra in captured if phase == "vector.embed.cache"][-1]
    assert embed_cache_phase["hit"] is True
    assert embed_cache_phase["source"] == "persistent"
    assert all(phase != "vector.embed.mcp" for phase, _extra in captured)


@pytest.mark.asyncio
async def test_run_semantic_search_applies_default_projection(monkeypatch):
    """Semantic search should apply projection and adaptive small scanner defaults."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    _ = await run_semantic_search(
        client=client,
        query="projection",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )

    options = json.loads(dummy_store.last_options_json)
    assert options["batch_size"] == 256
    assert options["fragment_readahead"] == 2
    assert options["batch_readahead"] == 4
    assert "scan_limit" not in options
    assert options["projection"] == ["id", "content", "_distance", "metadata"]


@pytest.mark.asyncio
async def test_run_semantic_search_uses_medium_profile_for_larger_windows(monkeypatch):
    """Larger result windows should use medium scanner profile defaults."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    _ = await run_semantic_search(
        client=client,
        query="medium-window",
        n_results=64,
        collection="knowledge_chunks",
        use_cache=False,
    )

    options = json.loads(dummy_store.last_options_json)
    assert options["batch_size"] == 1024
    assert options["fragment_readahead"] == 4
    assert options["batch_readahead"] == 16


@pytest.mark.asyncio
async def test_run_semantic_search_keeps_explicit_scanner_overrides(monkeypatch):
    """Explicit scanner options should take precedence over adaptive defaults."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)

    _ = await run_semantic_search(
        client=client,
        query="explicit-overrides",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
        batch_size=777,
        fragment_readahead=9,
        batch_readahead=33,
    )

    options = json.loads(dummy_store.last_options_json)
    assert options["batch_size"] == 777
    assert options["fragment_readahead"] == 9
    assert options["batch_readahead"] == 33


@pytest.mark.asyncio
async def test_run_semantic_search_skips_mcp_probe_targets_in_backoff(monkeypatch):
    """Endpoints in MCP backoff should be skipped and search should move to HTTP fallback."""
    from omni.foundation.services.vector import search as vector_search
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    mcp_calls = {"count": 0}

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        mcp_calls["count"] += 1
        return None

    class _HttpClient:
        async def embed_batch(self, _texts, timeout_seconds=None):
            return [[0.1, 0.2, 0.3]]

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)
    monkeypatch.setattr(
        "omni.foundation.embedding_client.get_embedding_client",
        lambda _base_url: _HttpClient(),
    )

    for port, path in vector_search._build_default_mcp_probe_targets():
        vector_search._remember_mcp_target_failure(port, path)

    _ = await run_semantic_search(
        client=client,
        query="backoff",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )

    assert mcp_calls["count"] == 0
    assert dummy_store.search_optimized_calls == 1


@pytest.mark.asyncio
async def test_run_semantic_search_skips_http_call_when_http_backoff_active(monkeypatch):
    """HTTP fallback should fail fast when endpoint is in backoff cache."""
    from omni.foundation.services.embedding import EmbeddingUnavailableError
    from omni.foundation.services.vector import search as vector_search
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    async def _fake_embed_via_mcp(_texts, **_kwargs):
        return None

    get_client_calls = {"count": 0}

    def _fake_get_embedding_client(_base_url: str):
        get_client_calls["count"] += 1
        raise AssertionError("HTTP client should not be created when endpoint backoff is active")

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _fake_embed_via_mcp)
    monkeypatch.setattr(
        "omni.foundation.embedding_client.get_embedding_client",
        _fake_get_embedding_client,
    )

    base_url = "http://127.0.0.1:18501"
    vector_search._remember_http_endpoint_failure(base_url)
    for port, path in vector_search._build_default_mcp_probe_targets():
        vector_search._remember_mcp_target_failure(port, path)

    def _fake_get_setting(key: str, default=None):
        if key == "embedding.client_url":
            return base_url
        return default

    monkeypatch.setattr("omni.foundation.config.settings.get_setting", _fake_get_setting)

    with pytest.raises(EmbeddingUnavailableError):
        _ = await run_semantic_search(
            client=client,
            query="http-backoff",
            n_results=3,
            collection="knowledge_chunks",
            use_cache=False,
        )

    assert get_client_calls["count"] == 0


@pytest.mark.asyncio
async def test_run_semantic_search_limits_total_mcp_probe_budget(monkeypatch):
    """MCP probe loop should respect global budget to avoid N * timeout stalls."""
    from omni.foundation.services.vector.search import run_semantic_search

    _reset_vector_search_caches(monkeypatch)
    dummy_store = _DummyStore()
    client = MagicMock()
    client._get_store_for_collection.return_value = dummy_store
    client._search_cache = _DummyCache()
    client._log_error = MagicMock()
    client._is_table_not_found = lambda _e: False

    mcp_calls = {"count": 0}

    async def _slow_embed_via_mcp(_texts, **_kwargs):
        mcp_calls["count"] += 1
        await asyncio.sleep(0.35)
        return None

    class _HttpClient:
        async def embed_batch(self, _texts, timeout_seconds=None):
            return [[0.1, 0.2, 0.3]]

    captured: list[tuple[str, dict[str, object]]] = []

    def _fake_record_phase(phase: str, _duration_ms: float, **extra: object) -> None:
        captured.append((phase, extra))

    monkeypatch.setattr("omni.agent.cli.mcp_embed.embed_via_mcp", _slow_embed_via_mcp)
    monkeypatch.setattr(
        "omni.foundation.embedding_client.get_embedding_client",
        lambda _base_url: _HttpClient(),
    )
    monkeypatch.setattr(
        "omni.foundation.services.vector.search.search_embed_timeout",
        lambda: 1,
    )
    monkeypatch.setattr(
        "omni.foundation.runtime.skills_monitor.record_phase",
        _fake_record_phase,
    )

    _ = await run_semantic_search(
        client=client,
        query="budget",
        n_results=3,
        collection="knowledge_chunks",
        use_cache=False,
    )

    assert mcp_calls["count"] < 6
    mcp_phase = [extra for phase, extra in captured if phase == "vector.embed.mcp"][-1]
    assert int(mcp_phase["attempts"]) < int(mcp_phase["candidate_count"])
