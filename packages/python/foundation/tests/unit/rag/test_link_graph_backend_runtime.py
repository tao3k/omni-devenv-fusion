"""Tests for link-graph runtime config helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from omni.foundation.config.link_graph_runtime import (
    DEFAULT_LINK_GRAPH_BACKEND,
    DEFAULT_LINK_GRAPH_CANDIDATE_MULTIPLIER,
    DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH,
    DEFAULT_LINK_GRAPH_DELTA_FULL_REBUILD_THRESHOLD,
    DEFAULT_LINK_GRAPH_EXCLUDED_ADDITIONAL_DIRS,
    DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS,
    DEFAULT_LINK_GRAPH_GRAPH_ROWS_PER_SOURCE,
    DEFAULT_LINK_GRAPH_HYBRID_MIN_HITS,
    DEFAULT_LINK_GRAPH_HYBRID_MIN_TOP_SCORE,
    DEFAULT_LINK_GRAPH_MAX_SOURCES,
    DEFAULT_LINK_GRAPH_POLICY_CACHE_TTL_SECONDS,
    DEFAULT_LINK_GRAPH_STATS_CACHE_TTL_SEC,
    DEFAULT_LINK_GRAPH_STATS_PERSISTENT_CACHE_TTL_SEC,
    DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC,
    DEFAULT_LINK_GRAPH_STATS_RESPONSE_REFRESH_TIMEOUT_SEC,
    DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC,
    LINK_GRAPH_CACHE_VALKEY_URL_ENV,
    LINK_GRAPH_VALKEY_KEY_PREFIX_ENV,
    LINK_GRAPH_VALKEY_TTL_SECONDS_ENV,
    get_link_graph_backend_name,
    get_link_graph_cache_key_prefix,
    get_link_graph_cache_ttl_seconds,
    get_link_graph_cache_valkey_url,
    get_link_graph_candidate_multiplier,
    get_link_graph_default_config_relative_path,
    get_link_graph_excluded_dirs,
    get_link_graph_graph_rows_per_source,
    get_link_graph_hybrid_min_hits,
    get_link_graph_hybrid_min_top_score,
    get_link_graph_include_dirs,
    get_link_graph_max_sources,
    get_link_graph_policy_cache_ttl_seconds,
    get_link_graph_policy_search_timeout_scale,
    get_link_graph_policy_search_timeout_seconds,
    get_link_graph_policy_timeout_marker_ttl_seconds,
    get_link_graph_proximity_max_parallel_stems,
    get_link_graph_proximity_max_stems,
    get_link_graph_proximity_neighbor_limit,
    get_link_graph_proximity_stem_cache_ttl_seconds,
    get_link_graph_proximity_timeout_seconds,
    get_link_graph_retrieval_mode,
    get_link_graph_root_dir,
    get_link_graph_runtime_config,
    get_link_graph_stats_cache_ttl_sec,
    get_link_graph_stats_response_probe_timeout_sec,
    get_link_graph_stats_response_refresh_timeout_sec,
    get_link_graph_stats_timeout_sec,
    normalize_link_graph_dir_entries,
    resolve_link_graph_cache_key_prefix,
    resolve_link_graph_cache_ttl_seconds,
    resolve_link_graph_cache_valkey_url,
    resolve_link_graph_excluded_dirs,
    resolve_link_graph_include_dirs,
)


def test_get_link_graph_default_config_relative_path_defaults() -> None:
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda _k, default=None: default,
    ):
        relative_path = get_link_graph_default_config_relative_path()

    assert str(relative_path) == DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH


def test_get_link_graph_default_config_relative_path_falls_back_on_blank() -> None:
    def _fake_get_setting(key: str, default: object = None) -> object:
        if key == "link_graph.config_relative_path":
            return " "
        return default

    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting", side_effect=_fake_get_setting
    ):
        relative_path = get_link_graph_default_config_relative_path()

    assert str(relative_path) == DEFAULT_LINK_GRAPH_CONFIG_RELATIVE_PATH


def test_get_link_graph_default_config_relative_path_prefers_configured() -> None:
    def _fake_get_setting(key: str, default: object = None) -> object:
        if key == "link_graph.config_relative_path":
            return ".link_graph/config.toml"
        return default

    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting", side_effect=_fake_get_setting
    ):
        relative_path = get_link_graph_default_config_relative_path()

    assert str(relative_path) == ".link_graph/config.toml"


def test_normalize_link_graph_dir_entries_dedup_and_clean() -> None:
    raw = [".cache/", r"docs\notes", "docs/notes", "  target  ", ".", ""]

    normalized = normalize_link_graph_dir_entries(raw)

    assert normalized == [".cache", "docs/notes", "target"]


def test_resolve_link_graph_excluded_dirs_ignores_hidden_config_and_merges_defaults() -> None:
    raw = [".cache", "custom-build", "TARGET", "custom-build"]

    resolved = resolve_link_graph_excluded_dirs(raw)

    assert resolved[: len(DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS)] == list(
        DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS
    )
    assert "custom-build" in resolved
    lowered = [item.lower() for item in resolved]
    assert "target" in lowered
    assert lowered.count("target") == 1
    assert resolved.count(".cache") == 1


def test_get_link_graph_excluded_dirs_uses_setting_default() -> None:
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda _k, default=None: default,
    ):
        resolved = get_link_graph_excluded_dirs()

    expected = list(DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS) + list(
        DEFAULT_LINK_GRAPH_EXCLUDED_ADDITIONAL_DIRS
    )
    assert resolved == expected


def test_resolve_link_graph_include_dirs_prefers_explicit() -> None:
    resolved = resolve_link_graph_include_dirs(
        ["docs/", r"assets\knowledge", "docs"],
        notebook_root=None,
        include_dirs_auto=True,
        auto_candidates_raw=["assets/knowledge"],
    )

    assert resolved == ["docs", "assets/knowledge"]


def test_resolve_link_graph_include_dirs_auto_from_existing_candidates(tmp_path) -> None:
    notebook = tmp_path / "notes"
    (notebook / "docs").mkdir(parents=True)
    (notebook / ".data" / "harvested").mkdir(parents=True)

    resolved = resolve_link_graph_include_dirs(
        [],
        notebook_root=notebook,
        include_dirs_auto=True,
        auto_candidates_raw=["docs", ".data/harvested", "missing"],
    )

    assert resolved == ["docs", ".data/harvested"]


def test_get_link_graph_include_dirs_uses_settings_overlay(tmp_path) -> None:
    notebook = tmp_path / "notes"
    (notebook / "docs").mkdir(parents=True)

    def _fake_get_setting(key: str, default: object = None) -> object:
        values = {
            "link_graph.include_dirs": [],
            "link_graph.include_dirs_auto": True,
            "link_graph.include_dirs_auto_candidates": ["docs", "missing"],
        }
        return values.get(key, default)

    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting", side_effect=_fake_get_setting
    ):
        resolved = get_link_graph_include_dirs(notebook)

    assert resolved == ["docs"]


def test_get_link_graph_include_dirs_supports_custom_setting_reader(tmp_path) -> None:
    notebook = tmp_path / "notes"
    (notebook / "docs").mkdir(parents=True)

    def _reader(key: str, default: object = None) -> object:
        values = {
            "link_graph.include_dirs": [],
            "link_graph.include_dirs_auto": "false",
            "link_graph.include_dirs_auto_candidates": ["docs"],
        }
        return values.get(key, default)

    resolved = get_link_graph_include_dirs(
        notebook,
        setting_reader=_reader,
    )

    assert resolved == []


def test_get_link_graph_excluded_dirs_supports_custom_setting_reader() -> None:
    def _reader(key: str, default: object = None) -> object:
        if key == "link_graph.exclude_dirs":
            return ["build", ".cache", "target"]
        return default

    resolved = get_link_graph_excluded_dirs(setting_reader=_reader)

    assert "build" in resolved
    assert resolved.count(".cache") == 1
    lowered = [item.lower() for item in resolved]
    assert lowered.count("target") == 1


def test_get_link_graph_backend_name_prefers_explicit_name() -> None:
    resolved = get_link_graph_backend_name("wendao")
    assert resolved == DEFAULT_LINK_GRAPH_BACKEND


def test_get_link_graph_backend_name_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unsupported link_graph backend"):
        get_link_graph_backend_name("legacy")


def test_get_link_graph_backend_name_reads_setting_reader() -> None:
    def _reader(key: str, default: object = None) -> object:
        if key == "link_graph.backend":
            return "wendao"
        return default

    resolved = get_link_graph_backend_name(setting_reader=_reader)
    assert resolved == DEFAULT_LINK_GRAPH_BACKEND


def test_get_link_graph_root_dir_prefers_setting_reader() -> None:
    def _reader(key: str, default: object = None) -> object:
        if key == "link_graph.root_dir":
            return "~/notes"
        return default

    resolved = get_link_graph_root_dir(setting_reader=_reader)
    assert resolved == "~/notes"


def test_get_link_graph_stats_timeouts_use_defaults() -> None:
    def _reader(_key: str, default: object = None) -> object:
        return default

    assert (
        get_link_graph_stats_cache_ttl_sec(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_STATS_CACHE_TTL_SEC
    )
    assert (
        get_link_graph_stats_timeout_sec(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC
    )
    assert (
        get_link_graph_stats_response_probe_timeout_sec(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC
    )
    assert (
        get_link_graph_stats_response_refresh_timeout_sec(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_STATS_RESPONSE_REFRESH_TIMEOUT_SEC
    )


def test_get_link_graph_stats_timeouts_clamp_invalid_values() -> None:
    def _reader(key: str, default: object = None) -> object:
        values = {
            "link_graph.stats_cache_ttl_sec": "-1",
            "link_graph.stats_timeout_sec": "nan",
            "link_graph.stats_response_probe_timeout_sec": None,
            "link_graph.stats_response_refresh_timeout_sec": "3.5",
        }
        return values.get(key, default)

    assert get_link_graph_stats_cache_ttl_sec(setting_reader=_reader) == 0.0
    assert (
        get_link_graph_stats_timeout_sec(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_STATS_TIMEOUT_SEC
    )
    assert (
        get_link_graph_stats_response_probe_timeout_sec(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_STATS_RESPONSE_PROBE_TIMEOUT_SEC
    )
    assert get_link_graph_stats_response_refresh_timeout_sec(setting_reader=_reader) == 3.5


def test_get_link_graph_retrieval_policy_defaults() -> None:
    def _reader(_key: str, default: object = None) -> object:
        return default

    assert get_link_graph_retrieval_mode(setting_reader=_reader) == "hybrid"
    assert (
        get_link_graph_policy_cache_ttl_seconds(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_POLICY_CACHE_TTL_SECONDS
    )
    assert (
        get_link_graph_candidate_multiplier(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_CANDIDATE_MULTIPLIER
    )
    assert get_link_graph_max_sources(setting_reader=_reader) == DEFAULT_LINK_GRAPH_MAX_SOURCES
    assert (
        get_link_graph_hybrid_min_hits(setting_reader=_reader) == DEFAULT_LINK_GRAPH_HYBRID_MIN_HITS
    )
    assert (
        get_link_graph_hybrid_min_top_score(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_HYBRID_MIN_TOP_SCORE
    )
    assert (
        get_link_graph_graph_rows_per_source(setting_reader=_reader)
        == DEFAULT_LINK_GRAPH_GRAPH_ROWS_PER_SOURCE
    )


def test_get_link_graph_retrieval_policy_clamps_invalid_values() -> None:
    def _reader(key: str, default: object = None) -> object:
        values = {
            "link_graph.candidate_multiplier": "0",
            "link_graph.max_sources": "200",
            "link_graph.hybrid.min_hits": "-1",
            "link_graph.hybrid.min_top_score": "2.5",
            "link_graph.graph_rows_per_source": "0",
            "link_graph.policy_cache_ttl_seconds": "9999",
            "link_graph.policy.search_timeout_seconds": "0.001",
            "link_graph.policy.timeout_marker_ttl_seconds": "999",
        }
        return values.get(key, default)

    assert get_link_graph_candidate_multiplier(setting_reader=_reader) == 1
    assert get_link_graph_max_sources(setting_reader=_reader) == 100
    assert get_link_graph_hybrid_min_hits(setting_reader=_reader) == 1
    assert get_link_graph_hybrid_min_top_score(setting_reader=_reader) == 1.0
    assert get_link_graph_graph_rows_per_source(setting_reader=_reader) == 1
    assert get_link_graph_policy_cache_ttl_seconds(setting_reader=_reader) == 600.0
    assert get_link_graph_policy_search_timeout_seconds(setting_reader=_reader) == 0.05
    assert get_link_graph_policy_timeout_marker_ttl_seconds(setting_reader=_reader) == 120.0


def test_get_link_graph_policy_search_timeout_scale_by_bucket() -> None:
    def _reader(key: str, default: object = None) -> object:
        values = {
            "link_graph.policy.search_timeout_scale.machine_like": "0.4",
            "link_graph.policy.search_timeout_scale.symbol_heavy": "0.7",
            "link_graph.policy.search_timeout_scale.short": "0.9",
            "link_graph.policy.search_timeout_scale.long_natural": "1.2",
            "link_graph.policy.search_timeout_scale.default": "1.1",
        }
        return values.get(key, default)

    assert get_link_graph_policy_search_timeout_scale("machine_like", setting_reader=_reader) == 0.4
    assert get_link_graph_policy_search_timeout_scale("symbol_heavy", setting_reader=_reader) == 0.7
    assert get_link_graph_policy_search_timeout_scale("short", setting_reader=_reader) == 0.9
    assert get_link_graph_policy_search_timeout_scale("long_natural", setting_reader=_reader) == 1.2
    assert get_link_graph_policy_search_timeout_scale("normal", setting_reader=_reader) == 1.1


def test_get_link_graph_proximity_defaults_and_clamps() -> None:
    def _default_reader(_key: str, default: object = None) -> object:
        return default

    assert get_link_graph_proximity_max_stems(setting_reader=_default_reader) == 8
    assert get_link_graph_proximity_stem_cache_ttl_seconds(setting_reader=_default_reader) == 60.0
    assert get_link_graph_proximity_timeout_seconds(setting_reader=_default_reader) == 5.0
    assert get_link_graph_proximity_max_parallel_stems(setting_reader=_default_reader) == 3
    assert get_link_graph_proximity_neighbor_limit(setting_reader=_default_reader) == 0

    def _clamp_reader(key: str, default: object = None) -> object:
        values = {
            "link_graph.proximity.max_stems": "0",
            "link_graph.proximity.stem_cache_ttl_seconds": "9999",
            "link_graph.proximity.timeout_seconds": "0",
            "link_graph.proximity.max_parallel_stems": "100",
            "link_graph.proximity.neighbor_limit": "-1",
        }
        return values.get(key, default)

    assert get_link_graph_proximity_max_stems(setting_reader=_clamp_reader) == 1
    assert get_link_graph_proximity_stem_cache_ttl_seconds(setting_reader=_clamp_reader) == 3600.0
    assert get_link_graph_proximity_timeout_seconds(setting_reader=_clamp_reader) == 0.05
    assert get_link_graph_proximity_max_parallel_stems(setting_reader=_clamp_reader) == 32
    assert get_link_graph_proximity_neighbor_limit(setting_reader=_clamp_reader) == 0


def test_resolve_link_graph_cache_valkey_url_prefers_setting_over_env() -> None:
    env = {LINK_GRAPH_CACHE_VALKEY_URL_ENV: "redis://127.0.0.1:6391/0"}
    resolved = resolve_link_graph_cache_valkey_url(
        env=env,
        setting_value="redis://127.0.0.1:6394/0",
    )

    assert resolved == "redis://127.0.0.1:6394/0"


def test_resolve_link_graph_cache_valkey_url_falls_back_to_setting() -> None:
    resolved = resolve_link_graph_cache_valkey_url(
        env={},
        setting_value="redis://127.0.0.1:6393/0",
    )

    assert resolved == "redis://127.0.0.1:6393/0"


def test_resolve_link_graph_cache_valkey_url_falls_back_to_env() -> None:
    env = {LINK_GRAPH_CACHE_VALKEY_URL_ENV: "redis://127.0.0.1:6391/0"}
    resolved = resolve_link_graph_cache_valkey_url(
        env=env,
        setting_value=None,
    )

    assert resolved == "redis://127.0.0.1:6391/0"


def test_resolve_link_graph_cache_valkey_url_ignores_redis_url_env() -> None:
    env = {"REDIS_URL": "redis://127.0.0.1:6392/0"}
    with pytest.raises(RuntimeError, match="link_graph cache valkey url is required"):
        resolve_link_graph_cache_valkey_url(env=env)


def test_get_link_graph_cache_valkey_url_prefers_setting_over_env() -> None:
    env = {LINK_GRAPH_CACHE_VALKEY_URL_ENV: "redis://127.0.0.1:6391/0"}
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda key, default=None: (
            "redis://127.0.0.1:6394/0" if key == "link_graph.cache.valkey_url" else default
        ),
    ):
        resolved = get_link_graph_cache_valkey_url(env=env, reload_on_missing=False)

    assert resolved == "redis://127.0.0.1:6394/0"


def test_get_link_graph_cache_valkey_url_falls_back_to_env() -> None:
    env = {LINK_GRAPH_CACHE_VALKEY_URL_ENV: "redis://127.0.0.1:6391/0"}
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda _key, default=None: default,
    ):
        resolved = get_link_graph_cache_valkey_url(env=env, reload_on_missing=False)

    assert resolved == "redis://127.0.0.1:6391/0"


def test_get_link_graph_cache_valkey_url_supports_custom_setting_reader_and_reload() -> None:
    reads = {"count": 0}

    def _reader(_key: str, _default: object = None) -> object:
        reads["count"] += 1
        if reads["count"] == 1:
            return None
        return "redis://127.0.0.1:6395/0"

    reload_called = {"count": 0}

    def _reload() -> None:
        reload_called["count"] += 1

    resolved = get_link_graph_cache_valkey_url(
        env={},
        setting_reader=_reader,
        reload_settings=_reload,
    )

    assert resolved == "redis://127.0.0.1:6395/0"
    assert reload_called["count"] == 1


def test_get_link_graph_cache_key_prefix_prefers_env() -> None:
    env = {LINK_GRAPH_VALKEY_KEY_PREFIX_ENV: "omni:from:env"}
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda key, default=None: (
            "omni:from:settings" if key == "link_graph.cache.key_prefix" else default
        ),
    ):
        resolved = get_link_graph_cache_key_prefix(env=env)

    assert resolved == "omni:from:env"


def test_get_link_graph_cache_key_prefix_falls_back_to_setting() -> None:
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda key, default=None: (
            "omni:from:settings" if key == "link_graph.cache.key_prefix" else default
        ),
    ):
        resolved = get_link_graph_cache_key_prefix(env={})

    assert resolved == "omni:from:settings"


def test_get_link_graph_cache_ttl_seconds_prefers_env() -> None:
    env = {LINK_GRAPH_VALKEY_TTL_SECONDS_ENV: "999"}
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda key, default=None: (
            300 if key == "link_graph.cache.ttl_seconds" else default
        ),
    ):
        resolved = get_link_graph_cache_ttl_seconds(env=env)

    assert resolved == "999"


def test_get_link_graph_cache_ttl_seconds_falls_back_to_setting() -> None:
    with patch(
        "omni.foundation.config.link_graph_runtime.get_setting",
        side_effect=lambda key, default=None: (
            300 if key == "link_graph.cache.ttl_seconds" else default
        ),
    ):
        resolved = get_link_graph_cache_ttl_seconds(env={})

    assert resolved == "300"


def test_get_link_graph_runtime_config_resolves_unified_fields() -> None:
    env = {LINK_GRAPH_CACHE_VALKEY_URL_ENV: "redis://127.0.0.1:6391/0"}

    def _reader(key: str, default: object = None) -> object:
        values = {
            "link_graph.root_dir": "~/notes",
            "link_graph.include_dirs": ["docs", "docs", "assets/knowledge"],
            "link_graph.include_dirs_auto": False,
            "link_graph.include_dirs_auto_candidates": ["assets/knowledge", "docs"],
            "link_graph.exclude_dirs": ["target", ".cache", "build"],
            "link_graph.stats_persistent_cache_ttl_sec": "42.5",
            "link_graph.index.delta.full_rebuild_threshold": "512",
            "link_graph.cache.valkey_url": "redis://127.0.0.1:6394/0",
            "link_graph.cache.key_prefix": "omni:link-graph:test",
            "link_graph.cache.ttl_seconds": 99,
        }
        return values.get(key, default)

    config = get_link_graph_runtime_config(
        env=env,
        reload_on_missing=False,
        setting_reader=_reader,
    )

    assert config.root_dir == "~/notes"
    assert config.include_dirs == ["docs", "assets/knowledge"]
    assert config.include_dirs_auto is False
    assert config.include_dirs_auto_candidates == ["assets/knowledge", "docs"]
    assert config.exclude_dirs[: len(DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS)] == list(
        DEFAULT_LINK_GRAPH_EXCLUDED_HIDDEN_DIRS
    )
    assert "build" in config.exclude_dirs
    assert config.stats_persistent_cache_ttl_sec == 42.5
    assert config.delta_full_rebuild_threshold == 512
    assert config.cache_valkey_url == "redis://127.0.0.1:6394/0"
    assert config.cache_key_prefix == "omni:link-graph:test"
    assert config.cache_ttl_seconds == "99"


def test_get_link_graph_runtime_config_uses_defaults_on_invalid_values() -> None:
    def _reader(_key: str, default: object = None) -> object:
        return default

    config = get_link_graph_runtime_config(
        env={LINK_GRAPH_CACHE_VALKEY_URL_ENV: "redis://127.0.0.1:6391/0"},
        reload_on_missing=False,
        setting_reader=_reader,
    )

    assert config.root_dir is None
    assert config.include_dirs == []
    assert config.include_dirs_auto is True
    assert config.include_dirs_auto_candidates == []
    assert (
        config.stats_persistent_cache_ttl_sec == DEFAULT_LINK_GRAPH_STATS_PERSISTENT_CACHE_TTL_SEC
    )
    assert config.delta_full_rebuild_threshold == DEFAULT_LINK_GRAPH_DELTA_FULL_REBUILD_THRESHOLD


def test_resolve_link_graph_cache_key_prefix_prefers_env() -> None:
    env = {LINK_GRAPH_VALKEY_KEY_PREFIX_ENV: "omni:from:env"}

    resolved = resolve_link_graph_cache_key_prefix(
        env=env,
        setting_value="omni:from:settings",
    )

    assert resolved == "omni:from:env"


def test_resolve_link_graph_cache_key_prefix_falls_back_to_setting() -> None:
    resolved = resolve_link_graph_cache_key_prefix(
        env={},
        setting_value="omni:from:settings",
    )

    assert resolved == "omni:from:settings"


def test_resolve_link_graph_cache_ttl_seconds_prefers_env() -> None:
    env = {LINK_GRAPH_VALKEY_TTL_SECONDS_ENV: "999"}

    resolved = resolve_link_graph_cache_ttl_seconds(
        env=env,
        setting_value=300,
    )

    assert resolved == "999"


def test_resolve_link_graph_cache_ttl_seconds_falls_back_to_setting() -> None:
    resolved = resolve_link_graph_cache_ttl_seconds(
        env={},
        setting_value=300,
    )

    assert resolved == "300"
