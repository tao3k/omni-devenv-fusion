"""Tests for router configuration schema and loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from omni.core.router.config import (
    RouterConfidenceProfile,
    RouterSearchConfig,
    load_router_search_config,
    resolve_router_schema_path,
    router_search_json_schema,
    write_router_search_json_schema,
)


def test_load_router_search_config_from_settings(monkeypatch):
    """Settings values should be loaded when explicit args are not provided."""
    values = {
        "router.search.semantic_weight": 0.6,
        "router.search.keyword_weight": 0.4,
        "router.search.adaptive_threshold_step": 0.2,
        "router.search.adaptive_max_attempts": 4,
        "router.search.active_profile": "balanced",
        "router.search.auto_profile_select": True,
        "router.search.default_limit": 12,
        "router.search.default_threshold": 0.25,
        "router.search.rerank": False,
        "router.search.profiles": {
            "balanced": {
                "high_threshold": 0.8,
                "medium_threshold": 0.55,
                "high_base": 0.91,
                "high_scale": 0.06,
                "high_cap": 0.98,
                "medium_base": 0.61,
                "medium_scale": 0.31,
                "medium_cap": 0.88,
                "low_floor": 0.11,
            }
        },
    }

    monkeypatch.setattr(
        "omni.core.router.config.get_setting",
        lambda key, default=None: values.get(key, default),
    )

    config = load_router_search_config()

    assert config.semantic_weight == 0.6
    assert config.keyword_weight == 0.4
    assert config.adaptive_threshold_step == 0.2
    assert config.adaptive_max_attempts == 4
    assert config.active_profile == "balanced"
    assert config.auto_profile_select is True
    assert config.default_limit == 12
    assert config.default_threshold == 0.25
    assert config.rerank is False
    assert "balanced" in config.profiles
    assert config.active_confidence_profile.high_threshold == 0.8
    assert config.active_confidence_profile.medium_threshold == 0.55
    assert config.active_confidence_profile.low_floor == 0.11


def test_load_router_search_config_explicit_overrides(monkeypatch):
    """Explicit args should override settings values."""

    def _mock_get_setting(key, default=None):
        # Keep non-overridden fields valid while explicit args are asserted below.
        if key == "router.search.active_profile":
            return "balanced"
        if key == "router.search.auto_profile_select":
            return True
        if key == "router.search.profiles":
            return {
                "balanced": {
                    "high_threshold": 0.75,
                    "medium_threshold": 0.50,
                    "high_base": 0.90,
                    "high_scale": 0.05,
                    "high_cap": 0.99,
                    "medium_base": 0.60,
                    "medium_scale": 0.30,
                    "medium_cap": 0.89,
                    "low_floor": 0.10,
                }
            }
        if key == "router.search.default_limit":
            return 10
        if key == "router.search.default_threshold":
            return 0.2
        return 0.99

    monkeypatch.setattr("omni.core.router.config.get_setting", _mock_get_setting)

    config = load_router_search_config(
        semantic_weight=0.7,
        keyword_weight=0.3,
        adaptive_threshold_step=0.1,
        adaptive_max_attempts=2,
    )

    assert config.semantic_weight == 0.7
    assert config.keyword_weight == 0.3
    assert config.adaptive_threshold_step == 0.1
    assert config.adaptive_max_attempts == 2


def test_load_router_search_config_rejects_missing_active_profile(monkeypatch):
    values = {
        "router.search.active_profile": "missing",
        "router.search.profiles": {
            "balanced": {
                "high_threshold": 0.75,
                "medium_threshold": 0.50,
                "high_base": 0.90,
                "high_scale": 0.05,
                "high_cap": 0.99,
                "medium_base": 0.60,
                "medium_scale": 0.30,
                "medium_cap": 0.89,
                "low_floor": 0.10,
            }
        },
    }
    monkeypatch.setattr(
        "omni.core.router.config.get_setting",
        lambda key, default=None: values.get(key, default),
    )
    with pytest.raises(ValidationError):
        load_router_search_config()


def test_load_router_search_config_rejects_invalid_profile_ranges(monkeypatch):
    values = {
        "router.search.active_profile": "bad",
        "router.search.profiles": {
            "bad": {
                "high_threshold": 0.4,
                "medium_threshold": 0.6,
                "high_base": 0.90,
                "high_scale": 0.05,
                "high_cap": 0.99,
                "medium_base": 0.60,
                "medium_scale": 0.30,
                "medium_cap": 0.89,
                "low_floor": 0.10,
            }
        },
    }
    monkeypatch.setattr(
        "omni.core.router.config.get_setting",
        lambda key, default=None: values.get(key, default),
    )
    with pytest.raises(ValidationError):
        load_router_search_config()


def test_router_search_json_schema_contains_expected_fields():
    """JSON schema export should contain public config fields."""
    schema = router_search_json_schema()
    properties = schema.get("properties", {})

    assert "semantic_weight" in properties
    assert "active_profile" in properties
    assert "auto_profile_select" in properties
    assert "profiles" in properties
    assert "default_limit" in properties
    assert "default_threshold" in properties
    assert "rerank" in properties
    assert "keyword_weight" in properties
    assert "adaptive_threshold_step" in properties
    assert "adaptive_max_attempts" in properties


def test_resolve_router_schema_path_uses_prj_config(monkeypatch, tmp_path):
    """Schema path should resolve under conf_dir (driven by --conf)."""
    monkeypatch.setattr(
        "omni.core.router.config.get_setting",
        lambda key, default=None: "schemas/custom.router.schema.json",
    )
    monkeypatch.setattr(
        "omni.core.router.config.get_settings", lambda: type("S", (), {"conf_dir": str(tmp_path)})()
    )

    path = resolve_router_schema_path()
    assert path == tmp_path / "schemas" / "custom.router.schema.json"


def test_write_router_search_json_schema_writes_file(tmp_path):
    """Schema writer should materialize JSON schema at requested path."""
    target = tmp_path / "router.schema.json"
    output = write_router_search_json_schema(target)

    assert output == target
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert '"title": "RouterSearchConfig"' in content


def test_resolve_router_schema_path_keeps_absolute_path(monkeypatch):
    """Absolute schema_file should not be rebased to conf_dir."""
    monkeypatch.setattr(
        "omni.core.router.config.get_setting",
        lambda key, default=None: "/tmp/router.search.schema.json",
    )
    monkeypatch.setattr(
        "omni.core.router.config.get_settings",
        lambda: type("S", (), {"conf_dir": "/ignored"})(),
    )

    path = resolve_router_schema_path()
    assert str(path) == "/tmp/router.search.schema.json"


def test_router_search_config_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RouterSearchConfig(
            active_profile="balanced",
            profiles={
                "balanced": {
                    "high_threshold": 0.75,
                    "medium_threshold": 0.50,
                    "high_base": 0.90,
                    "high_scale": 0.05,
                    "high_cap": 0.99,
                    "medium_base": 0.60,
                    "medium_scale": 0.30,
                    "medium_cap": 0.89,
                    "low_floor": 0.10,
                }
            },
            unknown_field=1,
        )


def test_load_router_search_config_rerank_defaults_true_when_missing(monkeypatch):
    values = {
        "router.search.active_profile": "balanced",
        "router.search.profiles": {
            "balanced": {
                "high_threshold": 0.75,
                "medium_threshold": 0.50,
                "high_base": 0.90,
                "high_scale": 0.05,
                "high_cap": 0.99,
                "medium_base": 0.60,
                "medium_scale": 0.30,
                "medium_cap": 0.89,
                "low_floor": 0.10,
            }
        },
    }
    monkeypatch.setattr(
        "omni.core.router.config.get_setting",
        lambda key, default=None: values.get(key, default),
    )

    config = load_router_search_config()
    assert config.rerank is True


def test_router_confidence_profile_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RouterConfidenceProfile(
            high_threshold=0.75,
            medium_threshold=0.50,
            high_base=0.90,
            high_scale=0.05,
            high_cap=0.99,
            medium_base=0.60,
            medium_scale=0.30,
            medium_cap=0.89,
            low_floor=0.10,
            unknown_field=1,
        )
